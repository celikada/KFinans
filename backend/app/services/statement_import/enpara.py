"""Enpara (Enpara Bank A.Ş.) kredi kartı ekstresi parser'i (deterministik).

Enpara ekstresi tarihleri GG/AA/YYYY (slash), tutarları TR formatında verir.
Bu ekstre tipinde taksitli işlem kolonu var ama örnekte boş; taksit satırı
deterministik bir desenle gelmediği için taksit ayıklanmaz (varsa kullanıcı elle
ekler). Temel kart + ekstre alanları parse edilir.
"""

from __future__ import annotations

import re
from decimal import InvalidOperation

from ._utils import clamp_day, parse_amount, parse_date
from .base import ParsedStatement

# ReDoS-safe: bounded quantifiers (SonarQube S5852)
# "Kart numarası 5269 11** **** 1104" — satır kalanındaki son 4 hane.
_CARD_RE = re.compile(r"Kart numarası\s{0,4}:?\s{0,4}([0-9*\s]{1,40})")
# Büyük K: "Kart limiti" (küçük k'li "Kullanılabilir kart limiti" hariç).
_LIMIT_RE = re.compile(r"(?<!labilir )Kart limiti\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
_STMT_DATE_RE = re.compile(r"Ekstre tarihi\s{0,4}:?\s{0,4}(\d{2}/\d{2}/\d{4})")
_DUE_DATE_RE = re.compile(r"Son ödeme tarihi\s{0,4}:?\s{0,4}(\d{2}/\d{2}/\d{4})")
_DEBT_RE = re.compile(r"Ekstre borcu\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")


class EnparaParser:
    """Enpara kredi kartı ekstresi parser'i (StatementParser uyumlu)."""

    bank_key = "enpara"

    def matches(self, text: str) -> bool:
        return "enpara" in text.lower()

    def parse(self, text: str) -> ParsedStatement:
        warnings: list[str] = []

        stmt_match = _STMT_DATE_RE.search(text)
        if not stmt_match:
            raise ValueError("Ekstre tarihi bulunamadı — ekstre formatı tanınmadı.")
        statement_date = parse_date(stmt_match.group(1))

        due_match = _DUE_DATE_RE.search(text)
        if not due_match:
            raise ValueError("Son ödeme tarihi bulunamadı — ekstre formatı tanınmadı.")
        due_date = parse_date(due_match.group(1))

        debt_match = _DEBT_RE.search(text)
        if not debt_match:
            raise ValueError("Ekstre borcu bulunamadı — ekstre formatı tanınmadı.")
        statement_amount = parse_amount(debt_match.group(1))

        last_4: str | None = None
        card_match = _CARD_RE.search(text)
        if card_match:
            digits = re.findall(r"\d{4}", card_match.group(1))
            if digits:
                last_4 = digits[-1]
        if last_4 is None:
            warnings.append("Kart numarası okunamadı; lütfen elle girin.")

        credit_limit = None
        limit_match = _LIMIT_RE.search(text)
        if limit_match:
            try:
                credit_limit = parse_amount(limit_match.group(1))
            except InvalidOperation:
                warnings.append("Kart limiti okunamadı.")

        return ParsedStatement(
            bank_name="Enpara",
            last_4=last_4,
            credit_limit=credit_limit,
            statement_day=clamp_day(statement_date.day),
            payment_due_day=clamp_day(due_date.day),
            period_year=statement_date.year,
            period_month=statement_date.month,
            statement_amount=statement_amount,
            statement_date=statement_date,
            due_date=due_date,
            installments=[],
            warnings=warnings,
        )
