import calendar
import logging
from datetime import date as date_type
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.budget import Budget, BudgetLine, BudgetMonthNote, BudgetSettings
from app.models.expense import Expense
from app.models.user import User
from app.schemas.budget import (
    BudgetComparison,
    BudgetGridResponse,
    BudgetLineUpsert,
    BudgetOut,
    BudgetSettingsOut,
    BudgetSettingsUpdate,
    BudgetUpsert,
    MonthlyBudgetResponse,
    MonthNoteOut,
    MonthNoteUpdate,
)
from app.schemas.expense import EXPENSE_CATEGORIES
from app.services import budget_planner
from app.services import currency as currency_svc
from app.services import display_currency as display_svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetOut])
async def list_budgets(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Budget).where(Budget.user_id == current_user.id).order_by(Budget.category))
    return result.scalars().all()


# ─────────────────────────── Bütçe v2 (hibrit) ───────────────────────────


@router.get("/settings", response_model=BudgetSettingsOut)
async def get_budget_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ratios, bucket_map = await budget_planner.get_settings_resolved(db, current_user.id)
    return BudgetSettingsOut(
        fundamental_ratio=ratios["fundamental"],
        fun_ratio=ratios["fun"],
        future_ratio=ratios["future"],
        category_buckets=bucket_map,
    )


