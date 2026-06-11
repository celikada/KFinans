"""ZiraatParser deterministik ekstre parse testleri (saf-metin, pdfplumber'sız).

Örnek Ziraat Bankası Bankkart ekstresinin pdfplumber'ın üreteceğine yakın
metin temsili fixture olarak verilir; parser alan-alan doğrulanır. Format
değişikliği / tanınmama durumlarında fail-safe davranış da test edilir.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.statement_import import detect_parser
from app.services.statement_import.ziraat import ZiraatParser

# pdfplumber çıktısına yakın temsil (iki farklı sayı formatı: başlık TR, taksit EN).
SAMPLE_TEXT = """Sayın O*** Ç*******
5309-####-####-7316 Kart Limiti : 500.000,00 TL
Müşteri Numarası : 5*****91 Kullanılabilir Kart Limiti : 306.882,83 TL
Hesap Kesim Tarihi : 26.05.2026 Sonraki Hesap Kesim Tarihi : 26.06.2026
Son Ödeme Tarihi : 05.06.2026 Sonraki Son Ödeme Tarihi : 06.07.2026
Dönem Borcu TL : 83.558,33 TL
Asgari Ödeme Tutarı TL : 33.423,33 TL
İşlem Tarihi İşlem Açıklaması TL Tutar
04.05.2026 Bankkart 360 Bankkart Lira Kazanımı 0,00
06.05.2026 2066 şube-otomatik ödeme-teşekkür ederiz 243.260,16+
28.04.2026 Kart aidat ücreti 462,00
ÖNCEKİ AYDAN DEVİR 243.281,35
KART NO : 5309-####-####-4638 / O*** Ç*******
27.04.2026 Sonradan Taksit S/ANADOLU HAY 4. Taksit (100000.00 TL İşlemin 4/4 Taksidi) 25.000,00
09.05.2026 09/03 IYZICO/SHOP.HUAWEİ 03.Tak İSTANBUL (15499.00 TL İşlemin 3/3 Taksidi) 5.166,33
"""


def test_detect_parser_recognizes_ziraat():
    assert isinstance(detect_parser(SAMPLE_TEXT), ZiraatParser)


def test_detect_parser_unknown_bank_returns_none():
    assert detect_parser("Rastgele bir metin, banka değil.") is None


def test_parse_card_and_statement_fields():
    parsed = ZiraatParser().parse(SAMPLE_TEXT)
    assert parsed.bank_name == "Ziraat Bankası"
    assert parsed.last_4 == "7316"  # ilk maskeli kart (asıl kart)
    assert parsed.credit_limit == Decimal("500000.00")
    assert parsed.statement_date == date(2026, 5, 26)
    assert parsed.due_date == date(2026, 6, 5)  # "Sonraki Son Ödeme" tuzağına düşmez
    assert parsed.period_year == 2026
    assert parsed.period_month == 5
    assert parsed.statement_amount == Decimal("83558.33")
    assert parsed.statement_day == 26
    assert parsed.payment_due_day == 5


def test_parse_installments():
    parsed = ZiraatParser().parse(SAMPLE_TEXT)
    assert len(parsed.installments) == 2

    anadolu = next(i for i in parsed.installments if "ANADOLU" in i.description)
    assert anadolu.total_amount == Decimal("100000.00")
    assert anadolu.installments_total == 4
    assert anadolu.installments_paid == 4
    assert anadolu.monthly_amount == Decimal("25000.00")
    # 4. taksit Mayıs'ta → ilk taksit 3 ay önce = Şubat 2026
    assert anadolu.first_due_date == date(2026, 2, 1)

    huawei = next(i for i in parsed.installments if "HUAWE" in i.description)
    assert huawei.total_amount == Decimal("15499.00")
    assert huawei.installments_total == 3
    assert huawei.monthly_amount == Decimal("5166.33")  # 15499/3 yuvarlanmış


def test_parse_skips_non_installment_lines():
    """Ödeme / Bankkart Lira / aidat / devir satırları taksit sayılmaz."""
    parsed = ZiraatParser().parse(SAMPLE_TEXT)
    descriptions = " ".join(i.description for i in parsed.installments)
    assert "aidat" not in descriptions.lower()
    assert "devir" not in descriptions.lower()


def test_parse_emits_warning_for_multiple_installments():
    parsed = ZiraatParser().parse(SAMPLE_TEXT)
    assert any("taksit satırı" in w for w in parsed.warnings)


def test_parse_missing_required_field_raises():
    """Format değişmiş / eksik alan → ValueError (fail-safe, tahmin yok)."""
    broken = "Ziraat Bankası ekstresi ama hiçbir tarih/tutar yok."
    with pytest.raises(ValueError):
        ZiraatParser().parse(broken)


def test_parse_stripped_turkish_chars():
    """Glyph-düşmüş metin (Türkçe-özel harf kaybı) zorunlu alanları okumalı.

    Bazı PDF metin katmanları "Ödeme"→"deme", "Dönem"→"Dnem" gibi harf düşürür;
    parser bu durumda da kart + ekstre alanlarını çıkarabilmeli (regresyon).
    """
    stripped = SAMPLE_TEXT.translate({ord(c): None for c in "çÇğĞıİöÖşŞüÜ"})
    parsed = ZiraatParser().parse(stripped)
    assert parsed.last_4 == "7316"
    assert parsed.due_date == date(2026, 6, 5)  # "Sonraki Son Ödeme" tuzağına düşmez
    assert parsed.statement_amount == Decimal("83558.33")
    assert parsed.statement_date == date(2026, 5, 26)


def test_statement_day_clamped_to_28():
    """Kesim günü >28 ise model aralığına (le=28) clamp edilir."""
    text = SAMPLE_TEXT.replace("Hesap Kesim Tarihi : 26.05.2026", "Hesap Kesim Tarihi : 31.05.2026")
    parsed = ZiraatParser().parse(text)
    assert parsed.statement_day == 28
    assert parsed.statement_date == date(2026, 5, 31)  # gerçek tarih korunur
