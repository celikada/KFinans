"""İş Bankası (Maximum) kredi kartı ekstresi parser'i (deterministik).

İş Bankası tutarları TR formatında ("14.589,28"), tarihleri sayısal
("05.06.2026") verir. Dönem borcu etiketi "Hesap Özeti Borcu"dur. Taksitler
işlem satırının sonunda bitişik "k/ntaksidi(toplam)" biçimindedir
("WWW.TRENDYOL.COMISTANBULTR 1.537,86 3/3taksidi(4.613,60)").
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ._utils import clamp_day, months_back, parse_amount, search_labeled_date, tr_tolerant
from .base import ParsedInstallment, ParsedStatement

# ReDoS-safe: bounded quantifiers (SonarQube S5852). tr_tolerant: Türkçe harf
# içeren etiketler glyph-düşmüş PDF metninde de eşleşir ("Özeti"→"zeti" vb).
_CARD_RE = re.compile(tr_tolerant("Kart Numarası") + r"\s{0,4}:?\s{0,4}([\d *]{8,30})")
# "Toplam Kart Limiti: 195.090,00 TL" — "Toplam Kullanılabilir Kart Limiti" ile
# çakışmaz ("Toplam Kart" bitişik değildir orada).
_LIMIT_RE = re.compile(r"Toplam Kart Limiti\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
_DEBT_RE = re.compile(tr_tolerant("Hesap Özeti Borcu") + r"\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
# Taksit: "<aylık tutar> k/ntaksidi(<toplam>)" (PDF metninde bitişik).
_INSTALLMENT_RE = re.compile(
    r"(-?[\d.,]{1,20})\s{1,4}(\d{1,2})\s{0,2}/\s{0,2}(\d{1,2})\s{0,2}taksidi\s{0,2}\(([\d.,]{1,20})\)",
    re.IGNORECASE,
)
_LEAD_NUM_DATE_RE = re.compile(r"^\d{2}[./]\d{2}[./]\d{4}\s{0,4}")


class IsbankParser:
    """İş Bankası Maximum ekstresi parser'i (StatementParser uyumlu)."""

    bank_key = "isbank"

    def matches(self, text: str) -> bool:
        low = text.lower()
        return "maximum" in low or "maxipuan" in low or "isbank.com" in low

    def parse(self, text: str) -> ParsedStatement:
        warnings: list[str] = []

        statement_date = search_labeled_date(text, "Hesap Kesim Tarihi", turkish=False)
        if statement_date is None:
            raise ValueError("Hesap kesim tarihi bulunamadı — ekstre formatı tanınmadı.")

        due_date = search_labeled_date(text, "Son Ödeme Tarihi", turkish=False)
        if due_date is None:
            raise ValueError("Son ödeme tarihi bulunamadı — ekstre formatı tanınmadı.")

        debt_match = _DEBT_RE.search(text)
        if not debt_match:
            raise ValueError("Hesap özeti borcu bulunamadı — ekstre formatı tanınmadı.")
        statement_amount = parse_amount(debt_match.group(1))

        last_4 = self._last_4(text, warnings)
        credit_limit = self._limit(text, warnings)
        installments = self._parse_installments(text, statement_date, warnings)

        return ParsedStatement(
            bank_name="İş Bankası",
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

    def _last_4(self, text: str, warnings: list[str]) -> str | None:
        m = _CARD_RE.search(text)
        if m:
            digits = re.findall(r"\d{4}", m.group(1))
            if digits:
                return digits[-1]
        warnings.append("Kart numarası okunamadı; lütfen elle girin.")
        return None

    def _limit(self, text: str, warnings: list[str]) -> Decimal | None:
        m = _LIMIT_RE.search(text)
        if not m:
            return None
        try:
            return parse_amount(m.group(1))
        except InvalidOperation:
            warnings.append("Kart limiti okunamadı.")
            return None

    def _parse_installments(self, text, statement_date, warnings):
        """ "k/ntaksidi(toplam)" taksitlerini ayıkla.

        İlk tutar bu ayın dilimi (monthly), parantezdeki toplam alışveriş tutarı.
        İade (negatif) ve son dilim (k>=n) atlanır.
        """
        installments: list[ParsedInstallment] = []
        for line in text.splitlines():
            m = _INSTALLMENT_RE.search(line)
            if not m:
                continue
            try:
                monthly_amount = parse_amount(m.group(1))
                total_amount = parse_amount(m.group(4))
            except InvalidOperation:
                continue
            if monthly_amount <= 0:
                continue  # iade satırı
            paid = int(m.group(2))
            total_count = int(m.group(3))
            if total_count < 1 or paid < 1 or paid >= total_count:
                continue

            desc = _LEAD_NUM_DATE_RE.sub("", line[: m.start()]).strip() or "Taksitli işlem"
            fy, fm = months_back(statement_date.year, statement_date.month, paid - 1)
            installments.append(
                ParsedInstallment(
                    description=f"{desc} ({paid}/{total_count})"[:200],
                    total_amount=total_amount,
                    monthly_amount=monthly_amount,
                    installments_total=total_count,
                    installments_paid=paid,
                    first_due_date=date(fy, fm, 1),
                )
            )

        if len(installments) > 1:
            warnings.append(f"{len(installments)} taksit satırı bulundu; kaydetmeden önce listeyi kontrol edip gereksiz olanları silin.")
        return installments
