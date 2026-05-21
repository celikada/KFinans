"""Adres ve PII maskeleme yardimcilari.

BACK-013 + COMP-024 (FAZ H): Wallet adresleri (xpub icerebilir) JSON
response'lari icin maskelenir. xpub sizmasi blockchain bakiye gecmisini
aciga cikarir; bu yuzden API hicbir endpoint'te full xpub plaintext
dondurmemeli (Excel export `?include_full_address=true` ile audit'li
opt-in haric).

SEC-010 (PII Log Filter): Application log'larina kullanici email'i plaintext
yazilmamali (KVKK m.4 veri minimizasyon + log aggregator/Sentry breadcrumb
sizmasi). `mask_email` local-part'i kismi maskeler, domain korunur.
"""

import hashlib


def mask_address(addr: str) -> str:
    """Adresi maskele: ilk 6 + son 4 karakter, ortasi `...`.

    Cok kisa adresler (<=12 char) icin 4+4 mask, 8 char altinda hic
    dokunulmaz (zaten label benzeri kisa).

    Ornekler:
        xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKi -> xpub6C...mzXd
        bc1qar0srrr7xfkvy5l643lydnw9re59gtzz -> bc1qar...59gtzz (degil — 4+4)
    """
    if not addr:
        return ""
    if len(addr) <= 8:
        return addr
    if len(addr) <= 12:
        return f"{addr[:4]}...{addr[-4:]}"
    return f"{addr[:6]}...{addr[-4:]}"


def mask_email(email: str | None) -> str:
    """Email local-part'i kismi maskele; domain korunur.

    Kural: local-part'in ilk + son karakteri tutulur, ortasi `*` ile doldurulur.
    Cok kisa (1-2 karakter) local-part icin tek `*` ile maskele. Domain her
    zaman plaintext (DNS arac/aggregator filtresi domain'i zaten gorur).

    Ornekler:
        celikada@gmail.com -> c******a@gmail.com
        ab@x.com           -> *@x.com
        a@x.com            -> *@x.com
        ""                 -> ""
        None               -> ""
        bozuk-string       -> *** (no @)
    """
    if not email:
        return ""
    if "@" not in email:
        # Email-shaped degil — tum stringi maskele (PII olabilir)
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        return f"*@{domain}"
    return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"


def hash_email(email: str | None) -> str:
    """Email'in SHA-256 hex digest'inin ilk 8 karakterini dondur.

    Audit/dedup amacli — ayni kullanici (ayni hash) tespiti icin mask_email
    yetersizse kullanilir. Geri donusu yok (one-way).
    """
    if not email:
        return ""
    return hashlib.sha256(email.lower().encode("utf-8")).hexdigest()[:8]