@router.put("/settings", response_model=BudgetSettingsOut)
async def update_budget_settings(
    payload: BudgetSettingsUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        pg_insert(BudgetSettings)
        .values(
            user_id=current_user.id,
            fundamental_ratio=payload.fundamental_ratio,
            fun_ratio=payload.fun_ratio,
            future_ratio=payload.future_ratio,
            category_buckets=payload.category_buckets,
        )
        .on_conflict_do_update(
            index_elements=[BudgetSettings.user_id],
            set_={
                "fundamental_ratio": payload.fundamental_ratio,
                "fun_ratio": payload.fun_ratio,
                "future_ratio": payload.future_ratio,
                "category_buckets": payload.category_buckets,
                "updated_at": func.now(),
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    ratios, bucket_map = await budget_planner.get_settings_resolved(db, current_user.id)
    return BudgetSettingsOut(
        fundamental_ratio=ratios["fundamental"],
        fun_ratio=ratios["fun"],
        future_ratio=ratios["future"],
        category_buckets=bucket_map,
    )


@router.get("/grid", response_model=BudgetGridResponse)
async def get_budget_grid(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Query(ge=2020, le=2100)],
    display: Annotated[str | None, Query()] = None,
):
    return await budget_planner.build_grid(db, current_user, year, display)


@router.put("/grid/{year}/{month}/{category}", response_model=BudgetOut)
async def upsert_budget_line(
    year: Annotated[int, Path(ge=2020, le=2100)],
    month: Annotated[int, Path(ge=1, le=12)],
    category: str,
    payload: BudgetLineUpsert,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if category not in budget_planner.ALL_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geçersiz kategori: {category}",
        )
    currency = payload.currency or current_user.default_currency or "TRY"
    stmt = (
        pg_insert(BudgetLine)
        .values(
            user_id=current_user.id,
            year=year,
            month=month,
            category=category,
            amount=payload.amount,
            currency=currency,
        )
        .on_conflict_do_update(
            constraint="uq_budget_line_period_cat",
            set_={"amount": payload.amount, "currency": currency, "updated_at": func.now()},
        )
        .returning(BudgetLine)
    )
    result = await db.execute(stmt)
    await db.commit()
    row = result.scalar_one()
    await db.refresh(row)
    return BudgetOut(id=row.id, category=row.category, amount=row.amount, currency=row.currency, updated_at=row.updated_at)


@router.delete("/grid/{year}/{month}/{category}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_line(
    year: Annotated[int, Path(ge=2020, le=2100)],
    month: Annotated[int, Path(ge=1, le=12)],
    category: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(BudgetLine).where(
            BudgetLine.user_id == current_user.id,
            BudgetLine.year == year,
            BudgetLine.month == month,
            BudgetLine.category == category,
        )
    )
    line = result.scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bütçe hücresi bulunamadı")
    await db.delete(line)
    await db.commit()


@router.get("/monthly", response_model=MonthlyBudgetResponse)
async def get_monthly_budget(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Query(ge=2020, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    display: Annotated[str | None, Query()] = None,
):
    return await budget_planner.monthly_buckets(db, current_user, year, month, display)


@router.get("/notes/{year}/{month}", response_model=MonthNoteOut)
async def get_month_note(
    year: Annotated[int, Path(ge=2020, le=2100)],
    month: Annotated[int, Path(ge=1, le=12)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (
        await db.execute(
            select(BudgetMonthNote).where(
                BudgetMonthNote.user_id == current_user.id,
                BudgetMonthNote.year == year,
                BudgetMonthNote.month == month,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return MonthNoteOut(year=year, month=month, analysis=None, action_plan=None)
    return row


@router.put("/notes/{year}/{month}", response_model=MonthNoteOut)
async def upsert_month_note(
    year: Annotated[int, Path(ge=2020, le=2100)],
    month: Annotated[int, Path(ge=1, le=12)],
    payload: MonthNoteUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        pg_insert(BudgetMonthNote)
        .values(
            user_id=current_user.id,
            year=year,
            month=month,
            analysis=payload.analysis,
            action_plan=payload.action_plan,
        )
        .on_conflict_do_update(
            constraint="uq_budget_note_period",
            set_={"analysis": payload.analysis, "action_plan": payload.action_plan, "updated_at": func.now()},
        )
        .returning(BudgetMonthNote)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()


@router.put("/{category}", response_model=BudgetOut)
async def upsert_budget(
    category: str,
    payload: BudgetUpsert,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if category not in EXPENSE_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geçersiz kategori: {category}",
        )

    currency = payload.currency or current_user.default_currency or "TRY"
    stmt = (
        pg_insert(Budget)
        .values(user_id=current_user.id, category=category, amount=payload.amount, currency=currency)
        .on_conflict_do_update(
            constraint="uq_budget_user_category",
            set_={"amount": payload.amount, "currency": currency, "updated_at": func.now()},
        )
        .returning(Budget)
    )
    result = await db.execute(stmt)
    await db.commit()
    row = result.scalar_one()
    await db.refresh(row)
    return row


@router.delete("/{category}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    category: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Budget).where(
            Budget.user_id == current_user.id,
            Budget.category == category,
        )
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bütçe bulunamadı")
    await db.delete(budget)
    await db.commit()


async def _actual_display_by_category(
    db: AsyncSession,
    user_id,
    first_day: date_type,
    last_day: date_type,
    not_double_counted,
    display_ccy: str,
) -> dict[str, Decimal]:
    """Kategori bazında gerçekleşmiş gider toplamının görüntüleme-birimi karşılığı
    (Faz B, tarihsel kur). Yalnız display != TRY iken çağrılır."""
    rows = (
        await db.execute(
            select(Expense.category, Expense.amount, Expense.currency, Expense.date, Expense.amount_tl).where(
                Expense.user_id == user_id,
                Expense.date >= first_day,
                Expense.date <= last_day,
                not_double_counted,
            )
        )
    ).all()
    cat_display, _ = await display_svc.convert_realized_grouped(db, rows, display_ccy)
    return cat_display


@router.get("/comparison", response_model=list[BudgetComparison])
async def get_comparison(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Query(ge=2020, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    display: Annotated[str | None, Query()] = None,
):
    first_day = date_type(year, month, 1)
    last_day = date_type(year, month, calendar.monthrange(year, month)[1])
    display_ccy = display_svc.normalize_display(display, current_user.default_currency)

    budgets_q = await db.execute(select(Budget).where(Budget.user_id == current_user.id))
    budgets = budgets_q.scalars().all()
    # Bütçe orijinal para birimi + tutar. Karşılaştırma TL bazlı (hibrit kur):
    # bütçe güncel kurla TL'ye çevrilir, harcama amount_tl (işlem-anı kuru) ile kıyas.
    budget_map: dict[str, tuple[Decimal, str]] = {b.category: (b.amount, b.currency or "TRY") for b in budgets}
    rates = await currency_svc.fetch_rates() if budgets else {}

    # Cift sayim filtresi: kart + odendi olanlari haric tut (kart borcu sayar)
    not_double_counted = or_(
        Expense.credit_card_id.is_(None),
        Expense.is_paid.is_(False),
    )
    actuals_q = await db.execute(
        select(Expense.category, func.coalesce(func.sum(Expense.amount_tl), 0))
        .where(
            Expense.user_id == current_user.id,
            Expense.date >= first_day,
            Expense.date <= last_day,
            not_double_counted,
        )
        .group_by(Expense.category)
    )
    actual_map: dict[str, Decimal] = {cat: Decimal(amt) for cat, amt in actuals_q.all()}

    # Görüntüleme para birimi (Faz B): actual → tarihsel, budget → güncel.
    actual_display_map: dict[str, Decimal] = {}
    if display_ccy != display_svc.TRY:
        actual_display_map = await _actual_display_by_category(db, current_user.id, first_day, last_day, not_double_counted, display_ccy)

    categories = sorted(set(budget_map.keys()) | set(actual_map.keys()))
    rows: list[BudgetComparison] = []
    for cat in categories:
        budget_entry = budget_map.get(cat)
        actual_amt = actual_map.get(cat, Decimal("0"))  # TL (amount_tl)
        actual_display = actual_amt if display_ccy == display_svc.TRY else actual_display_map.get(cat, Decimal("0"))
        if budget_entry is not None:
            budget_amt, budget_currency = budget_entry
            budget_amt_tl = currency_svc.convert_to_tl(Decimal(budget_amt), budget_currency, rates)
            remaining = budget_amt_tl - actual_amt
            pct_used = float(actual_amt / budget_amt_tl * 100) if budget_amt_tl > 0 else None
            over_budget = actual_amt > budget_amt_tl
            budget_display = display_svc.convert_forecast(Decimal(budget_amt), budget_currency, display_ccy, rates)
            remaining_display = display_svc.quantize_tl(budget_display - actual_display)
        else:
            budget_amt = None
            budget_currency = "TRY"
            budget_amt_tl = None
            remaining = None
            pct_used = None
            over_budget = False
            budget_display = None
            remaining_display = None
        rows.append(
            BudgetComparison(
                category=cat,
                budget_amount=budget_amt,
                budget_amount_tl=budget_amt_tl,
                budget_currency=budget_currency,
                actual_amount=actual_amt,
                remaining=remaining,
                pct_used=pct_used,
                over_budget=over_budget,
                display_currency=display_ccy,
                budget_amount_display=budget_display,
                actual_amount_display=actual_display,
                remaining_display=remaining_display,
            )
        )
    return rows
