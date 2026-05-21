import calendar
import logging
from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.budget import Budget
from app.models.expense import Expense
from app.models.user import User
from app.schemas.budget import BudgetComparison, BudgetOut, BudgetUpsert
from app.schemas.expense import EXPENSE_CATEGORIES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetOut])
async def list_budgets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Budget).where(Budget.user_id == current_user.id).order_by(Budget.category)
    )
    return result.scalars().all()


@router.put("/{category}", response_model=BudgetOut)
async def upsert_budget(
    category: str,
    payload: BudgetUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if category not in EXPENSE_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geçersiz kategori: {category}",
        )

    stmt = (
        pg_insert(Budget)
        .values(user_id=current_user.id, category=category, amount=payload.amount)
        .on_conflict_do_update(
            constraint="uq_budget_user_category",
            set_={"amount": payload.amount, "updated_at": func.now()},
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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


@router.get("/comparison", response_model=list[BudgetComparison])
async def get_comparison(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    first_day = date_type(year, month, 1)
    last_day = date_type(year, month, calendar.monthrange(year, month)[1])

    budgets_q = await db.execute(select(Budget).where(Budget.user_id == current_user.id))
    budget_map: dict[str, Decimal] = {b.category: b.amount for b in budgets_q.scalars().all()}

    # Cift sayim filtresi: kart + odendi olanlari haric tut (kart borcu sayar)
    not_double_counted = or_(
        Expense.credit_card_id.is_(None),
        Expense.is_paid.is_(False),
    )
    actuals_q = await db.execute(
        select(Expense.category, func.coalesce(func.sum(Expense.amount), 0))
        .where(
            Expense.user_id == current_user.id,
            Expense.date >= first_day,
            Expense.date <= last_day,
            not_double_counted,
        )
        .group_by(Expense.category)
    )
    actual_map: dict[str, Decimal] = {cat: Decimal(amt) for cat, amt in actuals_q.all()}

    categories = sorted(set(budget_map.keys()) | set(actual_map.keys()))
    rows: list[BudgetComparison] = []
    for cat in categories:
        budget_amt = budget_map.get(cat)
        actual_amt = actual_map.get(cat, Decimal("0"))
        if budget_amt is not None:
            remaining = budget_amt - actual_amt
            pct_used = float(actual_amt / budget_amt * 100) if budget_amt > 0 else None
            over_budget = actual_amt > budget_amt
        else:
            remaining = None
            pct_used = None
            over_budget = False
        rows.append(
            BudgetComparison(
                category=cat,
                budget_amount=budget_amt,
                actual_amount=actual_amt,
                remaining=remaining,
                pct_used=pct_used,
                over_budget=over_budget,
            )
        )
    return rows
