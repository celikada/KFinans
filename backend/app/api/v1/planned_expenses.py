import calendar
from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.planned_expense import PlannedExpense
from app.models.user import User
from app.schemas.planned_expense import (
    ForecastItem,
    ForecastMonth,
    ForecastResult,
    PlannedExpenseCreate,
    PlannedExpenseOut,
    PlannedExpenseUpdate,
)

router = APIRouter(prefix="/planned-expenses", tags=["planned-expenses"])


def _add_months(d: date_type, n: int) -> date_type:
    total = (d.year * 12 + d.month - 1) + n
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date_type(year, month, day)


def _applies_in_month(pe: PlannedExpense, year: int, month: int) -> bool:
    last_day = calendar.monthrange(year, month)[1]
    first_of_month = date_type(year, month, 1)
    last_of_month = date_type(year, month, last_day)

    if pe.start_date > last_of_month:
        return False
    if pe.end_date is not None and pe.end_date < first_of_month:
        return False

    rec = pe.recurrence
    months_since = (year * 12 + month) - (pe.start_date.year * 12 + pe.start_date.month)

    if rec == "one_time":
        return pe.start_date.year == year and pe.start_date.month == month
    elif rec == "monthly":
        return months_since >= 0
    elif rec == "quarterly":
        return months_since >= 0 and months_since % 3 == 0
    elif rec == "biannual":
        return months_since >= 0 and months_since % 6 == 0
    elif rec == "yearly":
        return pe.start_date.month == month and pe.start_date.year <= year
    elif rec == "custom":
        return pe.months is not None and month in pe.months and pe.start_date.year <= year
    return False


@router.get("", response_model=list[PlannedExpenseOut])
async def list_planned_expenses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlannedExpense)
        .where(PlannedExpense.user_id == current_user.id)
        .order_by(PlannedExpense.start_date)
    )
    return result.scalars().all()


@router.post("", response_model=PlannedExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_planned_expense(
    payload: PlannedExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    end_date = payload.end_date
    if payload.remaining_count and not end_date and payload.recurrence == "monthly":
        end_date = _add_months(payload.start_date, payload.remaining_count - 1)

    pe = PlannedExpense(
        user_id=current_user.id,
        title=payload.title.strip(),
        amount=payload.amount,
        is_estimated=payload.is_estimated,
        category=payload.category,
        recurrence=payload.recurrence,
        months=payload.months,
        day_of_month=payload.day_of_month,
        start_date=payload.start_date,
        end_date=end_date,
        remaining_count=payload.remaining_count,
        notes=payload.notes.strip() if payload.notes else None,
        credit_card_id=payload.credit_card_id,
        is_paid=payload.is_paid,
    )
    db.add(pe)
    await db.commit()
    await db.refresh(pe)
    return pe


@router.put("/{pe_id}", response_model=PlannedExpenseOut)
async def update_planned_expense(
    pe_id: int,
    payload: PlannedExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlannedExpense).where(
            PlannedExpense.id == pe_id,
            PlannedExpense.user_id == current_user.id,
        )
    )
    pe = result.scalar_one_or_none()
    if not pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")

    for field in (
        "title", "amount", "is_estimated", "category", "recurrence",
        "months", "day_of_month", "start_date", "end_date", "remaining_count", "notes",
        "is_paid",
    ):
        val = getattr(payload, field)
        if val is not None:
            setattr(pe, field, val)
    # credit_card_id: None set edebilmek için explicit kontrol
    if "credit_card_id" in payload.model_fields_set:
        pe.credit_card_id = payload.credit_card_id

    await db.commit()
    await db.refresh(pe)
    return pe


@router.delete("/{pe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_planned_expense(
    pe_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlannedExpense).where(
            PlannedExpense.id == pe_id,
            PlannedExpense.user_id == current_user.id,
        )
    )
    pe = result.scalar_one_or_none()
    if not pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")
    await db.delete(pe)
    await db.commit()


@router.get("/forecast", response_model=ForecastResult)
async def get_forecast(
    year: int = Query(..., ge=2020, le=2100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yillik nakit akisi tahmini — planli odemeler baz alinir."""
    result = await db.execute(
        select(PlannedExpense).where(PlannedExpense.user_id == current_user.id)
    )
    all_planned = result.scalars().all()

    months_out: list[ForecastMonth] = []
    year_total = Decimal("0")

    for m in range(1, 13):
        items: list[ForecastItem] = []
        for pe in all_planned:
            if _applies_in_month(pe, year, m):
                items.append(
                    ForecastItem(
                        id=pe.id,
                        title=pe.title,
                        amount=pe.amount,
                        category=pe.category,
                        is_estimated=pe.is_estimated,
                    )
                )
        total = sum(i.amount for i in items) if items else Decimal("0")
        year_total += total
        months_out.append(ForecastMonth(month=m, total=total, items=items))

    return ForecastResult(year=year, months=months_out, year_total=year_total)
