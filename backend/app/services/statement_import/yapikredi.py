"""Yapı Kredi World (Platinum) kredi kartı ekstresi parser'i (deterministik).

Yapı Kredi tutarları TR formatında ("2.000,00"), tarihleri **Türkçe ay adıyla**
verir ("5 Haziran 2026"). Taksit satırı "X TL'lik işlemin k / n taksidi" biçiminde
ayrı bir satırdadır; satıcı adı bir önceki işlem satırındadır.

Not (çarpışma): hem Yapı Kredi hem VakıfBank "Worldcard/World" markasını kullanır.
Bu parser `PARSERS` listesinde VakıfBank'tan ÖNCE gelir ve yalnızca Yapı Kredi'ye
özgü imzayla eşleşir ("yapikredi" — www.yapikredi.com.tr; veya "yapı ve kred").
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ._utils import clamp_day, months_back, parse_amount, search_labeled_date
from .base import ParsedInstallment, ParsedStatement

# ReDoS-safe: bounded quantifiers (SonarQube S5852)
_CARD_RE = re.compile(r"Kart Numarası\s{0,4}:?\s{0,4}([\d *]{8,30})")
_LIMIT_RE = re.compile(r"(?<!Müşteri )Kart Limiti\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
# "Dönem Borcu : 2.000,00 TL" — "Önceki Dönem Hesap Özeti Borcu" tuzağına düşmez
# ("Dönem Hesap" araya girer, "Dönem Borcu" bitişik değildir).
_DEBT_RE = re.compile(r"Dönem Borcu\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL")
# Taksit: "12.000,00 TL'lik işlemin 6 / 6 taksidi"
_INSTALLMENT_RE = re.compile(
    r"([\d.,]{1,20})\s{0,4}TL.?lik işlemin\s{0,4}(\d{1,3})\s{0,4}/\s{0,4}(\d{1,3})\s{0,4}taksidi",
    re.IGNORECASE,
)
_LEAD_TR_DATE_RE = re.compile(r"^\d{1,2}\s{1,3}\w{3,9}\s{1,3}\d{4}\s{0,4}")
_TRAIL_AMOUNT_RE = re.compile(r"[+\-]?[\d.,]{1,20}\s{0,4}$")


class YapiKrediParser:
    """Yapı Kredi World ekstresi parser'i (StatementParser uyumlu)."""

    bank_key = "yapikredi"

    def matches(self, text: str) -> bool:
        low = text.lower()
        # "YAPI KREDİ".lower() Türkçe İ→i̇ sorunu nedeniyle "yapı ve kred"
        # (İ'den önce kesilmiş) ile; ayrıca ASCII URL "yapikredi" ile eşleşir.
        return "yapikredi" in low or "yapı ve kred" in low

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
            bank_name="Yapı Kredi",
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
        """Her "X TL'lik işlemin k / n taksidi" satırını ayıkla.

        Satıcı adı bir önceki dolu satırdadır (tarih + tutar temizlenir).
        Son dilim (k>=n, gelecek ödeme yok) atlanır.
        """
        lines = text.splitlines()
        installments: list[ParsedInstallment] = []
        for idx, line in enumerate(lines):
            m = _INSTALLMENT_RE.search(line)
            if not m:
                continue
            try:
                total_amount = parse_amount(m.group(1))
            except InvalidOperation:
                continue
            paid = int(m.group(2))
            total_count = int(m.group(3))
            if total_count < 1 or paid < 1 or paid >= total_count:
                continue  # son dilim / geçersiz → gelecek taksit yok

            desc = "Taksitli işlem"
            for j in range(idx - 1, -1, -1):
                prev = lines[j].strip()
                if prev:
                    desc = prev
                    break
            desc = _LEAD_TR_DATE_RE.sub("", desc)
            desc = _TRAIL_AMOUNT_RE.sub("", desc).strip() or "Taksitli işlem"

            monthly_amount = (total_amount / Decimal(total_count)).quantize(Decimal("0.01"))
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
