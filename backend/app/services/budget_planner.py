"""Bütçe v2 (hibrit) hesaplama servisi.

Mevcut veriyi (expenses/incomes/planned_expenses) kaynak alan birleşik planlama
katmanı. Üç ana çıktı:

- **Izgara** (``build_grid``): her (kategori, ay) için planlanan (``budget_lines``)
  + gerçekleşen (``expenses``) — butce26.xlsx 12 aylık ızgara.
- **Aylık 3-kova** (``monthly_buckets``): Fundamental/Fun/Future You kovalarında
  budget-vs-actual + gelir + NET — Budget empty.xlsx May/June.
- **Ağırlıklandırma** (``weighted_periodic_for_month``): aylık-olmayan planlı
  giderlerin (yıllık/biannual/quarterly/custom) aylık-eşdeğer yükü (yıllık/12).

Para birimi: actual → tarihsel kur (``display_currency.convert_realized_grouped``);
planlanan/tahmin → güncel kur (``convert_forecast``). ``display == TRY`` hızlı yol
(``Σ amount_tl`` SQL). Çift-sayım filtresi gider actual'ında uygulanır.
"""

from __future__ import annotations

import calendar
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import BudgetLine, BudgetSettings
from app.models.expense import Expense
from app.models.income import Income
from app.models.planned_expense import PlannedExpense
from app.models.user import User
from app.schemas.expense import EXPENSE_CATEGORIES
from app.services import currency as currency_svc
from app.services import display_currency as display_svc
from app.services.recurrence import applies_in_month

TRY = display_svc.TRY

# Future You kovası bütçe hedefi bu özel kategori anahtarıyla tutulur (gider
# kategorisi değil — birikim/yatırım hedefi).
SAVINGS_CATEGORY = "savings"

BUCKETS: tuple[str, ...] = ("fundamental", "fun", "future")

# Kategori → kova varsayılan eşlemesi (kullanıcı ``budget_settings`` ile override eder).
# Hem gider kategorileri hem de planlı-gider kategorileri (insurance/rent/utility/...)
# kapsanır — ağırlıklı periyodik satırlar planlı kategoriyi kullanır (butce26'da
# kasko/sigorta/MTV/okul hep temel ihtiyaç).
DEFAULT_CATEGORY_BUCKET: dict[str, str] = {
    # Expense kategorileri
    "groceries": "fundamental",
    "bills": "fundamental",
    "transport": "fundamental",
    "health": "fundamental",
    "home": "fundamental",
    "tax": "fundamental",
    "food": "fun",
    "entertainment": "fun",
    "clothing": "fun",
    "other": "fun",
    # Planlı-gider kategorileri (ağırlıklandırma için)
    "loan": "fundamental",
    "insurance": "fundamental",
    "rent": "fundamental",
    "utility": "fundamental",
    "subscription": "fun",
    SAVINGS_CATEGORY: "future",
}

DEFAULT_RATIOS = {"fundamental": 0.5, "fun": 0.3, "future": 0.2}

# Aylık-olmayan (ağırlıklandırılacak) periyodik tipler.
_WEIGHTED_RECURRENCES = {"quarterly", "biannual", "yearly", "custom"}

# Grid/monthly'de gösterilecek tüm kategoriler (gider + savings).
ALL_CATEGORIES: tuple[str, ...] = (*EXPENSE_CATEGORIES, SAVINGS_CATEGORY)

_NOT_DOUBLE_COUNTED = or_(Expense.credit_card_id.is_(None), Expense.is_paid.is_(False))


def resolve_category_buckets(overrides: dict | None) -> dict[str, str]:
    """Kod-içi default + kullanıcı override'larını birleştirip tam kategori→kova map döner."""
    merged = dict(DEFAULT_CATEGORY_BUCKET)
    if overrides:
        for cat, bucket in overrides.items():
            if bucket in BUCKETS:
                merged[cat] = bucket
    return merged


async def get_settings_resolved(db: AsyncSession, user_id) -> tuple[dict[str, float], dict[str, str]]:
    """Kullanıcının kova oranları + tam çözümlenmiş kategori→kova map'i.

    Kayıt yoksa kod-içi varsayılanlar döner (DB'ye yazmaz)."""
    row = (await db.execute(select(BudgetSettings).where(BudgetSettings.user_id == user_id))).scalar_one_or_none()
    if row is None:
        return dict(DEFAULT_RATIOS), resolve_category_buckets(None)
    ratios = {
        "fundamental": float(row.fundamental_ratio),
        "fun": float(row.fun_ratio),
        "future": float(row.future_ratio),
    }
    return ratios, resolve_category_buckets(row.category_buckets)


