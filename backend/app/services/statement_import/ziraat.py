"""Ziraat Bankasi Bankkart kredi karti ekstresi parser'i (deterministik).

Saf-metin uzerinde calisir (pdfplumber'dan bagimsiz) — boylece unit test'te
ornek ekstre metni fixture string olarak verilip parse dogrulanabilir.

Ekstrede iki farkli sayi formati bir arada bulunur:
- Satir/baslik tutarlari TR formatinda: "500.000,00" (nokta binlik, virgul ondalik).
- Taksit parantezindeki toplam tutar EN formatinda: "100000.00" (nokta ondalik).
Bu yuzden iki ayri parse helper'i var.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ._utils import clamp_day, months_back, parse_amount, tr_tolerant
from .base import ParsedInstallment, ParsedStatement

# ReDoS-safe: bounded quantifiers (SonarQube S5852). tr_tolerant: Türkçe harf
# içeren etiketler glyph-düşmüş PDF metninde de eşleşir ("Ödeme"→"deme" vb).
# Maskeli kart numarasi: "5309-####-####-7316" -> son 4 hane (7316).
_CARD_RE = re.compile(r"\d{4}-[\d#*]{4}-[\d#*]{4}-(\d{4})")
_LIMIT_RE = re.compile(r"Kart Limiti\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL", re.IGNORECASE)
# "Hesap Kesim Tarihi : 26.05.2026" — "Sonraki Hesap Kesim Tarihi" haric tutulur.
_STMT_DATE_RE = re.compile(r"(?<!Sonraki )Hesap Kesim Tarihi\s{0,4}:?\s{0,4}(\d{2})\.(\d{2})\.(\d{4})")
_DUE_DATE_RE = re.compile(r"(?<!Sonraki )" + tr_tolerant("Son Ödeme Tarihi") + r"\s{0,4}:?\s{0,4}(\d{2})\.(\d{2})\.(\d{4})")
_DEBT_RE = re.compile(tr_tolerant("Dönem Borcu TL") + r"\s{0,4}:?\s{0,4}([\d.,]{1,20})\s{0,4}TL", re.IGNORECASE)
# Taksit satiri: "... (100000.00 TL İşlemin 4/4 Taksidi) ..." + onundeki aciklama.
_INSTALLMENT_RE = re.compile(
    r"\(([\d.]{1,20})\s{0,4}TL\s{0,4}İşlemin\s{0,4}(\d{1,3})\s{0,4}/\s{0,4}(\d{1,3})\s{0,4}Taksidi\)",
    re.IGNORECASE,
)


class ZiraatParser:
    """Ziraat Bankasi Bankkart ekstresi parser'i (StatementParser uyumlu)."""

    bank_key = "ziraat"

    def matches(self, text: str) -> bool:
        lowered = text.lower()
        return "ziraat" in lowered or "bankkart" in lowered

    def parse(self, text: str) -> ParsedStatement:
        warnings: list[str] = []

        # --- Kart numarasi (ilk maskeli kart = asil kart) ---
        card_match = _CARD_RE.search(text)
        last_4 = card_match.group(1) if card_match else None
        if last_4 is None:
            warnings.append("Kart numarası okunamadı; lütfen elle girin.")

        # --- Kart limiti ---
        credit_limit: Decimal | None = None
        limit_match = _LIMIT_RE.search(text)
        if limit_match:
            try:
                credit_limit = parse_amount(limit_match.group(1))
            except InvalidOperation:
                warnings.append("Kart limiti okunamadı.")

        # --- Hesap kesim tarihi (zorunlu) ---
        stmt_match = _STMT_DATE_RE.search(text)
        if not stmt_match:
            raise ValueError("Hesap kesim tarihi bulunamadı — ekstre formatı tanınmadı.")
        statement_date = date(int(stmt_match.group(3)), int(stmt_match.group(2)), int(stmt_match.group(1)))

        # --- Son ödeme tarihi (zorunlu) ---
        due_match = _DUE_DATE_RE.search(text)
        if not due_match:
            raise ValueError("Son ödeme tarihi bulunamadı — ekstre formatı tanınmadı.")
        due_date = date(int(due_match.group(3)), int(due_match.group(2)), int(due_match.group(1)))

        # --- Dönem borcu (zorunlu) ---
        debt_match = _DEBT_RE.search(text)
        if not debt_match:
            raise ValueError("Dönem borcu bulunamadı — ekstre formatı tanınmadı.")
        statement_amount = parse_amount(debt_match.group(1))

        # statement_day / payment_due_day: model 1-28 araligi (le=28) — clamp.
        statement_day = clamp_day(statement_date.day)
        payment_due_day = clamp_day(due_date.day)

        installments = self._parse_installments(text, statement_date, warnings)

        return ParsedStatement(
            bank_name="Ziraat Bankası",
            last_4=last_4,
            credit_limit=credit_limit,
            statement_day=statement_day,
            payment_due_day=payment_due_day,
            period_year=statement_date.year,
            period_month=statement_date.month,
            statement_amount=statement_amount,
            statement_date=statement_date,
            due_date=due_date,
            installments=installments,
            warnings=warnings,
        )

    def _parse_installments(
        self,
        text: str,
        statement_date: date,
        warnings: list[str],
    ) -> list[ParsedInstallment]:
        """Taksitli işlem satırlarını ayıkla.

        Her "İşlemin X/Y Taksidi" eşleşmesi ayrı bir taksit kaydı olur.
        Aynı işlemin farklı ay satırları (ör. 2/4 ve 3/4) veya aynı tutarlı
        ayrı poliçeler deterministik olarak ayırt edilemediği için hepsi ayrı
        tutulur ve toplu bir uyarı eklenir — kullanıcı önizlemede düzeltir.
        """
        installments: list[ParsedInstallment] = []
        for line in text.splitlines():
            m = _INSTALLMENT_RE.search(line)
            if not m:
                continue
            try:
                total_amount = parse_amount(m.group(1))
            except InvalidOperation:
                continue
            installments_paid = int(m.group(2))
            installments_total = int(m.group(3))
            if installments_total < 1 or installments_paid < 1:
                continue

            # monthly = toplam / taksit sayısı (satır hizalamasına bağlı değil).
            monthly_amount = (total_amount / Decimal(installments_total)).quantize(Decimal("0.01"))

            # Açıklama: parantezden önceki kısımdan tarih ve "Sonradan Taksit"
            # etiketini temizle; kalan işlem adı (ör. "S/ANADOLU HAY").
            prefix = line[: m.start()].strip()
            prefix = re.sub(r"^\d{2}\.\d{2}\.\d{4}\s{0,4}", "", prefix)
            prefix = re.sub(r"Sonradan Taksit\s{0,4}", "", prefix, flags=re.IGNORECASE).strip()
            desc = prefix or "Taksitli işlem"
            description = f"{desc} ({installments_paid}/{installments_total})"[:200]

            # İlk taksit ayı = ekstre dönemi - (paid - 1) ay (gün = 1).
            fy, fm = months_back(statement_date.year, statement_date.month, installments_paid - 1)
            first_due_date = date(fy, fm, 1)

            installments.append(
                ParsedInstallment(
                    description=description,
                    total_amount=total_amount,
                    monthly_amount=monthly_amount,
                    installments_total=installments_total,
                    installments_paid=installments_paid,
                    first_due_date=first_due_date,
                )
            )

        if len(installments) > 1:
            warnings.append(
                f"{len(installments)} taksit satırı bulundu. Aynı işlemin farklı ay "
                "satırları ya da aynı tutarlı ayrı poliçeler olabilir; kaydetmeden "
                "önce listeyi kontrol edip gereksiz olanları silin."
            )
        return installments
