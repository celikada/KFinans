import calendar
import logging
from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import (
    CategoryBreakdown,
    EXPENSE_CATEGORIES,
    ExpenseCreate,
    ExpenseOut,
    ExpenseSummary,
    ExpenseUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseOut])
async def list_expenses(
    year: int | None = Query(default=None, ge=2020, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Harcama listesi — opsiyonel year/month/category filtresi.

    En son tarihliden eskiye sirayla doner; ayni gun icindekiler en son
    eklenen ust sirada.
    """
    stmt = select(Expense).where(Expense.user_id == current_user.id)
    if year is not None and month is not None:
        first_day = date_type(year, month, 1)
        last_day = date_type(year, month, calendar.monthrange(year, month)[1])
        stmt = stmt.where(Expense.date >= first_day, Expense.date <= last_day)
    if category:
        if category not in EXPENSE_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Geçersiz kategori: {category}",
            )
        stmt = stmt.where(Expense.category == category)
    stmt = stmt.order_by(desc(Expense.date), desc(Expense.created_at))

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    expense = Expense(
        user_id=current_user.id,
        amount=payload.amount,
        category=payload.category,
        date=payload.date,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.put("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == current_user.id,
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Harcama bulunamadı")

    if payload.amount is not None:
        expense.amount = payload.amount
    if payload.category is not None:
        expense.category = payload.category
    if payload.date is not None:
        expense.date = payload.date
    if payload.description is not None:
        expense.description = payload.description.strip() or None

    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == current_user.id,
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Harcama bulunamadı")

    await db.delete(expense)
    await db.commit()


@router.get("/summary", response_model=ExpenseSummary)
async def get_expense_summary(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirli ay icin toplam + kategori bazinda kirilim."""
    first_day = date_type(year, month, 1)
    last_day = date_type(year, month, calendar.monthrange(year, month)[1])

    # Toplam ve adet
    total_q = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.id))
        .where(
            Expense.user_id == current_user.id,
            Expense.date >= first_day,
            Expense.date <= last_day,
        )
    )
    total, count = total_q.one()

    # Kategori kirilimi
    cat_q = await db.execute(
        select(
            Expense.category,
            func.sum(Expense.amount),
            func.count(Expense.id),
        )
        .where(
            Expense.user_id == current_user.id,
            Expense.date >= first_day,
            Expense.date <= last_day,
        )
        .group_by(Expense.category)
        .order_by(desc(func.sum(Expense.amount)))
    )
    breakdown = [
        CategoryBreakdown(category=cat, total=Decimal(amt), count=cnt)
        for cat, amt, cnt in cat_q.all()
    ]

    return ExpenseSummary(
        year=year,
        month=month,
        total=Decimal(total),
        count=count,
        by_category=breakdown,
    )