def _bucket_of(category: str, bucket_map: dict[str, str]) -> str:
    return bucket_map.get(category, "fun")


# ───────────────────────── Actual (gider/gelir) yardımcıları ─────────────────────────


async def _expense_actuals_year(db: AsyncSession, user_id, year: int, display: str) -> dict[str, dict[int, Decimal]]:
    """{kategori: {ay: display-tutar}} — yıl boyunca gerçekleşen gider (çift-sayım hariç)."""
    first = date_type(year, 1, 1)
    last = date_type(year, 12, 31)
    if display == TRY:
        rows = (
            await db.execute(
                select(
                    Expense.category,
                    func.extract("month", Expense.date),
                    func.coalesce(func.sum(Expense.amount_tl), 0),
                )
                .where(
                    Expense.user_id == user_id,
                    Expense.date >= first,
                    Expense.date <= last,
                    _NOT_DOUBLE_COUNTED,
                )
                .group_by(Expense.category, func.extract("month", Expense.date))
            )
        ).all()
        out: dict[str, dict[int, Decimal]] = {}
        for cat, month, amt in rows:
            out.setdefault(cat, {})[int(month)] = Decimal(amt)
        return out

    # display != TRY → tarihsel kur; ham satırları (kategori|ay) anahtarıyla grupla.
    raw = (
        await db.execute(
            select(Expense.category, Expense.amount, Expense.currency, Expense.date, Expense.amount_tl).where(
                Expense.user_id == user_id,
                Expense.date >= first,
                Expense.date <= last,
                _NOT_DOUBLE_COUNTED,
            )
        )
    ).all()
    keyed = [(f"{cat}|{on.month}", amount, currency, on, amount_tl) for cat, amount, currency, on, amount_tl in raw]
    grouped, _ = await display_svc.convert_realized_grouped(db, keyed, display)
    out = {}
    for key, val in grouped.items():
        cat, month = key.rsplit("|", 1)
        out.setdefault(cat, {})[int(month)] = val
    return out


async def _expense_actuals_month(db: AsyncSession, user_id, year: int, month: int, display: str) -> dict[str, Decimal]:
    """{kategori: display-tutar} — tek ay gerçekleşen gider (çift-sayım hariç)."""
    first = date_type(year, month, 1)
    last = date_type(year, month, calendar.monthrange(year, month)[1])
    if display == TRY:
        rows = (
            await db.execute(
                select(Expense.category, func.coalesce(func.sum(Expense.amount_tl), 0))
                .where(
                    Expense.user_id == user_id,
                    Expense.date >= first,
                    Expense.date <= last,
                    _NOT_DOUBLE_COUNTED,
                )
                .group_by(Expense.category)
            )
        ).all()
        return {cat: Decimal(amt) for cat, amt in rows}

    raw = (
        await db.execute(
            select(Expense.category, Expense.amount, Expense.currency, Expense.date, Expense.amount_tl).where(
                Expense.user_id == user_id,
                Expense.date >= first,
                Expense.date <= last,
                _NOT_DOUBLE_COUNTED,
            )
        )
    ).all()
    grouped, _ = await display_svc.convert_realized_grouped(db, raw, display)
    return grouped


async def _income_total_month(db: AsyncSession, user_id, year: int, month: int, display: str) -> Decimal:
    """Tek ay gerçekleşen gelir toplamı (display birimi)."""
    first = date_type(year, month, 1)
    last = date_type(year, month, calendar.monthrange(year, month)[1])
    if display == TRY:
        total = (
            await db.execute(
                select(func.coalesce(func.sum(Income.amount_tl), 0)).where(
                    Income.user_id == user_id,
                    Income.date >= first,
                    Income.date <= last,
                )
            )
        ).scalar_one()
        return Decimal(total)

    raw = (
        await db.execute(
            select(Income.category, Income.amount, Income.currency, Income.date, Income.amount_tl).where(
                Income.user_id == user_id,
                Income.date >= first,
                Income.date <= last,
            )
        )
    ).all()
    # Tek toplam yeterli → sabit anahtar.
    keyed = [("_", amount, currency, on, amount_tl) for _cat, amount, currency, on, amount_tl in raw]
    _grouped, total = await display_svc.convert_realized_grouped(db, keyed, display)
    return total


