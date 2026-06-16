"""Vodafone (GSM) e-Arşiv fatura parser'ı.

Metin tabanlı PDF (cid=0; dekoratif glyph blokları zararsız). Sayı **EN formatı**
(1,077.00 → virgül binlik!). Tarihler `.`/`/` karışık. Sonraki fatura + sonraki
son ödeme tarihi faturada açık.
"""

from __future__ import annotations

import re
from decimal import InvalidOperation

from app.services.statement_import._utils import parse_amount, parse_date, search_labeled_date

from .base import ParsedBill

_GSM_RE = re.compile(r"GSM NO:\s*([\d ]+?)\s+Abonelik")
_AMOUNT_RE = re.compile(r"FATURA TUTARI:\s*([\d.,]+)\s*TL")
_BILL_DATE_RE = re.compile(r"Fatura Tarihi:\s*(\d{2}[./]\d{2}[./]\d{4})")
_NEXT_BILL_RE = re.compile(r"BİR SONRAKİ FATURA TARİHİ:\s*(\d{2}[./]\d{2}[./]\d{4})")
_NEXT_DUE_RE = re.compile(r"BİR SONRAKİ SON ÖDEME TARİHİ:\s*(\d{2}[./]\d{2}[./]\d{4})")
_BILL_NO_RE = re.compile(r"Fatura ID:\s*(\S+)")


class VodafoneParser:
    provider_code = "vodafone"

    def matches(self, text: str) -> bool:
        return "vodafone" in text.lower()

    def parse(self, text: str) -> ParsedBill:
        gsm_m = _GSM_RE.search(text)
        amt_m = _AMOUNT_RE.search(text)
        bd_m = _BILL_DATE_RE.search(text)
        # Güncel son ödeme: "BİR SONRAKİ ... SON ÖDEME" tuzağını atla (search_labeled_date).
        # Etiket faturada BÜYÜK harf; regex case-sensitive → büyük harf ver.
        due_date = search_labeled_date(text, "SON ÖDEME TARİHİ")
        if not (gsm_m and amt_m and bd_m and due_date):
            raise ValueError("Vodafone faturası beklenen alanlar bulunamadı (format değişmiş olabilir)")
        try:
            amount = parse_amount(amt_m.group(1))
        except InvalidOperation as e:
            raise ValueError(f"Vodafone tutar ayrıştırılamadı: {amt_m.group(1)!r}") from e
        bill_date = parse_date(bd_m.group(1))
        next_bill_m = _NEXT_BILL_RE.search(text)
        next_due_m = _NEXT_DUE_RE.search(text)
        no_m = _BILL_NO_RE.search(text)
        return ParsedBill(
            provider_code=self.provider_code,
            subscriber_no=gsm_m.group(1).strip(),
            bill_amount=amount,
            currency="TRY",
            bill_date=bill_date,
            due_date=due_date,
            period_year=bill_date.year,
            period_month=bill_date.month,
            next_bill_date=parse_date(next_bill_m.group(1)) if next_bill_m else None,
            next_due_date=parse_date(next_due_m.group(1)) if next_due_m else None,
            bill_no=no_m.group(1) if no_m else None,
        )
