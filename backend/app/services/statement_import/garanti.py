"""Garanti BBVA (Bonus) kredi kartı ekstresi parser'i (deterministik).

Garanti tutarları TR formatında ("17.176,69"), tarihleri Türkçe ay adıyla
("01 Haziran 2026") ve etiketleri iki-noktasız ("Hesap Kesim Tarihi 01 Haziran 2026")
verir. Taksitli işlemler "k/n" sütunuyla gelebilir; bu sütun bulunamazsa taksit
ayıklanmaz ve kullanıcı uyarılır (fail-safe — tahmini taksit yazılmaz).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ._utils import clamp_day, months_back, parse_amount, search_labeled_date, tr_tolerant
from .base import ParsedInstallment, ParsedStatement

# ReDoS-safe: bounded quantifiers (SonarQube S5852). tr_tolerant: Türkçe harf
# içeren etiketler glyph-düşmüş PDF metninde de eşleşir ("Numarası"→"Numaras" vb).
_CARD_RE = re.compile(tr_tolerant("Kart Numarası") + r"\s{0,4}:?\s{0,4}([\d *]{8,30})")
_LIMIT_RE = re.compile(r"(?<!Müşteri )(?<!Avans )Kart Limiti\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
_DEBT_RE = re.compile(tr_tolerant("Dönem Borcunuz") + r"\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
# Taksitli işlem satırı (best-effort): "... <tutar> k/n" — Garanti işlem tarihleri
# Türkçe ay adıyla olduğundan "/" yalnız taksit sütununda görünür.
_INSTALLMENT_RE = re.compile(r"([\d.,]{1,20})\s{1,4}(\d{1,2})/(\d{1,2})(?:\s|$)")
_LEAD_TR_DATE_RE = re.compile(r"^\d{1,2}\s{1,3}\w{3,9}\s{1,3}\d{4}\s{0,4}")


class GarantiParser:
    """Garanti BBVA (Bonus) ekstresi parser'i (StatementParser uyumlu)."""

    bank_key = "garanti"

    def matches(self, text: str) -> bool:
        low = text.lower()
        return "garanti" in low or "bonusflaş" in low

    def parse(self, text: str) -> ParsedStatement:
        warnings: list[str] = []

        statement_date = search_labeled_date(text, "Hesap Kesim Tarihi", turkish=True)
        if statement_date is None:
            raise ValueError("Hesap kesim tarihi bulunamadı — ekstre formatı tanınmadı.")

        due_date = search_labeled_date(text, "Son Ödeme Tarihi", turkish=True)
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
            bank_name="Garanti BBVA",
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
        """ "<tutar> k/n" desenli taksitleri best-effort ayıkla; son dilim atlanır.

        Garanti ekstre formatı sürüme göre değişebildiğinden, taksit bulunsun
        bulunmasın kullanıcı kontrol için uyarılır.
        """
        installments: list[ParsedInstallment] = []
        for line in text.splitlines():
            # Tarihsiz satırları (özet/footer) ve Türkçe-tarihli işlem satırlarını ele al;
            # yalnız "<tutar> k/n" deseni yakalanır.
            m = _INSTALLMENT_RE.search(line)
            if not m:
                continue
            try:
                monthly_amount = parse_amount(m.group(1))
            except InvalidOperation:
                continue
            if monthly_amount <= 0:
                continue
            paid = int(m.group(2))
            total_count = int(m.group(3))
            if total_count < 1 or paid < 1 or paid >= total_count or total_count > 36:
                continue

            desc = _LEAD_TR_DATE_RE.sub("", line[: m.start()]).strip() or "Taksitli işlem"
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

        warnings.append("Garanti BBVA ekstrelerinde taksit biçimi değişkendir. Otomatik aktarılan taksitleri kontrol edin; okunamayan taksitleri elle ekleyin.")
        return installments