# ───────────────────────────── Ağırlıklandırma ─────────────────────────────


async def weighted_periodic_for_year(
    db: AsyncSession,
    user_id,
    year: int,
    display: str,
    rates: dict[str, Decimal],
) -> list[tuple[str, str, Decimal]]:
    """Aylık-olmayan planlı giderlerin aylık-eşdeğer yükü (ay-bağımsız).

    Her aylık-olmayan ``planned_expense`` (yıllık/biannual/quarterly/custom) için
    yıl içindeki toplam tutar hesaplanır ve 12'ye bölünerek aylık ağırlık bulunur
    (butce26 "Aylık olmayan Giderlerin Aylık Ağırlığı"). Değer her ay için aynıdır.
    Döner: ``(label, bucket_category, monthly_equiv_display)``.
    """
    rows = (
        (
            await db.execute(
                select(PlannedExpense).where(
                    PlannedExpense.user_id == user_id,
                    PlannedExpense.recurrence.in_(_WEIGHTED_RECURRENCES),
                )
            )
        )
        .scalars()
        .all()
    )

    out: list[tuple[str, str, Decimal]] = []
    for pe in rows:
        occurrences = sum(1 for m in range(1, 13) if applies_in_month(pe, year, m))
        if occurrences == 0:
            continue
        per_hit = display_svc.convert_forecast(Decimal(pe.amount), pe.currency, display, rates)
        monthly_equiv = display_svc.quantize_tl(per_hit * occurrences / Decimal(12))
        out.append((pe.title, pe.category, monthly_equiv))
    return out


# ───────────────────────────── Izgara (yıllık) ─────────────────────────────


async def build_grid(db: AsyncSession, user: User, year: int, display: str | None) -> dict:
    """12 aylık × kategori ızgara: planlanan (budget_lines) + gerçekleşen (expenses)."""
    display_ccy = display_svc.normalize_display(display, user.default_currency)
    _ratios, bucket_map = await get_settings_resolved(db, user.id)

    lines = (await db.execute(select(BudgetLine).where(BudgetLine.user_id == user.id, BudgetLine.year == year))).scalars().all()
    planned_by_cat: dict[str, dict[int, BudgetLine]] = {}
    for ln in lines:
        planned_by_cat.setdefault(ln.category, {})[int(ln.month)] = ln

    rates = await currency_svc.fetch_rates() if lines or display_ccy != TRY else {}
    actuals = await _expense_actuals_year(db, user.id, year, display_ccy)

    categories = sorted(
        set(ALL_CATEGORIES) | set(planned_by_cat) | set(actuals),
        key=lambda c: (BUCKETS.index(_bucket_of(c, bucket_map)) if _bucket_of(c, bucket_map) in BUCKETS else 9, c),
    )

    monthly_planned = [Decimal(0) for _ in range(12)]
    monthly_actual = [Decimal(0) for _ in range(12)]
    grand_planned = Decimal(0)
    grand_actual = Decimal(0)
    rows_out = []
    for cat in categories:
        cells = []
        row_planned = Decimal(0)
        row_actual = Decimal(0)
        for m in range(1, 13):
            ln = planned_by_cat.get(cat, {}).get(m)
            planned_display = None
            planned_amt = None
            planned_ccy = None
            if ln is not None:
                planned_amt = Decimal(ln.amount)
                planned_ccy = ln.currency
                planned_display = display_svc.convert_forecast(planned_amt, ln.currency, display_ccy, rates)
                row_planned += planned_display
                monthly_planned[m - 1] += planned_display
            actual_display = actuals.get(cat, {}).get(m, Decimal(0))
            row_actual += actual_display
            monthly_actual[m - 1] += actual_display
            cells.append(
                {
                    "month": m,
                    "planned": planned_amt,
                    "planned_currency": planned_ccy,
                    "planned_display": planned_display,
                    "actual_display": actual_display,
                }
            )
        grand_planned += row_planned
        grand_actual += row_actual
        rows_out.append(
            {
                "category": cat,
                "bucket": _bucket_of(cat, bucket_map),
                "cells": cells,
                "planned_total_display": display_svc.quantize_tl(row_planned),
                "actual_total_display": display_svc.quantize_tl(row_actual),
            }
        )

    return {
        "year": year,
        "display_currency": display_ccy,
        "rows": rows_out,
        "monthly_planned_display": [display_svc.quantize_tl(x) for x in monthly_planned],
        "monthly_actual_display": [display_svc.quantize_tl(x) for x in monthly_actual],
        "planned_total_display": display_svc.quantize_tl(grand_planned),
        "actual_total_display": display_svc.quantize_tl(grand_actual),
    }


