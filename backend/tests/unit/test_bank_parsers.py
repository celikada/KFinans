"""Enpara + VakıfBank ekstre parser'ları + ortak parse util + Axess fail-safe.

Fixture metinleri gerçek ekstrelerin pdfplumber'ın üreteceğine yakın temsilidir.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

import pytest

from app.services.statement_import import detect_parser
from app.services.statement_import._utils import (
    clamp_day,
    months_back,
    parse_amount,
    parse_date,
    tr_tolerant,
)
from app.services.statement_import.enpara import EnparaParser
from app.services.statement_import.vakifbank import VakifBankParser

# Glyph-düşmesini taklit eder: bazı PDF metin katmanları Türkçe-özel harfleri
# tamamen düşürür ("Ödeme"→"deme", "Numarası"→"Numaras", "Mayıs"→"Mays").
_TR_SPECIAL = "çÇğĞıİöÖşŞüÜ"


def _strip_tr(s: str) -> str:
    return s.translate({ord(c): None for c in _TR_SPECIAL})


def test_tr_tolerant_matches_intact_stripped_and_cid():
    pat = re.compile(tr_tolerant("Son Ödeme Tarihi") + r"\s{0,3}(\d{2}\.\d{2}\.\d{4})")
    assert pat.search("Son Ödeme Tarihi 05.06.2026").group(1) == "05.06.2026"  # korunmuş
    assert pat.search("Son deme Tarihi 05.06.2026").group(1) == "05.06.2026"  # glyph düşmüş
    # pdfplumber Türkçe harfi (cid:N) token'ına çevirir — bu da eşleşmeli (asıl bug):
    assert pat.search("Son (cid:0)deme Tarihi 05.06.2026").group(1) == "05.06.2026"
    # Boşluk → \s{1,3} (çoklu boşluk toleransı); Türkçe-özel harfsiz diğerleri re.escape.
    assert tr_tolerant("HesapKesim") == re.escape("HesapKesim")
    assert "\\s{1,3}" in tr_tolerant("Hesap Kesim")


# ─── Ortak parse util ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("500.000,00", Decimal("500000.00")),  # TR
        ("1.442,25", Decimal("1442.25")),  # TR
        ("9.000,00", Decimal("9000.00")),  # TR
        ("17,495.87", Decimal("17495.87")),  # EN
        ("320,000.00", Decimal("320000.00")),  # EN
        ("100000.00", Decimal("100000.00")),  # EN tek ayraç
        ("1.084,50", Decimal("1084.50")),  # TR
        ("289,00 TL", Decimal("289.00")),  # birim ek
    ],
)
def test_parse_amount_tr_en_autodetect(raw, expected):
    assert parse_amount(raw) == expected


def test_parse_amount_invalid_raises():
    with pytest.raises(InvalidOperation):
        parse_amount("abc")


def test_parse_date_dot_and_slash():
    assert parse_date("Hesap Kesim Tarihi : 26.05.2026") == date(2026, 5, 26)
    assert parse_date("Ekstre tarihi 10/05/2026") == date(2026, 5, 10)


def test_clamp_day():
    assert clamp_day(31) == 28
    assert clamp_day(15) == 15
    assert clamp_day(0) == 1


def test_months_back():
    assert months_back(2026, 5, 3) == (2026, 2)
    assert months_back(2026, 1, 1) == (2025, 12)


# ─── Enpara ──────────────────────────────────────────────────────────────────

ENPARA_TEXT = """Ekstre tarihi 10/05/2026
Ekstre borcu 1.442,25 TL
Minimum ödeme tutarı 289,00 TL
Son ödeme tarihi 20/05/2026
Ad soyad Ozan Çelikada
Kart numarası 5269 11** **** 1104
Kart limiti 9.000,00 TL
Kullanılabilir kart limiti 7.183,75 TL
11/04/2026 MCDONALDS ESKİŞEHİR 195,00 TL
Bir sonraki ekstrenizin tarihi 10/06/2026, son ödeme tarihi ise 22/06/2026'dır.
Enpara Bank A.Ş. Büyük Mükellefler V.D. 3350917589
"""


def test_detect_enpara():
    assert isinstance(detect_parser(ENPARA_TEXT), EnparaParser)


def test_enpara_fields():
    p = EnparaParser().parse(ENPARA_TEXT)
    assert p.bank_name == "Enpara"
    assert p.last_4 == "1104"
    assert p.credit_limit == Decimal("9000.00")  # "Kullanılabilir kart limiti" değil
    assert p.statement_date == date(2026, 5, 10)
    assert p.due_date == date(2026, 5, 20)  # "son ödeme tarihi ise 22/06" tuzağına düşmez
    assert p.statement_amount == Decimal("1442.25")
    assert p.statement_day == 10
    assert p.payment_due_day == 20
    assert p.installments == []  # Enpara örneğinde taksit yok


def test_enpara_missing_field_raises():
    with pytest.raises(ValueError):
        EnparaParser().parse("Enpara ama alan yok")


# Bazı Enpara PDF varyantlarının metin katmanı Türkçe karakterleri düşürür:
# "ödeme"→"deme", "numarası"→"numaras", "Açıklama"→"Aıklama" vb. Parser bu
# bozuk metinde de kart + ekstre alanlarını çıkarabilmeli (regresyon).
ENPARA_TEXT_STRIPPED = """Ekstre tarihi 10/06/2026
Ekstre borcu 4.915,01 TL
Minimum deme tutarı 984,00 TL
Son deme tarihi 22/06/2026
Ad soyad Ozan elikada
Kart numarası 5269 11** **** 1104
Kart limiti 9.000,00 TL
Kullanlabilir kart limiti 4.084,99 TL
lem tarihi Aıklama Taksit Tutar
08/06/2026 BIZIM CICEK EVI 1.100,00 TL
Bir sonraki ekstrenizin tarihi 10/07/2026, son deme tarihi ise 20/07/2026'dr.
Enpara Bank A.. B	y	k M	kellefler V.D. 3350917589
"""


def test_enpara_stripped_turkish_chars():
    """Türkçe karakteri düşmüş Enpara metni de doğru parse edilmeli."""
    p = EnparaParser().parse(ENPARA_TEXT_STRIPPED)
    assert p.bank_name == "Enpara"
    assert p.last_4 == "1104"
    assert p.credit_limit == Decimal("9000.00")
    assert p.statement_date == date(2026, 6, 10)
    assert p.due_date == date(2026, 6, 22)  # "son deme tarihi ise 20/07" tuzağına düşmez
    assert p.statement_amount == Decimal("4915.01")
    assert p.statement_day == 10
    assert p.payment_due_day == 22


# GERÇEK pdfplumber çıktısı: Enpara font'unda Türkçe-özel harf `(cid:N)` token'ı
# olur ("Son ödeme" → "Son (cid:0)deme", "Çelikada" → "(cid:16)elikada").
# İki sütunlu yerleşim → etiket+değer aynı satırda. (Asıl prod bug'ı — #v0.8.x.)
ENPARA_TEXT_CID = """Kredi Kartı Ekstresi
Ekstre tarihi 10/06/2026 Ad soyad Ozan (cid:16)elikada
Ekstre borcu 4.915,01 TL Kart numarası 5269 11** **** 1104
Minimum (cid:0)deme tutarı 984,00 TL Kart limiti 9.000,00 TL
Son (cid:0)deme tarihi 22/06/2026 Kullanılabilir kart limiti 4.084,99 TL
Bir sonraki ekstrenizin tarihi 10/07/2026, son (cid:7)deme tarihi ise 20/07/2026'dır.
Enpara Bank A.. Büyük Mükellefler V.D. 3350917589
"""


def test_enpara_pdfplumber_cid_tokens():
    """pdfplumber (cid:N) token'lı gerçek çıktı doğru parse edilmeli (regresyon)."""
    p = EnparaParser().parse(ENPARA_TEXT_CID)
    assert p.bank_name == "Enpara"
    assert p.last_4 == "1104"
    assert p.credit_limit == Decimal("9000.00")
    assert p.statement_date == date(2026, 6, 10)
    assert p.due_date == date(2026, 6, 22)  # "(cid:7)deme ... 20/07" tuzağına düşmez
    assert p.statement_amount == Decimal("4915.01")


