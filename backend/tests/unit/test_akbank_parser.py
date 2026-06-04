"""Akbank Axess ekstre parser'i — pdfplumber glyph (cid) çözümü + format-bazlı çıkarım.

pdfplumber Axess PDF'lerinin metnini `(cid:NNN)` token'ları + dağınık Latin
karakter olarak verir. `_decode` rakam + finansal sembolleri çözer; `_extract`
cid'den bağımsız format işaretleriyle (maskeli kart + dönem aralığı) alanları
çıkarır. Fixture'lar gerçek Axess PDF'lerinin pdfplumber çıktısından alınmıştır.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.statement_import import detect_parser
from app.services.statement_import.akbank import AkbankParser, _decode

# ─── _decode: glyph → rakam/sembol/tarih ──────────────────────────────────────


def test_decode_amount_tr():
    # "1.704,50": æ=1, k=binlik nokta, (cid:247/240/244)=7/0/4, K=ondalık virgül, ı=5
    assert _decode("æk(cid:247)(cid:240)(cid:244)Kı(cid:240)") == "1.704,50"


def test_decode_limit():
    assert _decode("ı(cid:240)(cid:240)k(cid:240)(cid:240)(cid:240)K(cid:240)(cid:240)") == "500.000,00"


def test_decode_date():
    assert _decode("(cid:240)(cid:242)a(cid:240)(cid:246)a(cid:242)(cid:240)(cid:242)(cid:246)") == "02/06/2026"


def test_decode_customer_no_latin_digits():
    # 47885494: (cid:244)=4 (cid:247)=7 ł=8 ł=8 ı=5 (cid:244)=4 ø=9 (cid:244)=4
    assert _decode("(cid:244)(cid:247)łłı(cid:244)ø(cid:244)") == "47885494"


def test_decode_preserves_unknown_glyphs():
    # 240-249 dışı cid'ler (harf glyph) korunur (etiketler decode edilmez).
    assert "(cid:133)" in _decode("(cid:133)abc")


# ─── _extract: decode edilmiş düz metinden alanlar ────────────────────────────

# Gerçek ekstrenin decode edilmiş (okunur) hali — sıra: kart, dönem borcu,
# son ödeme (ilk tarih), ekstre dönemi aralığı (sonu = hesap kesim), limit.
DECODED = (
    "5218@07**@****@6072\n"
    "1.704,50\n"
    "02/06/2026\n"
    "25/04/2026‘23/05/2026\n"
    "23/06/2026\n"  # bir sonraki hesap kesim (tuzak)
    "500.000,00\n"
    "498.145,50\n"  # kullanılabilir limit (< kart limiti)
)


def test_extract_fields():
    p = AkbankParser()._extract(DECODED)
    assert p.bank_name == "Akbank"
    assert p.last_4 == "6072"
    assert p.statement_date == date(2026, 5, 23)  # dönem aralığı sonu = hesap kesim
    assert p.due_date == date(2026, 6, 2)  # ilk tarih = son ödeme
    assert p.statement_amount == Decimal("1704.50")  # ilk tutar = dönem borcu
    assert p.credit_limit == Decimal("500000.00")  # en büyük tutar = kart limiti
    assert p.period_year == 2026
    assert p.period_month == 5
    assert p.statement_day == 23
    assert p.payment_due_day == 2
    assert p.installments == []


def test_extract_warns_about_decode():
    p = AkbankParser()._extract(DECODED)
    assert any("çözüld" in w.lower() for w in p.warnings)


def test_extract_changed_format_raises():
    """Maskeli kart / dönem aralığı yoksa fail-safe ValueError (kayıt yok)."""
    with pytest.raises(ValueError):
        AkbankParser()._extract("rastgele metin, kart yok tarih aralığı yok")


# ─── detect_parser: cid'li ham metin ──────────────────────────────────────────

# Ham (decode öncesi) — maskeli kart + dönem aralığı içerir → AkbankParser.
RAW_MIN = (
    "ı(cid:242)æł@(cid:240)(cid:247)\\\\@\\\\\\\\@(cid:246)(cid:240)(cid:247)(cid:242)\n"
    "(cid:242)ıa(cid:240)(cid:244)a(cid:242)(cid:240)(cid:242)(cid:246)‘(cid:242)(cid:243)a(cid:240)ıa(cid:242)(cid:240)(cid:242)(cid:246)\n"
)


def test_detect_akbank_from_raw():
    assert isinstance(detect_parser(RAW_MIN), AkbankParser)
