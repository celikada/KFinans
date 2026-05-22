"""SEC: Application logger PII masking filter (defence-in-depth).

Mevcut log statement'larında manuel `mask_email(user.email)` çağrıları var
(`app/api/v1/auth.py` vb). Bu filter, unutulmuş veya 3. parti kütüphane
(SQLAlchemy, httpx, FastAPI) log'larında sızabilecek PII'leri otomatik
mask'ler — defence-in-depth katmanı.

Sentry `send_default_pii=False` (`OBS-001 init_sentry`) ayrı bir katman.
Bu filter STDOUT/STDERR + container log'lara da etki eder (Loki, journald,
docker logs gibi).

Pattern'ler:
- Email                   → <email>
- IPv4                    → <ip>
- JWT (eyJ-eyJ-sig)       → <jwt>
- Authorization Bearer    → Bearer <token>
- Kredi kartı (PAN 16d)   → <card>

Bilinçli sınırlamalar:
- IPv6 yok (KFinans şu anda IPv6 trafik almıyor, edge case)
- Phone number yok (TR formatı çok varyatif; false positive riski)
- Pattern'ler conservative — false-positive < false-negative tercihi.

Test: tests/unit/test_log_filter.py
"""

from __future__ import annotations

import logging
import re

# (compiled regex, replacement) liste sırası önemli değil — hepsi sub uygulanır.
# Tüm PATTERNS module-level compile edilir (her log emission'da yeniden compile yok).
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Email — RFC 5322 simplified: alfanumerik + nokta/dash/underscore/plus
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b"), "<email>"),
    # JWT — eyJ ile başlayan 3-segmentli base64url string (header.payload.sig)
    # Bearer pattern'den ÖNCE çalışsın diye burada (Bearer'dan önce match yapar)
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "<jwt>"),
    # Authorization: Bearer <token> — JWT pattern'ı yakalamayan opaque token'lar için
    (re.compile(r"Bearer\s+[A-Za-z0-9_.\-]{20,}", re.IGNORECASE), "Bearer <token>"),
    # IPv4 — 4 oktet 0-255 (basit, false positive: tarih gibi `192.168.1.1` yakalamaz)
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
    # Kredi kartı PAN — 16 digit, opsiyonel boşluk/dash arasında
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "<card>"),
]


class PIIFilter(logging.Filter):
    """logging.Filter — record.getMessage() çıktısında PII'leri mask'ler.

    Filter args/msg substitution sonrasında çalışır (`record.getMessage()`
    args'ı msg'ye uygular). Mask sonrası `record.msg = masked; record.args = ()`
    set edilir; handler bir daha args uygulamaya çalışmasın.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            original = record.getMessage()
        except (TypeError, ValueError):
            # msg/args mismatch — orijinal davranışı bozma, kayıt yine geçsin.
            return True

        masked = original
        for pattern, replacement in _PATTERNS:
            masked = pattern.sub(replacement, masked)

        if masked != original:
            record.msg = masked
            record.args = ()

        return True


def install_pii_filter(target_logger: logging.Logger | None = None) -> None:
    """Root logger'ın tüm handler'larına PIIFilter ekler (idempotent).

    `main.py` lifespan startup'ta veya `logging.basicConfig` sonrasında çağrılır.
    Mevcut PIIFilter handler'da varsa atlanır (çift mask zarar vermez ama
    gereksiz CPU). `target_logger` None → root logger.
    """
    logger = target_logger if target_logger is not None else logging.getLogger()
    for handler in logger.handlers:
        if not any(isinstance(f, PIIFilter) for f in handler.filters):
            handler.addFilter(PIIFilter())