# ─── VakıfBank ─────────────────────────────────────────────────────────────────

VAKIF_TEXT = """Kredi Kartı Hesap Özeti (TL)
VakıfBank Worldcard
Dönem Borcunuz : 17,495.87 TL
Asgari Ödeme Tutarı : 6,999.00 TL
Son Ödeme Tarihi : 25.05.2026
Kart No : 5521********4156
Limitiniz : 320,000.00 TL
Hesap Kesim Tarihi : 15.05.2026
Bir Sonraki Hesap Kesim Tarihi : 15.06.2026
Bir Sonraki Son Ödeme Tarihi : 25.06.2026
17.03.2026 HEPSIPAY /HEPSIBU 2. Taksit 1,084.50 4x1,084.50
25.03.2026 HEPSIPAY /HEPSIBU 2. Taksit 439.00 1x439.00
21.04.2026 PAYCELL/TRENDYOL YEMEK/İSTANBUL 480.00
"""


def test_detect_vakifbank():
    assert isinstance(detect_parser(VAKIF_TEXT), VakifBankParser)


def test_vakifbank_fields():
    p = VakifBankParser().parse(VAKIF_TEXT)
    assert p.bank_name == "VakıfBank"
    assert p.last_4 == "4156"
    assert p.credit_limit == Decimal("320000.00")
    assert p.statement_date == date(2026, 5, 15)
    assert p.due_date == date(2026, 5, 25)  # "Bir Sonraki Son Ödeme" tuzağına düşmez
    assert p.statement_amount == Decimal("17495.87")


