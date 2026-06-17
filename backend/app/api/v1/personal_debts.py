"""Kişisel borç/alacak (kredi kartı dışı) CRUD — Budget empty.xlsx "Debt" sayfası."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.personal_debt import PersonalDebt
from app.models.user import User
from app.schemas.personal_debt import (
    PersonalDebtCreate,
    PersonalDebtListOut,
    PersonalDebtOut,
    PersonalDebtUpdate,
)
from app.services import currency as currency_svc
from app.services import display_currency as display_svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/personal-debts", tags=["personal-debts"])


def _to_out(d: PersonalDebt, display_ccy: str, rates: dict[str, Decimal]) -> PersonalDebtOut:
    amount_display = display_svc.convert_forecast(Decimal(d.amount), d.currency, display_ccy, rates)
    return PersonalDebtOut(
        id=d.id,
        counterparty=d.counterparty,
        kind=d.kind,
        amount=d.amount,
        currency=d.currency,
        due_date=d.due_date,
        note=d.note,
        settled_at=d.settled_at,
        amount_display=amount_display,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


@router.get("", response_model=PersonalDebtListOut)
async def list_personal_debts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    kind: Annotated[Optional[str], Query()] = None,
    include_settled: Annotated[bool, Query()] = False,
    display: Annotated[str | None, Query()] = None,
):
    display_ccy = display_svc.normalize_display(display, current_user.default_currency)
    rates = await currency_svc.fetch_rates()

    stmt = select(PersonalDebt).where(PersonalDebt.user_id == current_user.id)
    if kind in ("debt", "receivable"):
        stmt = stmt.where(PersonalDebt.kind == kind)
    if not include_settled:
        stmt = stmt.where(PersonalDebt.settled_at.is_(None))
    stmt = stmt.order_by(PersonalDebt.settled_at.is_(None).desc(), PersonalDebt.due_date.asc().nullslast(), PersonalDebt.created_at.desc())

    rows = (await db.execute(stmt)).scalars().all()
    items = [_to_out(d, display_ccy, rates) for d in rows]

    # Açık bakiye özetleri (settled olmayanlar)
    total_debt = sum(
        (it.amount_display for it, d in zip(items, rows, strict=True) if d.kind == "debt" and d.settled_at is None),
        Decimal(0),
    )
    total_receivable = sum(
        (it.amount_display for it, d in zip(items, rows, strict=True) if d.kind == "receivable" and d.settled_at is None),
        Decimal(0),
    )
    return PersonalDebtListOut(
        display_currency=display_ccy,
        items=items,
        total_debt_display=display_svc.quantize_tl(total_debt),
        total_receivable_display=display_svc.quantize_tl(total_receivable),
        net_display=display_svc.quantize_tl(total_receivable - total_debt),
    )


@router.post("", response_model=PersonalDebtOut, status_code=status.HTTP_201_CREATED)
async def create_personal_debt(
    payload: PersonalDebtCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    currency = payload.currency or current_user.default_currency or "TRY"
    debt = PersonalDebt(
        user_id=current_user.id,
        counterparty=payload.counterparty,
        kind=payload.kind,
        amount=payload.amount,
        currency=currency,
        due_date=payload.due_date,
        note=payload.note,
    )
    db.add(debt)
    await db.commit()
    await db.refresh(debt)
    rates = await currency_svc.fetch_rates()
    return _to_out(debt, display_svc.normalize_display(None, current_user.default_currency), rates)


async def _get_owned(db: AsyncSession, user_id, debt_id: int) -> PersonalDebt:
    row = (await db.execute(select(PersonalDebt).where(PersonalDebt.id == debt_id, PersonalDebt.user_id == user_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")
    return row


@router.put("/{debt_id}", response_model=PersonalDebtOut)
async def update_personal_debt(
    debt_id: int,
    payload: PersonalDebtUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    debt = await _get_owned(db, current_user.id, debt_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(debt, field, value)
    await db.commit()
    await db.refresh(debt)
    rates = await currency_svc.fetch_rates()
    return _to_out(debt, display_svc.normalize_display(None, current_user.default_currency), rates)


@router.post("/{debt_id}/settle", response_model=PersonalDebtOut)
async def settle_personal_debt(
    debt_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    debt = await _get_owned(db, current_user.id, debt_id)
    if debt.settled_at is None:
        debt.settled_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(debt)
    rates = await currency_svc.fetch_rates()
    return _to_out(debt, display_svc.normalize_display(None, current_user.default_currency), rates)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_personal_debt(
    debt_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    debt = await _get_owned(db, current_user.id, debt_id)
    await db.delete(debt)
    await db.commit()
