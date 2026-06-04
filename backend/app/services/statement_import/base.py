"""Kredi karti ekstresi parser arayuzu ve cikti veri yapilari.

Parser motoru pluggable: her banka icin bir `StatementParser` implementasyonu
`PARSERS` listesine eklenir. Ilk asamada yalnizca deterministik (regex tabanli)
parser'lar var; AI/hibrit parser ileride ayni `StatementParser` arayuzunu
implement ederek eklenebilir (bkz. docs/plans faz3 ekstre import Asama 3).

Parse ciktilari ham dataclass'lardir (DB'ye yazilmaz); endpoint bunlari
Pydantic `ParsedStatementOut`'a cevirip kullaniciya onizleme olarak doner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass
class ParsedInstallment:
    """Ekstreden ayiklanmis tek taksit yukumlulugu.

    `installments_paid` ekstrede gorunen "X. taksit" sirasidir (X/Y'deki X);
    commit asamasinda kalan taksit (`installments_remaining`) first_due_date'ten
    yeniden hesaplanir (mevcut `_calc_remaining` ile).
    """

    description: str
    total_amount: Decimal
    monthly_amount: Decimal
    installments_total: int
    installments_paid: int
    first_due_date: date


@dataclass
class ParsedStatement:
    """Bir ekstre PDF'inden ayiklanmis tum veri (kart + ekstre + taksitler)."""

    bank_name: str
    last_4: str | None
    credit_limit: Decimal | None
    statement_day: int
    payment_due_day: int
    period_year: int
    period_month: int
    statement_amount: Decimal
    statement_date: date
    due_date: date
    installments: list[ParsedInstallment] = field(default_factory=list)
    # Parse belirsizlikleri (orn. ayni taksit grubunun birden cok satiri) —
    # kullanici onizlemede gorup duzeltsin diye toplanir.
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class StatementParser(Protocol):
    """Banka-spesifik ekstre parser sozlesmesi.

    `matches(text)` bu parser'in metni isleyip isleyemeyecegini (banka tespiti)
    bildirir; `parse(text)` ham ekstre metnini `ParsedStatement`'a cevirir.
    """

    bank_key: str

    def matches(self, text: str) -> bool: ...

    def parse(self, text: str) -> ParsedStatement: ...
