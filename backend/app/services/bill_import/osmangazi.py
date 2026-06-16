"""Osmangazi Elektrik (Zorlu Enerji) fatura parser'ı.

Bu kurumun "Yazdır" PDF'i **taranmış görüntü** (metin katmanı yok) → endpoint OCR
fallback (`_ocr.ocr_pdf`) ile metne çevirir, sonra bu parser çalışır. OCR gürültülü
olabileceğinden bounded + tolerant regex; bulunamayan alan → ValueError (fail-safe,
kullanıcı elle girer). Tarih `-` ile (10-06-2026); sonraki-tarih faturada yok → türetilir.

Not: text-katmanlı bir e-Arşiv Osmangazi faturası gelirse OCR'a gerek kalmadan da
aynı parser çalışır (detect_parser metin üzerinden dener).
"""

from __future__ import annotations

import re
from decimal import InvalidOperation

from app.services.statement_import._utils import parse_amount

from .base import ParsedBill, add_one_month, parse_flex_date

_SUBSCRIBER_RE = re.compile(r"T[üu]ketici No\s{0,3}:?\s{0,3}(\d+)")
# "ÖDENECEK TUTAR(TL): 477,80" — parantezli birim.
_AMOUNT_RE = re.compile(r"ÖDENECEK TUTAR\s{0,3}\(TL\)\s{0,3}:?\s{0,3}([\d.,]+)")
_BILL_DATE_RE = re.compile(r"FATURA TARİHİ\s{0,3}:?\s{0,3}(\d{1,2}[-./]\d{1,2}[-./]\d{4})")
_DUE_DATE_RE = re.compile(r"SON ÖDEME TARİHİ\s{0,3}:?\s{0,3}(\d{1,2}[-./]\d{1,2}[-./]\d{4})")
_BILL_NO_RE = re.compile(r"Sözleşme Hesap No\s{0,3}:?\s{0,3}(\w+)")


class OsmangaziParser:
    provider_code = "osmangazi_elektrik"

    def matches(self, text: str) -> bool:
        low = text.lower()
        return "osmangazi" in low and "elektrik" in low

    def parse(self, text: str) -> ParsedBill:
        sub_m = _SUBSCRIBER_RE.search(text)
        amt_m = _AMOUNT_RE.search(text)
        bd_m = _BILL_DATE_RE.search(text)
        dd_m = _DUE_DATE_RE.search(text)
        if not (sub_m and amt_m and bd_m and dd_m):
            raise ValueError("Osmangazi faturası beklenen alanlar bulunamadı (OCR/format) — elle girin")
        try:
            amount = parse_amount(amt_m.group(1))
        except InvalidOperation as e:
            raise ValueError(f"Osmangazi tutar ayrıştırılamadı: {amt_m.group(1)!r}") from e
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
            warnings=["OCR ile okundu — tutar ve tarihleri kontrol edin"],
        )
