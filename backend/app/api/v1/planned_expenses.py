import calendar
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.expense import Expense
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
from app.schemas.recurring import RealizeMonthRequest, RealizeResult
from app.services import recurrence

_ISTANBUL = ZoneInfo("Europe/Istanbul")
_NOT_FOUND = "Kayıt bulunamadı"

router = APIRouter(prefix="/planned-expenses", tags=["planned-expenses"])


def _add_months(d: date_type, n: int) -> date_type:
    total = (d.year * 12 + d.month - 1) + n
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date_type(year, month, day)


def _applies_in_month(pe: PlannedExpense, year: int, month: int) -> bool:
    """Periyodik giderin verilen ay içinde geçerli olup olmadığı (ortak util)."""
    return recurrence.applies_in_month(pe, year, month)


@router.get("", response_model=list[PlannedExpenseOut])
async def list_planned_expenses(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(PlannedExpense).where(PlannedExpense.user_id == current_user.id).order_by(PlannedExpense.start_date))
    return result.scalars().all()


@router.post("", response_model=PlannedExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_planned_expense(
    payload: PlannedExpenseCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(PlannedExpense).where(
            PlannedExpense.id == pe_id,
            PlannedExpense.user_id == current_user.id,
        )
    )
    pe = result.scalar_one_or_none()
    if not pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)

    for field in (
        "title",
        "amount",
        "is_estimated",
        "category",
        "recurrence",
        "months",
        "day_of_month",
        "start_date",
        "end_date",
        "remaining_count",
        "notes",
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
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(PlannedExpense).where(
            PlannedExpense.id == pe_id,
            PlannedExpense.user_id == current_user.id,
        )
    )
    pe = result.scalar_one_or_none()
    if not pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    await db.delete(pe)
    await db.commit()


@router.get("/forecast", response_model=ForecastResult)
async def get_forecast(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Query(ge=2020, le=2100)],
):
    """Yillik nakit akisi tahmini — planli odemeler baz alinir.

    Cift sayim kurali: credit_card_id NOT NULL + is_paid=true olan kayitlar
    forecast'a dahil edilmez (kart borcu zaten sayilmis). Henuz odenmemis
    kart planlari (is_paid=false) dahil — gelecek bir nakit cikisi.
    """
    result = await db.execute(select(PlannedExpense).where(PlannedExpense.user_id == current_user.id))
    all_planned = result.scalars().all()
    # Filtre: kart + odendi olanlari at
    eligible = [pe for pe in all_planned if pe.credit_card_id is None or not pe.is_paid]

    months_out: list[ForecastMonth] = []
    year_total = Decimal("0")

    for m in range(1, 13):
        items: list[ForecastItem] = []
        for pe in eligible:
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


# ---------------------------------------------------------------------------
# Periyodik gider gerçekleştirme (planned_expense → expenses) — income paralel
# ---------------------------------------------------------------------------
async def _get_owned_planned(pe_id: int, user: User, db: AsyncSession) -> PlannedExpense:
    result = await db.execute(select(PlannedExpense).where(PlannedExpense.id == pe_id, PlannedExpense.user_id == user.id))
    pe = result.scalar_one_or_none()
    if not pe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return pe


async def _realize_one_expense(
    db: AsyncSession,
    pe: PlannedExpense,
    year: int,
    month: int,
    user_id,
    today: date_type | None = None,
) -> int | None:
    """Tek bir periyodik gider için verilen ay-yıl gerçek `Expense` oluşturur.

    None döner: periyot dışı / ödeme günü henüz gelmedi / o dönem zaten realize.
    Çift sayım: pe kredi kartından ise credit_card_id + is_paid taşınır
    (kart borcuyla mükerrer sayılmaması filtreye uyumlu)."""
    if not recurrence.applies_in_month(pe, year, month):
        return None
    target_date = recurrence.date_for_period(pe, year, month)
    if today is None:
        today = datetime.now(_ISTANBUL).date()
    if target_date > today:
        return None
    existing_q = await db.execute(
        select(Expense.id).where(
            Expense.user_id == user_id,
            Expense.planned_expense_id == pe.id,
            Expense.date == target_date,
        )
    )
    if existing_q.scalar_one_or_none() is not None:
        return None
    exp = Expense(
        user_id=user_id,
        amount=pe.amount,
        category=pe.category,
        date=target_date,
        description=pe.title,
        planned_expense_id=pe.id,
        credit_card_id=pe.credit_card_id,
        is_paid=True,
    )
    db.add(exp)
    await db.flush()
    return exp.id


@router.post("/{pe_id}/realize", response_model=RealizeResult)
async def realize_planned_period(
    pe_id: int,
    payload: RealizeMonthRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Periyodik giderin belirli bir ay-yılı için gerçek harcama kaydı oluştur.
    Idempotent: aynı dönem ikinci kez çağrılırsa skip."""
    pe = await _get_owned_planned(pe_id, current_user, db)
    if not recurrence.applies_in_month(pe, payload.year, payload.month):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bu kayıt belirtilen ay-yılında geçerli değil (periyot dışı)",
        )
    today = datetime.now(_ISTANBUL).date()
    target_date = recurrence.date_for_period(pe, payload.year, payload.month)
    if target_date > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ödeme günü ({target_date.isoformat()}) henüz gelmedi — gerçekleşti olarak işaretlenemez",
        )
    new_id = await _realize_one_expense(db, pe, payload.year, payload.month, current_user.id, today=today)
    await db.commit()
    if new_id is None:
        return RealizeResult(realized=0, skipped=1, ids=[])
    return RealizeResult(realized=1, skipped=0, ids=[new_id])


@router.post("/{pe_id}/realize-past", response_model=RealizeResult)
async def realize_planned_past(
    pe_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Periyodik giderin start_date'ten bugüne tüm geçmiş dönemlerini gerçekleştir.
    Mevcut realize'ler skip."""
    pe = await _get_owned_planned(pe_id, current_user, db)
    today = datetime.now(_ISTANBUL).date()
    ids: list[int] = []
    skipped = 0
    for y, m, _target in recurrence.iter_due_periods(pe, today):
        new_id = await _realize_one_expense(db, pe, y, m, current_user.id, today=today)
        if new_id is None:
            skipped += 1
        else:
            ids.append(new_id)
    await db.commit()
    return RealizeResult(realized=len(ids), skipped=skipped, ids=ids)
