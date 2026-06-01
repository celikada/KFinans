"""Startup kritik secret kontrolü (non-blocking).

Sebep (2026-06-01): production `RESEND_API_KEY` geçersizdi ("API key is invalid")
→ e-posta gönderimi SESSİZCE başarısız oldu (best-effort; kimse fark etmedi).
Bu modül startup'ta kritik secret'ları doğrular ve sorunları yapılandırılmış
WARNING/ERROR olarak log'lar (Sentry yakalar). Uygulamayı CRASH ETMEZ —
yalnızca görünürlük sağlar.

İki katman:
1. `check_critical_secrets()` — format/varlık kontrolü (her zaman, hızlı, offline).
2. `verify_resend_key()` — canlı Resend API probu (opt-in: `VERIFY_RESEND_ON_STARTUP`).
   Geçersiz-ama-iyi-formatlı key'i yakalar (format kontrolünün kaçırdığı durum).
"""

from __future__ import annotations

import logging

import httpx
from cryptography.fernet import Fernet

from app.config import settings

logger = logging.getLogger(__name__)


def check_critical_secrets() -> list[str]:
    """Kritik secret'ların varlık/format kontrolü. Issue listesi döner + log'lar."""
    issues: list[str] = []

    if not settings.secret_key or len(settings.secret_key) < 32:
        issues.append("SECRET_KEY eksik veya 32 karakterden kısa")

    try:
        Fernet(settings.fernet_key)
    except Exception:
        issues.append("FERNET_KEY geçersiz (Fernet decode edemedi)")

    rk = settings.resend_api_key
    if rk and not rk.startswith("re_"):
        issues.append("RESEND_API_KEY 're_' ile başlamıyor (format şüpheli)")
    elif not rk:
        # E-posta best-effort; eksik key kritik değil ama görünür olmalı.
        logger.info("STARTUP_SECRET_CHECK: RESEND_API_KEY tanımsız — e-posta gönderimi pasif")

    for issue in issues:
        logger.warning("STARTUP_SECRET_CHECK: %s", issue)
    return issues


async def verify_resend_key() -> bool | None:
    """Resend key'in canlı geçerliliğini doğrular (best-effort, opt-in).

    Returns:
        True  — key geçerli (HTTP 200)
        False — key GEÇERSİZ (HTTP 401) → e-posta çalışmaz, ERROR log'lanır
        None  — atlandı (key yok) veya prob başarısız (ağ/timeout)
    """
    if not settings.resend_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.resend.com/domains",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
    except (httpx.TimeoutException, httpx.RequestError):
        logger.warning("STARTUP_SECRET_CHECK: Resend geçerlilik probu başarısız (ağ/timeout) — atlandı")
        return None

    if resp.status_code == 401:
        logger.error("STARTUP_SECRET_CHECK: RESEND_API_KEY GEÇERSİZ (HTTP 401) — e-posta doğrulama/şifre sıfırlama gönderimi ÇALIŞMAYACAK")
        return False
    if resp.status_code >= 400:
        logger.warning("STARTUP_SECRET_CHECK: Resend beklenmeyen yanıt: HTTP %s", resp.status_code)
        return None
    return True
