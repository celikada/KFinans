"""QNB (QNB Fix / eski Finansbank) kredi kartı ekstresi parser'i (deterministik).

QNB tutarları EN/US formatında ("85,275.04"), hesap kesim tarihi sayısal
("09/05/2026"), son ödeme tarihi ise Türkçe ay adıyla ("20 Mayıs 2026") gelir.
Taksitler işlem satırının sonunda "k/n" sütunundadır
("26/04/2026 SPORLINE OUTLET 1,043.69 1/3 7,457").
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ._utils import clamp_day, months_back, parse_amount, search_labeled_date
from .base import ParsedInstallment, ParsedStatement

# ReDoS-safe: bounded quantifiers (SonarQube S5852)
_CARD_RE = re.compile(r"Kredi Kartı Numarası\s{0,4}:?\s{0,4}([\d *]{8,30})")
# "Kredi Kartı Limiti : 315,000.00 TL" — "Toplam Kredi Kartı Limiti" tuzağını atla.
_LIMIT_RE = re.compile(r"(?<!Toplam )Kredi Kartı Limiti\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
_DEBT_RE = re.compile(r"Dönem Borcu\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
# İşlem satırı taksitli: "DD/MM/YYYY <satıcı> <tutar> k/n [parapuan]"
_INSTALLMENT_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s{1,4}(.+?)\s{1,4}(-?[\d.,]{1,20})\s{1,4}(\d{1,2})/(\d{1,2})(?:\s|$)")


class QnbParser:
    """QNB Fix ekstresi parser'i (StatementParser uyumlu)."""

    bank_key = "qnb"

    def matches(self, text: str) -> bool:
        low = text.lower()
        return "qnb" in low or "qnbcard" in low

    def parse(self, text: str) -> ParsedStatement:
        warnings: list[str] = []

        statement_date = search_labeled_date(text, "Hesap Kesim Tarihi", turkish=False)
        if statement_date is None:
            raise ValueError("Hesap kesim tarihi bulunamadı — ekstre formatı tanınmadı.")

        # QNB son ödeme tarihini Türkçe ay adıyla yazar ("20 Mayıs 2026").
        due_date = search_labeled_date(text, "Son Ödeme Tarihi", turkish=True)
        if due_date is None:
            due_date = search_labeled_date(text, "Son Ödeme Tarihi", turkish=False)
        if due_date is None:
            raise ValueError("Son ödeme tarihi bulunamadı — ekstre formatı tanınmadı.")

        debt_match = _DEBT_RE.search(text)
        if not debt_match:
            raise ValueError("Dönem borcu bulunamadı — ekstre formatı tanınmadı.")
        statement_amount = parse_amount(debt_match.group(1))

        last_4 = self._last_4(text, warnings)
        credit_limit = self._limit(text, warnings)
        installments = self._parse_installments(text, statement_date, warnings)

        return ParsedStatement(
            bank_name="QNB",
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
        """İşlem satırlarındaki "k/n" taksitleri ayıkla.

        Tutar bu ayın taksit dilimidir (monthly). İade/düzeltme (negatif tutar)
        ve son dilim (k>=n, gelecek ödeme yok) atlanır.
        """
        installments: list[ParsedInstallment] = []
        for line in text.splitlines():
            m = _INSTALLMENT_RE.search(line)
            if not m:
                continue
            try:
                monthly_amount = parse_amount(m.group(3))
            except InvalidOperation:
                continue
            if monthly_amount <= 0:
                continue  # iade / düzeltme satırı
            paid = int(m.group(4))
            total_count = int(m.group(5))
            if total_count < 1 or paid < 1 or paid >= total_count:
                continue

            desc = m.group(2).strip() or "Taksitli işlem"
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

        if len(installments) > 1:
            warnings.append(f"{len(installments)} taksit satırı bulundu; kaydetmeden önce listeyi kontrol edip gereksiz olanları silin.")
        return installments
