"""SEC (audit #5): Sifre politikasi sertlestirmesi.

Iki katmanli kontrol:
  1. zxcvbn strength score >= 3 (out of 4) — context-aware (email + isim).
  2. HIBP k-anonymity check (Have I Been Pwned) — sizmis sifre reddet.

Ikinci katman ag I/O gerektirir; fail-open (HIBP API down -> izin ver, log
warning). Bu UX vs security trade-off bilincli bir karar: HIBP downtime
saatlerce surebilir, ve gercek saldirgan zaten zxcvbn'i bypass etmez.
zxcvbn katmani offline ve hep aktif — birinci savunma.

Logger PII guvenli: sifre kendisi log'a YAZILMAZ; sadece score, leaked_count,
warning/suggestion metinleri log'lanir.
"""

from __future__ import annotations

import hashlib
import logging

import httpx
from zxcvbn import zxcvbn

from app.config import settings

logger = logging.getLogger(__name__)

# OWASP ASVS V2.1.7 + NIST 800-63B: minimum zxcvbn score
# 0 = too guessable (instant), 1 = very guessable (< 1e3),
# 2 = somewhat guessable (< 1e6), 3 = safely unguessable (< 1e8),
# 4 = very unguessable (>= 1e10). Para verisi tutan SaaS icin 3 makul.
_MIN_ZXCVBN_SCORE = 3

# HIBP API timeout — kullanici akisini bloklamamak icin kisa.
_HIBP_TIMEOUT_SECONDS = 3.0
_HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"


def check_password_strength(
    password: str,
    user_inputs: list[str] | None = None,
) -> tuple[bool, str]:
    """zxcvbn ile sifre gucu kontrol et.

    Args:
        password: Plaintext sifre (caller hash'lemeden once verir).
        user_inputs: Kullanici bilgileri (email, full_name) — bunlari iceren
            sifreler reddedilir. Ornegin "ada.celik@gmail.com" kullanan biri
            "AdaCelik2026" yazarsa zxcvbn score'u dusurur.

    Returns:
        (is_valid, error_message_tr).
        is_valid=True -> error_message_tr bos string.
        is_valid=False -> kullaniciya gosterilebilir Turkce mesaj (PII icermez).
    """
    # zxcvbn user_inputs None'a izin vermez; bos liste default
    inputs = user_inputs or []
    # None elemanlari at (full_name None olabilir)
    inputs = [s for s in inputs if s]

    result = zxcvbn(password, user_inputs=inputs)
    score: int = result.get("score", 0)

    if score >= _MIN_ZXCVBN_SCORE:
        return True, ""

    # zxcvbn feedback Turkce'ye cevirmek karmasik (lokal sozluk yok);
    # genel Turkce mesaj + ipucu sayisi yeterli.
    feedback = result.get("feedback", {}) or {}
    warning = feedback.get("warning") or ""
    suggestions = feedback.get("suggestions") or []

    # PII guvenli log — sifre yok, sadece score + feedback metinleri
    logger.info(
        "Zayif sifre reddedildi: score=%s warning=%r suggestions=%s",
        score,
        warning,
        suggestions,
    )

    msg = (
        "Sifreniz cok zayif (skor "
        f"{score}/4). Daha guclu bir sifre secin: en az 12 karakter, "
        "kisisel bilgilerinizi (e-posta, isim) icermesin, yaygin sifrelerden "
        "(123456, password gibi) kacinin."
    )
    return False, msg


# S7483: httpx native `timeout=` parametresi (AsyncClient'a iletilir) idiomatik ve
# yeterli; asyncio.timeout() context manager'a geçmek ek bir katman getirmez.
async def check_hibp_pwned(password: str, timeout: float = _HIBP_TIMEOUT_SECONDS) -> int:  # NOSONAR
    """Have I Been Pwned k-anonymity kontrol — sizmis sifre var mi?

    Sifrenin SHA-1 hash'inin ilk 5 karakteri prefix olarak API'ye gonderilir.
    API ayni prefix ile baslayan tum sizinti hash'lerini doner; biz suffix
    eslesmesini lokal yapariz. Plaintext veya tam hash API'ye gitmez.

    Args:
        password: Plaintext sifre.
        timeout: HTTP timeout (default 3 sn).

    Returns:
        leaked_count: 0 = bulunamadi (guvenli), >= 1 = sizinti sayisi.

    Notlar:
        - Fail-open: timeout/network/non-200 -> 0 doner + warning log.
          Saldirgan HIBP'yi DoS edip kayit yapacak deger degil; UX gercek
          dunya kosullarinda HIBP'nin dustugu durumlarda kullaniciyi bloklamaz.
        - SHA-1 burada hash collision icin DEGIL; HIBP API'sinin secimi.
          Plaintext asla aga gitmez, sadece prefix.
    """
    if not settings.hibp_check_enabled:
        return 0

    sha1_hex = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1_hex[:5], sha1_hex[5:]
    url = _HIBP_RANGE_URL.format(prefix=prefix)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers={"Add-Padding": "true"})
        if response.status_code != 200:
            logger.warning(
                "HIBP API beklenmeyen yanit: status=%s (fail-open)",
                response.status_code,
            )
            return 0
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        # Fail-open — kayit/sifre degisikligini bloklamayiz
        logger.warning("HIBP API erisilemedi: %s (fail-open)", type(exc).__name__)
        return 0

    # Response format: HASH_SUFFIX:COUNT (her satir bir hash)
    # Ornek satir: "1E4C9B93F3F0682250B6CF8331B7EE68FD8:12345"
    for line in response.text.splitlines():
        parts = line.strip().split(":")
        if len(parts) != 2:
            continue
        if parts[0].upper() == suffix:
            try:
                return int(parts[1])
            except ValueError:
                return 0
    return 0
