"""Ekstre parser'ları için ortak yardımcılar: sayı/tarih ayrıştırma.

Türk banka ekstreleri iki farklı sayı formatı kullanır:
- TR: "500.000,00" (nokta binlik, virgül ondalık) — Ziraat, Enpara
- EN/US: "17,495.87" (virgül binlik, nokta ondalık) — VakıfBank, Axess
`parse_amount` son görülen ayraçtan ondalık ayracını tespit eder, ikisini de
otomatik çözer.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_AMOUNT_CLEAN_RE = re.compile(r"[^\d.,-]")
# Tarih: gün ve ay 2 hane, ayraç nokta veya slash (26.05.2026 / 10/05/2026).
_DATE_RE = re.compile(r"(\d{2})[./](\d{2})[./](\d{4})")

# Türkçe ay adları → ay numarası. Üç varyant tanınır: aksanlı ("şubat"),
# ASCII-translit ("subat") ve glyph-düşmüş ("ubat" — bazı PDF metin katmanları
# Türkçe-özel harfi tamamen düşürür: Mayıs→Mays, Ağustos→Austos, Aralık→Aralk).
_TR_MONTHS: dict[str, int] = {
    "ocak": 1,
    "şubat": 2,
    "subat": 2,
    "ubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "mayis": 5,
    "mays": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "agustos": 8,
    "austos": 8,
    "eylül": 9,
    "eylul": 9,
    "eyll": 9,
    "ekim": 10,
    "kasım": 11,
    "kasim": 11,
    "kasm": 11,
    "aralık": 12,
    "aralik": 12,
    "aralk": 12,
}
# Ay-adı token'ı: harf VEYA `(cid:N)` token (pdfplumber Türkçe harfi cid'e çevirir:
# "Mayıs"→"May(cid:0)s"). Bounded (3-12 birim) → ReDoS-safe.
_TR_MONTH_TOKEN = r"(?:\(cid:\d{1,4}\)|[A-Za-zçğıöşüÇĞİÖŞÜ]){3,12}"
_CID_TOKEN_RE = re.compile(r"\(cid:\d{1,4}\)")
# "5 Haziran 2026" / "01 Haziran 2026" (gün ay-adı yıl).
_TR_DATE_RE = re.compile(r"(\d{1,2})\s{1,3}(" + _TR_MONTH_TOKEN + r")\s{1,3}(\d{4})")

# Türkçe-özel harfler: bazı banka PDF'lerinin metin katmanı (font cmap eksiği)
# bunları düşürür ("Ödeme"→"deme", "Numarası"→"Numaras", "Özeti"→"zeti").
_TR_SPECIAL_CHARS = "çÇğĞıİöÖşŞüÜ"


# Türkçe-özel harf, PDF metin katmanında üç biçimde görülebilir:
#   (1) korunmuş   → tek non-space karakter ("Ödeme")
#   (2) düşmüş      → hiç karakter yok ("deme")     — bazı PDF render'ları
#   (3) cid token   → "(cid:0)" ("(cid:0)deme")     — pdfplumber'ın yaygın çıktısı
# Bu üçünü de kapsayan, bounded (ReDoS-safe) tek-harf deseni:
_TR_GLYPH = r"(?:\(cid:\d{1,4}\)|\S){0,2}"


def tr_tolerant(label: str) -> str:
    r"""Bir etiketi Türkçe-harf glyph bozulmasına dayanıklı regex desenine çevirir.

    Her Türkçe-özel harf `_TR_GLYPH` (korunmuş tek char VEYA `(cid:N)` token VEYA
    hiç; en çok 2 birim, bounded → ReDoS-safe), boşluklar `\s{1,3}` (çoklu boşluğa
    tolerans), diğer karakterler `re.escape` ile temsil edilir. Böylece hem sağlam
    ("Son Ödeme Tarihi") hem glyph-düşmüş ("Son deme Tarihi") hem pdfplumber cid
    ("Son (cid:0)deme Tarihi") metin eşleşir.
    """
    out: list[str] = []
    for ch in label:
        if ch in _TR_SPECIAL_CHARS:
            out.append(_TR_GLYPH)
        elif ch == " ":
            out.append(r"\s{1,3}")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def parse_amount(raw: str) -> Decimal:
    """TR veya EN formatlı para tutarını Decimal'e çevirir (otomatik tespit).

    Örnekler: "500.000,00" -> 500000.00, "17,495.87" -> 17495.87,
    "100000.00" -> 100000.00, "1.442,25" -> 1442.25.
    Geçersiz girdi `InvalidOperation` (Decimal) fırlatır.
    """
    cleaned = _AMOUNT_CLEAN_RE.sub("", raw.strip())
    last_comma = cleaned.rfind(",")
    last_dot = cleaned.rfind(".")
    if last_comma > last_dot:
        # TR: virgül ondalık ayracı, nokta binlik.
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # EN/US (veya tek nokta): virgül binlik ayracı.
        cleaned = cleaned.replace(",", "")
    if not cleaned or cleaned in {"-", ".", "-."}:
        raise InvalidOperation(f"boş/geçersiz tutar: {raw!r}")
    return Decimal(cleaned)


def parse_date(raw: str) -> date:
    """İlk "GG.AA.YYYY" veya "GG/AA/YYYY" tarihini date'e çevirir.

    Eşleşme yoksa `ValueError` fırlatır.
    """
    m = _DATE_RE.search(raw)
    if not m:
        raise ValueError(f"tarih bulunamadı: {raw!r}")
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def parse_turkish_date(raw: str) -> date:
    """İlk "GG AyAdı YYYY" (ör. "5 Haziran 2026") tarihini date'e çevirir.

    Eşleşme yoksa veya ay adı tanınmazsa `ValueError` fırlatır.
    """
    m = _TR_DATE_RE.search(raw)
    if not m:
        raise ValueError(f"Türkçe tarih bulunamadı: {raw!r}")
    # cid token'larını ay adından temizle: "May(cid:0)s" → "Mays" (glyph-düşmüş
    # biçim _TR_MONTHS'ta zaten var). pdfplumber Türkçe harfi cid'e çevirebilir.
    name = _CID_TOKEN_RE.sub("", m.group(2)).lower()
    month = _TR_MONTHS.get(name)
    if month is None:
        raise ValueError(f"ay adı tanınmadı: {raw!r}")
    return date(int(m.group(3)), month, int(m.group(1)))


def search_labeled_date(text: str, label: str, *, turkish: bool = False) -> date | None:
    """`label` etiketinden sonraki ilk tarihi döndürür; bulunamazsa None.

    "Bir Sonraki ... / Bir Önceki ..." gibi sonraki/önceki dönem tuzaklarını
    (etiketten hemen önceki bağlamda "sonraki"/"önceki" geçen eşleşmeleri) atlar.
    `turkish=True` ise ay-adı biçimli tarih ("12 Haziran 2026") çözer; aksi halde
    "GG.AA.YYYY"/"GG/AA/YYYY" sayısal biçim.
    """
    if turkish:
        date_pat = r"\d{1,2}\s{1,3}" + _TR_MONTH_TOKEN + r"\s{1,3}\d{4}"
        conv = parse_turkish_date
    else:
        date_pat = r"\d{2}[./]\d{2}[./]\d{4}"
        conv = parse_date
    # tr_tolerant: etiketteki Türkçe harfler glyph-düşmesine dayanıklı eşleşir.
    pattern = re.compile(tr_tolerant(label) + r"\s{0,3}:?\s{0,3}(" + date_pat + r")")
    for m in pattern.finditer(text):
        pre = text[max(0, m.start() - 24) : m.start()].lower()
        # "önceki" glyph-düşmüş hâli "nceki" — ikisini de yakala (ö düşebilir).
        if "sonraki" in pre or "nceki" in pre:
            continue
        return conv(m.group(1))
    return None


def clamp_day(day: int) -> int:
    """statement_day / payment_due_day model aralığına (1-28, le=28) sıkıştır."""
    return min(max(day, 1), 28)


def months_back(year: int, month: int, n: int) -> tuple[int, int]:
    """(year, month)'tan n ay geriye git; (year, month) döner (month 1-12)."""
    total = year * 12 + (month - 1) - n
    return total // 12, total % 12 + 1
