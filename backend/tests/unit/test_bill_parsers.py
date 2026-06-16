"""Abonelik faturası PDF parser birim testleri (anonimleştirilmiş metin fixture'ları).

Fixture'lar gerçek pdfplumber çıktısının yapısını birebir taşır; PII (isim/no)
sahte değerlerle değiştirilmiştir.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.bill_import import detect_parser

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "bills"


def _text(name: str) -> str:
    return (_FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


def test_esgaz_parser():
    p = detect_parser(_text("esgaz"))
    assert p is not None and p.provider_code == "esgaz"
    b = p.parse(_text("esgaz"))
    assert b.subscriber_no == "1234567890"
    assert b.bill_amount == Decimal("1004.00")
    assert b.currency == "TRY"
    assert b.bill_date == date(2026, 6, 8)
    assert b.due_date == date(2026, 6, 18)
    assert (b.period_year, b.period_month) == (2026, 6)
    # ESGAZ'da sonraki tarih yok → bill_date/due_date + 1 ay türetilir
    assert b.next_bill_date == date(2026, 7, 8)
    assert b.next_due_date == date(2026, 7, 18)
    assert b.bill_no == "EAN2026000000000"


def test_vodafone_parser_en_number_format():
    p = detect_parser(_text("vodafone"))
    assert p is not None and p.provider_code == "vodafone"
    b = p.parse(_text("vodafone"))
    assert b.subscriber_no == "500 000 00 00"
    # EN format (1,077.00 → 1077.00) doğru ayrıştırılmalı
    assert b.bill_amount == Decimal("1077.00")
    assert b.bill_date == date(2026, 6, 6)
    # Güncel son ödeme "BİR SONRAKİ" tuzağına düşmemeli
    assert b.due_date == date(2026, 6, 22)
    assert b.next_bill_date == date(2026, 7, 7)
    assert b.next_due_date == date(2026, 7, 20)


def test_ttnet_parser():
    p = detect_parser(_text("ttnet"))
    assert p is not None and p.provider_code == "ttnet"
    b = p.parse(_text("ttnet"))
    assert b.subscriber_no == "7000000000"
    assert b.bill_amount == Decimal("1339.25")
    assert b.bill_date == date(2026, 6, 14)
    assert b.due_date == date(2026, 7, 1)  # "Bir Sonraki Son Ödeme" değil
    assert b.next_bill_date == date(2026, 7, 14)
    assert b.next_due_date == date(2026, 8, 3)


def test_detect_unknown_returns_none():
    assert detect_parser("Rastgele bir metin, fatura değil") is None


def test_parse_missing_fields_raises():
    """Kurum eşleşir ama alanlar yoksa ValueError (fail-safe)."""
    p = detect_parser("ESGAZ DOĞALGAZ faturası ama hiçbir alan yok")
    assert p is not None
    with pytest.raises(ValueError):
        p.parse("ESGAZ DOĞALGAZ faturası ama hiçbir alan yok")
