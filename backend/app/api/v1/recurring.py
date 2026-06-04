"""Periyodik gelir/gider ortak uçları: bekleyen dönemler (pending) + atlama (skip).

`/recurring/pending` — dashboard popup'ı için: tarihi geçmiş ama ne gerçekleşmiş
(income/expense kaydı) ne de atlanmış (recurring_skips) dönemleri döner.
`/recurring/skips` — bir dönemi 'gerçekleşmeyecek' işaretle / geri al.
"""

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.expense import Expense
from app.models.income import Income
from app.models.planned_expense import PlannedExpense
from app.models.recurring_income import RecurringIncome
from app.models.recurring_skip import RecurringSkip
from app.models.user import User
from app.schemas.recurring import PendingItem, PendingResponse, SkipOut, SkipRequest
from app.services import recurrence

_ISTANBUL = ZoneInfo("Europe/Istanbul")

router = APIRouter(prefix="/recurring", tags=["recurring"])


async def _collect_income_pending(
    db: AsyncSession,
    user: User,
    today,
    skip_set: set[tuple[str, int, int, int]],
) -> list[PendingItem]:
    """Periyodik gelirlerin bekleyen (gerçekleşmemiş + atlanmamış) dönemleri."""
    ri_list = (await db.execute(select(RecurringIncome).where(RecurringIncome.user_id == user.id))).scalars().all()
    realized_inc = {
        (rid, d)
        for rid, d in (
            await db.execute(
                select(Income.recurring_income_id, Income.date).where(
                    Income.user_id == user.id,
                    Income.recurring_income_id.is_not(None),
                )
            )
        ).all()
    }
    items: list[PendingItem] = []
    for ri in ri_list:
        for y, m, target in recurrence.iter_due_periods(ri, today):
            if (ri.id, target) in realized_inc:
                continue
            if ("income", ri.id, y, m) in skip_set:
                continue
            items.append(
                PendingItem(
                    kind="income",
                    ref_id=ri.id,
                    title=ri.title,
                    category=ri.category,
                    amount=ri.amount,
                    period_year=y,
                    period_month=m,
                    occurrence_date=target,
                )
            )
    return items


async def _collect_expense_pending(
    db: AsyncSession,
    user: User,
    today,
    skip_set: set[tuple[str, int, int, int]],
) -> list[PendingItem]:
    """Planlı (periyodik) giderlerin bekleyen dönemleri."""
    pe_list = (await db.execute(select(PlannedExpense).where(PlannedExpense.user_id == user.id))).scalars().all()
    realized_exp = {
        (pid, d)
        for pid, d in (
            await db.execute(
                select(Expense.planned_expense_id, Expense.date).where(
                    Expense.user_id == user.id,
                    Expense.planned_expense_id.is_not(None),
                )
            )
        ).all()
    }
    items: list[PendingItem] = []
    for pe in pe_list:
        for y, m, target in recurrence.iter_due_periods(pe, today):
            if (pe.id, target) in realized_exp:
                continue
            if ("expense", pe.id, y, m) in skip_set:
                continue
            items.append(
                PendingItem(
                    kind="expense",
                    ref_id=pe.id,
                    title=pe.title,
                    category=pe.category,
                    amount=pe.amount,
                    period_year=y,
                    period_month=m,
                    occurrence_date=target,
                )
            )
    return items


@router.get("/pending", response_model=PendingResponse)
async def get_pending(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tarihi geçmiş + işaretlenmemiş periyodik gelir ve gider dönemleri."""
    today = datetime.now(_ISTANBUL).date()

    # Skip set (kind, ref_id, year, month)
    skips = (await db.execute(select(RecurringSkip).where(RecurringSkip.user_id == current_user.id))).scalars().all()
    skip_set = {(s.kind, s.ref_id, s.period_year, s.period_month) for s in skips}

    items: list[PendingItem] = []
    items.extend(await _collect_income_pending(db, current_user, today, skip_set))
    items.extend(await _collect_expense_pending(db, current_user, today, skip_set))

    items.sort(key=lambda it: (it.occurrence_date, it.kind, it.ref_id))
    return PendingResponse(items=items)


async def _verify_owned_ref(kind: str, ref_id: int, user: User, db: AsyncSession) -> None:
    """ref_id'nin kullanıcıya ait olduğunu doğrula (IDOR koruması)."""
    if kind == "income":
        q = select(RecurringIncome.id).where(RecurringIncome.id == ref_id, RecurringIncome.user_id == user.id)
    else:
        q = select(PlannedExpense.id).where(PlannedExpense.id == ref_id, PlannedExpense.user_id == user.id)
    if (await db.execute(q)).scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Periyodik kayıt bulunamadı")


@router.post("/skips", response_model=SkipOut, status_code=status.HTTP_201_CREATED)
async def create_skip(
    payload: SkipRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Bir periyodik tanımın belirli dönemini 'gerçekleşmeyecek' işaretle (idempotent)."""
    await _verify_owned_ref(payload.kind, payload.ref_id, current_user, db)
    existing = (
        await db.execute(
            select(RecurringSkip).where(
                RecurringSkip.user_id == current_user.id,
                RecurringSkip.kind == payload.kind,
                RecurringSkip.ref_id == payload.ref_id,
                RecurringSkip.period_year == payload.year,
                RecurringSkip.period_month == payload.month,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    skip = RecurringSkip(
        user_id=current_user.id,
        kind=payload.kind,
        ref_id=payload.ref_id,
        period_year=payload.year,
        period_month=payload.month,
    )
    db.add(skip)
    await db.commit()
    await db.refresh(skip)
    return skip


@router.delete("/skips/{skip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skip(
    skip_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """'Gerçekleşmeyecek' işaretini geri al."""
    res = await db.execute(select(RecurringSkip).where(RecurringSkip.id == skip_id, RecurringSkip.user_id == current_user.id))
    skip = res.scalar_one_or_none()
    if not skip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")
    await db.delete(skip)
    await db.commit()
