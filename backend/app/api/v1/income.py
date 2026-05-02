import calendar
import logging
from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.income import Income
from app.models.user import User
from app.schemas.income import (
    INCOME_CATEGORIES,
    IncomeCategoryBreakdown,
    IncomeCreate,
    IncomeOut,
    IncomeSummary,
    IncomeUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/income", tags=["income"])


@router.get("", response_model=list[IncomeOut])
async def list_incomes(
    year: int | None = Query(default=None, ge=2020, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Income).where(Income.user_id == current_user.id)
    if year is not None and month is not None:
        first_day = date_type(year, month, 1)
        last_day = date_type(year, month, calendar.monthrange(year, month)[1])
        stmt = stmt.where(Income.date >= first_day, Income.date <= last_day)
    if category:
        if category not in INCOME_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Geçersiz kategori: {category}",
            )
        stmt = stmt.where(Income.category == category)
    stmt = stmt.order_by(desc(Income.date), desc(Income.created_at))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=IncomeOut, status_code=status.HTTP_201_CREATED)
async def create_income(
    payload: IncomeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inc = Income(
        user_id=current_user.id,
        amount=payload.amount,
        category=payload.category,
        date=payload.date,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(inc)
    await db.commit()
    await db.refresh(inc)
    return inc


@router.put("/{income_id}", response_model=IncomeOut)
async def update_income(
    income_id: int,
    payload: IncomeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Income).where(Income.id == income_id, Income.user_id == current_user.id)
    )
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")

    if payload.amount is not None:
        inc.amount = payload.amount
    if payload.category is not None:
        inc.category = payload.category
    if payload.date is not None:
        inc.date = payload.date
    if payload.description is not None:
        inc.description = payload.description.strip() or None

    await db.commit()
    await db.refresh(inc)
    return inc


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income(
    income_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Income).where(Income.id == income_id, Income.user_id == current_user.id)
    )
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")
    await db.delete(inc)
    await db.commit()


@router.get("/summary", response_model=IncomeSummary)
async def get_income_summary(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    first_day = date_type(year, month, 1)
    last_day = date_type(year, month, calendar.monthrange(year, month)[1])

    total_q = await db.execute(
        select(func.coalesce(func.sum(Income.amount), 0), func.count(Income.id))
        .where(Income.user_id == current_user.id, Income.date >= first_day, Income.date <= last_day)
    )
    total, count = total_q.one()

    cat_q = await db.execute(
        select(Income.category, func.sum(Income.amount), func.count(Income.id))
        .where(Income.user_id == current_user.id, Income.date >= first_day, Income.date <= last_day)
        .group_by(Income.category)
        .order_by(desc(func.sum(Income.amount)))
    )
    breakdown = [
        IncomeCategoryBreakdown(category=cat, total=Decimal(amt), count=cnt)
        for cat, amt, cnt in cat_q.all()
    ]

    return IncomeSummary(
        year=year, month=month,
        total=Decimal(total), count=count,
        by_category=breakdown,
    )