# ─────────────────────────── Aylık 3-kova görünümü ───────────────────────────


async def monthly_buckets(db: AsyncSession, user: User, year: int, month: int, display: str | None) -> dict:
    """Aylık 3-kova budget-vs-actual + gelir + NET (Budget empty May/June)."""
    display_ccy = display_svc.normalize_display(display, user.default_currency)
    ratios, bucket_map = await get_settings_resolved(db, user.id)
    rates = await currency_svc.fetch_rates()

    # Planlanan (o ay budget_lines)
    lines = (
        (
            await db.execute(
                select(BudgetLine).where(
                    BudgetLine.user_id == user.id,
                    BudgetLine.year == year,
                    BudgetLine.month == month,
                )
            )
        )
        .scalars()
        .all()
    )
    planned_by_cat = {ln.category: display_svc.convert_forecast(Decimal(ln.amount), ln.currency, display_ccy, rates) for ln in lines}

    actual_by_cat = await _expense_actuals_month(db, user.id, year, month, display_ccy)
    weighted = await weighted_periodic_for_year(db, user.id, year, display_ccy, rates)

    income_display = await _income_total_month(db, user.id, year, month, display_ccy)

    # Kova → kategori satırları
    blocks: dict[str, dict] = {b: {"budget": Decimal(0), "actual": Decimal(0), "categories": []} for b in BUCKETS}
    seen_categories = set(planned_by_cat) | set(actual_by_cat) | {SAVINGS_CATEGORY}
    for cat in sorted(seen_categories):
        bucket = _bucket_of(cat, bucket_map)
        if bucket not in blocks:
            bucket = "fun"
        budget_d = display_svc.quantize_tl(planned_by_cat.get(cat, Decimal(0)))
        actual_d = display_svc.quantize_tl(actual_by_cat.get(cat, Decimal(0)))
        if budget_d == 0 and actual_d == 0 and cat == SAVINGS_CATEGORY:
            continue  # boş savings satırını gösterme
        pct = float(actual_d / budget_d * 100) if budget_d > 0 else None
        blocks[bucket]["budget"] += budget_d
        blocks[bucket]["actual"] += actual_d
        blocks[bucket]["categories"].append(
            {
                "category": cat,
                "budget_display": budget_d,
                "actual_display": actual_d,
                "difference_display": display_svc.quantize_tl(budget_d - actual_d),
                "pct_used": pct,
                "over_budget": actual_d > budget_d > 0,
                "weighted": False,
            }
        )

    # Ağırlıklı periyodik satırları (budget tarafına, weighted rozet)
    for label, cat, monthly_equiv in weighted:
        bucket = _bucket_of(cat, bucket_map)
        if bucket not in blocks:
            bucket = "fundamental"
        blocks[bucket]["budget"] += monthly_equiv
        blocks[bucket]["categories"].append(
            {
                "category": label,
                "budget_display": monthly_equiv,
                "actual_display": Decimal(0),
                "difference_display": monthly_equiv,
                "pct_used": None,
                "over_budget": False,
                "weighted": True,
            }
        )

    expense_total = sum((b["actual"] for b in blocks.values()), Decimal(0))
    buckets_out = []
    for b in BUCKETS:
        data = blocks[b]
        budget_t = display_svc.quantize_tl(data["budget"])
        actual_t = display_svc.quantize_tl(data["actual"])
        actual_ratio = float(actual_t / expense_total) if expense_total > 0 else None
        buckets_out.append(
            {
                "bucket": b,
                "target_ratio": ratios[b],
                "budget_total_display": budget_t,
                "actual_total_display": actual_t,
                "difference_display": display_svc.quantize_tl(budget_t - actual_t),
                "actual_ratio": actual_ratio,
                "categories": data["categories"],
            }
        )

    expense_total_q = display_svc.quantize_tl(expense_total)
    return {
        "year": year,
        "month": month,
        "display_currency": display_ccy,
        "income_display": income_display,
        "expense_total_display": expense_total_q,
        "net_display": display_svc.quantize_tl(income_display - expense_total_q),
        "buckets": buckets_out,
    }
