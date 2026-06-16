"""ESGAZ (Eskişehir doğalgaz) e-Arşiv fatura parser'ı.

Metin tabanlı PDF (pdfplumber cid=0). Sayı TR formatı (1.004,00). Tarih `-` ile
(08-06-2026). Sonraki-fatura tarihi faturada YOK → bill_date + 1 ay türetilir.
"""

from __future__ import annotations

import re
from decimal import InvalidOperation

from app.services.statement_import._utils import parse_amount

from .base import ParsedBill, add_one_month, parse_flex_date

_SUBSCRIBER_RE = re.compile(r"Hesap No:\s*(\d+)")
_AMOUNT_RE = re.compile(r"Ödenecek Tutar\s*:?\s*([\d.,]+)\s*T[LR]")
_BILL_DATE_RE = re.compile(r"Fatura Tarihi\s*:?\s*(\d{1,2}[-./]\d{1,2}[-./]\d{4})")
_DUE_DATE_RE = re.compile(r"Son Ödeme Tarihi\s*:?\s*(\d{1,2}[-./]\d{1,2}[-./]\d{4})")
_BILL_NO_RE = re.compile(r"Fatura No\s*:?\s*(\S+)")


class EsgazParser:
    provider_code = "esgaz"

    def matches(self, text: str) -> bool:
        low = text.lower()
        return "esgaz" in low and "doğalgaz" in low

    def parse(self, text: str) -> ParsedBill:
        sub_m = _SUBSCRIBER_RE.search(text)
        amt_m = _AMOUNT_RE.search(text)
        bd_m = _BILL_DATE_RE.search(text)
        dd_m = _DUE_DATE_RE.search(text)
        if not (sub_m and amt_m and bd_m and dd_m):
            raise ValueError("ESGAZ faturası beklenen alanlar bulunamadı (format değişmiş olabilir)")
        try:
            amount = parse_amount(amt_m.group(1))
        except InvalidOperation as e:
            raise ValueError(f"ESGAZ tutar ayrıştırılamadı: {amt_m.group(1)!r}") from e
        bill_date = parse_flex_date(bd_m.group(1))
        due_date = parse_flex_date(dd_m.group(1))
        no_m = _BILL_NO_RE.search(text)
        return ParsedBill(
            provider_code=self.provider_code,
            subscriber_no=sub_m.group(1),
            bill_amount=amount,
            currency="TRY",
            bill_date=bill_date,
            due_date=due_date,
            period_year=bill_date.year,
            period_month=bill_date.month,
            next_bill_date=add_one_month(bill_date),
            next_due_date=add_one_month(due_date),
            bill_no=no_m.group(1) if no_m else None,
        )
