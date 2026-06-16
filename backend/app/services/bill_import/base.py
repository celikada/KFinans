"""Abonelik faturası (PDF) parser arayüzü + çıktı veri yapısı.

Kredi kartı ekstresi import'u (`statement_import`) ile aynı pluggable desen:
her kurum için bir `BillParser` implementasyonu `PARSERS` listesine eklenir.
Parser'lar saf-metin (pdfplumber'dan bağımsız, test edilebilir) + fail-safe
(beklenen alan yoksa ValueError → endpoint 422; asla tahmini veri yazılmaz).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

_FLEX_DATE_RE = re.compile(r"(\d{1,2})[-./](\d{1,2})[-./](\d{4})")


def parse_flex_date(raw: str) -> date:
    """İlk "GG.AA.YYYY" / "GG/AA/YYYY" / "GG-AA-YYYY" tarihini date'e çevirir.

    `statement_import._utils.parse_date` yalnız `.`/`/` destekler; ESGAZ `-`
    kullandığından bu esnek varyant. Eşleşme yoksa `ValueError`.
    """
    m = _FLEX_DATE_RE.search(raw)
    if not m:
        raise ValueError(f"tarih bulunamadı: {raw!r}")
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def add_one_month(d: date) -> date:
    """Bir sonraki ayın aynı günü (gün taşmasında ay sonuna sıkıştırır)."""
    year = d.year + (1 if d.month == 12 else 0)
    month = 1 if d.month == 12 else d.month + 1
    import calendar

    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last))


@dataclass
class ParsedBill:
    """Bir abonelik faturası PDF'inden ayıklanmış veri (DB'ye yazılmaz; önizleme)."""

    provider_code: str  # esgaz | vodafone | ttnet (kategori PROVIDERS'tan türetilir)
    subscriber_no: str
    bill_amount: Decimal
    currency: str  # bu kurumlar için her zaman TRY
    bill_date: date
    due_date: date
    period_year: int
    period_month: int
    next_bill_date: date | None = None
    next_due_date: date | None = None
    bill_no: str | None = None
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class BillParser(Protocol):
    """Kurum-spesifik fatura parser sözleşmesi."""

    provider_code: str

    def matches(self, text: str) -> bool: ...

    def parse(self, text: str) -> ParsedBill: ...
