"""Ekstre parser'ları için ortak yardımcılar: sayı/tarih ayrıştırma.

Türk banka ekstreleri iki farklı sayı formatı kullanır:
- TR: "500.000,00" (nokta binlik, virgül ondalık) — Ziraat, Enpara
- EN/US: "17,495.87" (virgül binlik, nokta ondalık) — VakıfBank, Axess
`parse_amount` son görülen ayraçtan ondalık ayracını tespit eder, ikisini de
otomatik çözer.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_AMOUNT_CLEAN_RE = re.compile(r"[^\d.,-]")
# Tarih: gün ve ay 2 hane, ayraç nokta veya slash (26.05.2026 / 10/05/2026).
_DATE_RE = re.compile(r"(\d{2})[./](\d{2})[./](\d{4})")


def parse_amount(raw: str) -> Decimal:
    """TR veya EN formatlı para tutarını Decimal'e çevirir (otomatik tespit).

    Örnekler: "500.000,00" -> 500000.00, "17,495.87" -> 17495.87,
    "100000.00" -> 100000.00, "1.442,25" -> 1442.25.
    Geçersiz girdi `InvalidOperation` (Decimal) fırlatır.
    """
    cleaned = _AMOUNT_CLEAN_RE.sub("", raw.strip())
    last_comma = cleaned.rfind(",")
    last_dot = cleaned.rfind(".")
    if last_comma > last_dot:
        # TR: virgül ondalık ayracı, nokta binlik.
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # EN/US (veya tek nokta): virgül binlik ayracı.
        cleaned = cleaned.replace(",", "")
    if not cleaned or cleaned in {"-", ".", "-."}:
        raise InvalidOperation(f"boş/geçersiz tutar: {raw!r}")
    return Decimal(cleaned)


def parse_date(raw: str) -> date:
    """İlk "GG.AA.YYYY" veya "GG/AA/YYYY" tarihini date'e çevirir.

    Eşleşme yoksa `ValueError` fırlatır.
    """
    m = _DATE_RE.search(raw)
    if not m:
        raise ValueError(f"tarih bulunamadı: {raw!r}")
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def clamp_day(day: int) -> int:
    """statement_day / payment_due_day model aralığına (1-28, le=28) sıkıştır."""
    return min(max(day, 1), 28)


def months_back(year: int, month: int, n: int) -> tuple[int, int]:
    """(year, month)'tan n ay geriye git; (year, month) döner (month 1-12)."""
    total = year * 12 + (month - 1) - n
    return total // 12, total % 12 + 1