def test_vakifbank_installments_net_pattern():
    p = VakifBankParser().parse(VAKIF_TEXT)
    # Yalnız "Nx tutar" desenli 2 taksit yakalanır.
    assert len(p.installments) == 2
    first = p.installments[0]
    assert first.monthly_amount == Decimal("1084.50")
    assert first.installments_paid == 2
    assert first.installments_total == 6  # paid(2) + remaining(4)
    assert first.total_amount == Decimal("6507.00")  # 1084.50 * 6
    # Değişken format uyarısı her zaman eklenir.
    assert any("değişken" in w.lower() for w in p.warnings)


def test_vakifbank_stripped_turkish_chars():
    """Türkçe karakteri düşmüş VakıfBank metni de zorunlu alanları okumalı."""
    p = VakifBankParser().parse(_strip_tr(VAKIF_TEXT))
    assert p.due_date == date(2026, 5, 25)  # "Bir Sonraki Son Ödeme" tuzağına düşmez
    assert p.statement_amount == Decimal("17495.87")
    assert p.last_4 == "4156"


# ─── Fail-safe: yetersiz/tanınmayan içerik ────────────────────────────────────

# Akbank/Axess garbled metni ama yalnızca birkaç karakter — etiket imzaları yok.
# (Tam Akbank ekstresi test_akbank_parser.py'de tanınır; burada eksik içerik.)
INCOMPLETE_GARBLED = "Ò=¢@ ¥@ HK ÖéÁÕ@ hÅÓ¤ÒÁÄÁ ¦ÖãÅÃÈ@ âüÔÅÙ ÔÜ§£@ Õ ô÷øøõôùô"


def test_incomplete_garbled_not_recognized():
    """Etiket imzası yetersiz → hiçbir parser eşleşmez → None (endpoint 422)."""
    assert detect_parser(INCOMPLETE_GARBLED) is None
