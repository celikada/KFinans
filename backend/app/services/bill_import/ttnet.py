"""TTNET / Türk Telekom (internet) e-Arşiv fatura parser'ı.

Metin tabanlı PDF (cid=0). Sayı TR formatı (1.339,25). Tarihler `/` ile. Sonraki
fatura düzenleme + sonraki son ödeme tarihi faturada açık.
"""

from __future__ import annotations

import re
from decimal import InvalidOperation

from app.services.statement_import._utils import parse_amount, parse_date, search_labeled_date

from .base import ParsedBill

_ACCOUNT_RE = re.compile(r"HESAP NUMARASI\s{0,3}:?\s{0,3}(\d+)")
_AMOUNT_RE = re.compile(r"ÖDENECEK TUTAR\s{0,3}:?\s{0,3}([\d.,]+)\s{0,3}TL")
_BILL_DATE_RE = re.compile(r"FATURA TARİHİ\s{0,3}:?\s{0,3}(\d{2}/\d{2}/\d{4})")
_NEXT_BILL_RE = re.compile(r"Bir Sonraki Fatura Düzenleme Tarihi\s{0,3}:?\s{0,3}(\d{2}/\d{2}/\d{4})")
_NEXT_DUE_RE = re.compile(r"Bir Sonraki Son Ödeme Tarihi\s{0,3}:?\s{0,3}(\d{2}/\d{2}/\d{4})")
_BILL_NO_RE = re.compile(r"FATURA NO\s{0,3}:?\s{0,3}(\d+)")


class TtnetParser:
    provider_code = "ttnet"

    def matches(self, text: str) -> bool:
        low = text.lower()
        return "ttnet" in low or "türk telekom" in low or "turk telekom" in low

    def parse(self, text: str) -> ParsedBill:
        acc_m = _ACCOUNT_RE.search(text)
        amt_m = _AMOUNT_RE.search(text)
        bd_m = _BILL_DATE_RE.search(text)
        # Güncel son ödeme: "Bir Sonraki Son Ödeme" tuzağını atla.
        # Güncel etiket faturada BÜYÜK harf ("SON ÖDEME TARİHİ"); sonraki etiket
        # mixed-case ("Bir Sonraki Son Ödeme Tarihi") → büyük-harf etiket ikisini ayırır.
        due_date = search_labeled_date(text, "SON ÖDEME TARİHİ")
        if not (acc_m and amt_m and bd_m and due_date):
            raise ValueError("TTNET faturası beklenen alanlar bulunamadı (format değişmiş olabilir)")
        try:
            amount = parse_amount(amt_m.group(1))
        except InvalidOperation as e:
            raise ValueError(f"TTNET tutar ayrıştırılamadı: {amt_m.group(1)!r}") from e
        bill_date = parse_date(bd_m.group(1))
        next_bill_m = _NEXT_BILL_RE.search(text)
        next_due_m = _NEXT_DUE_RE.search(text)
        no_m = _BILL_NO_RE.search(text)
        return ParsedBill(
            provider_code=self.provider_code,
            subscriber_no=acc_m.group(1),
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
