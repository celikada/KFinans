"""Adres maskeleme yardimcilari.

BACK-013 + COMP-024 (FAZ H): Wallet adresleri (xpub icerebilir) JSON
response'lari icin maskelenir. xpub sizmasi blockchain bakiye gecmisini
aciga cikarir; bu yuzden API hicbir endpoint'te full xpub plaintext
dondurmemeli (Excel export `?include_full_address=true` ile audit'li
opt-in haric).
"""


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
