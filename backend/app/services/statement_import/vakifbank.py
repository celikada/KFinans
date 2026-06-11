"""VakıfBank Worldcard kredi kartı ekstresi parser'i (deterministik).

VakıfBank tutarları EN/US formatında ("17,495.87"), tarihleri GG.AA.YYYY verir.
Taksit satırları çok değişken formatlıdır ("4x1,084.50", "543.99 12", "1,235.00 26");
yalnızca net "Nx tutar" deseni güvenle ayıklanır, gerisi için kullanıcı uyarılır
(kararla: yapılabileni yap, belirsizde uyar, kalanı elle eklenebilsin).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ._utils import clamp_day, months_back, parse_amount, tr_tolerant
from .base import ParsedInstallment, ParsedStatement

# ReDoS-safe: bounded quantifiers (SonarQube S5852). tr_tolerant: Türkçe harf
# içeren etiketler glyph-düşmüş PDF metninde de eşleşir ("Ödeme"→"deme" vb).
_CARD_RE = re.compile(r"Kart No\s{0,4}:?\s{0,4}([0-9*]{1,40})")
_LIMIT_RE = re.compile(r"Limitiniz\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
_STMT_DATE_RE = re.compile(r"(?<!Sonraki )Hesap Kesim Tarihi\s{0,4}:?\s{0,4}(\d{2})\.(\d{2})\.(\d{4})")
_DUE_DATE_RE = re.compile(r"(?<!Sonraki )" + tr_tolerant("Son Ödeme Tarihi") + r"\s{0,4}:?\s{0,4}(\d{2})\.(\d{2})\.(\d{4})")
_DEBT_RE = re.compile(tr_tolerant("Dönem Borcunuz") + r"\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
# Net taksit deseni: "4x1,084.50" → kalan 4 taksit, aylık 1.084,50.
_INSTALLMENT_RE = re.compile(r"(\d{1,3})\s{0,4}x\s{0,4}([\d.,]{1,20})")
# Açıklamadaki "2. Taksit" → bu işlemin kaçıncı taksiti.
_PAID_RE = re.compile(r"(\d{1,3})\.\s{0,4}Taksit")


class VakifBankParser:
    """VakıfBank Worldcard ekstresi parser'i (StatementParser uyumlu)."""

    bank_key = "vakifbank"

    def matches(self, text: str) -> bool:
        low = text.lower()
        return "vakıfbank" in low or "worldcard" in low

    def parse(self, text: str) -> ParsedStatement:
        warnings: list[str] = []

        stmt_match = _STMT_DATE_RE.search(text)
        if not stmt_match:
            raise ValueError("Hesap kesim tarihi bulunamadı — ekstre formatı tanınmadı.")
        statement_date = date(int(stmt_match.group(3)), int(stmt_match.group(2)), int(stmt_match.group(1)))

        due_match = _DUE_DATE_RE.search(text)
        if not due_match:
            raise ValueError("Son ödeme tarihi bulunamadı — ekstre formatı tanınmadı.")
        due_date = date(int(due_match.group(3)), int(due_match.group(2)), int(due_match.group(1)))

        debt_match = _DEBT_RE.search(text)
        if not debt_match:
            raise ValueError("Dönem borcu bulunamadı — ekstre formatı tanınmadı.")
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

        installments = self._parse_installments(text, statement_date, warnings)

        return ParsedStatement(
            bank_name="VakıfBank",
            last_4=last_4,
            credit_limit=credit_limit,
            statement_day=clamp_day(statement_date.day),
            payment_due_day=clamp_day(due_date.day),
            period_year=statement_date.year,
            period_month=statement_date.month,
            statement_amount=statement_amount,
            statement_date=statement_date,
            due_date=due_date,
            installments=installments,
            warnings=warnings,
        )

    def _parse_installments(self, text, statement_date, warnings):
        """Yalnız net "Nx tutar" desenli taksitleri ayıkla; varsa uyarı ekle."""
        installments: list[ParsedInstallment] = []
        for line in text.splitlines():
            m = _INSTALLMENT_RE.search(line)
            if not m:
                continue
            try:
                monthly_amount = parse_amount(m.group(2))
            except InvalidOperation:
                continue
            remaining = int(m.group(1))
            if remaining < 1:
                continue
            paid_m = _PAID_RE.search(line)
            paid = int(paid_m.group(1)) if paid_m else 1
            total_count = paid + remaining

            desc = re.sub(r"^\d{2}[./]\d{2}[./]\d{4}\s{0,4}", "", line)
            desc = _INSTALLMENT_RE.sub("", desc)
            desc = _PAID_RE.sub("", desc)
            desc = re.sub(r"[\d.,]{1,20}\s{0,4}$", "", desc).strip() or "Taksitli işlem"

            fy, fm = months_back(statement_date.year, statement_date.month, paid - 1)
            installments.append(
                ParsedInstallment(
                    description=f"{desc} ({paid}/{total_count})"[:200],
                    total_amount=(monthly_amount * Decimal(total_count)).quantize(Decimal("0.01")),
                    monthly_amount=monthly_amount,
                    installments_total=total_count,
                    installments_paid=paid,
                    first_due_date=date(fy, fm, 1),
                )
            )

        warnings.append(
            "VakıfBank ekstresinde taksit satırları değişken formatlıdır. Otomatik "
            "aktarılan taksitleri kaydetmeden kontrol edin; okunamayan taksitleri elle ekleyin."
        )
        return installments
