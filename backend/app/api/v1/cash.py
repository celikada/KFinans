"""Nakit/banka hesabı CRUD endpoint'leri."""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.cash import CashHolding
from app.models.user import User
from app.schemas.cash import CashCreate, CashOut, CashSummaryOut, CashUpdate
from app.services.aggregator import fetch_usd_to_tl

router = APIRouter(prefix="/cash", tags=["cash"])


async def _amount_to_tl(amount: Decimal, currency: str) -> Decimal:
    """Currency → TL dönüşüm. TRY ise 1:1, USD/EUR/GBP için TCMB+fallback."""
    if currency == "TRY":
        return amount
    if currency in ("USD", "EUR", "GBP"):
        # USD/TRY üzerinden — EUR ve GBP için yaklaşık 1:1 USD varsayım
        # (precision için ileride ayrı kur servisi eklenecek)
        usd_tl = await fetch_usd_to_tl()
        return (amount * usd_tl).quantize(Decimal("0.01"))
    return amount


@router.get("", response_model=CashSummaryOut)
async def list_cash(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rows = (await db.execute(
        select(CashHolding)
        .where(CashHolding.user_id == current_user.id)
        .order_by(CashHolding.id)
    )).scalars().all()

    out: list[CashOut] = []
    total_tl = Decimal(0)
    for r in rows:
        tl = await _amount_to_tl(r.amount, r.currency)
        total_tl += tl
        out.append(CashOut(
            id=r.id, label=r.label, amount=r.amount, currency=r.currency,
            notes=r.notes, updated_at=r.updated_at, amount_tl=tl,
        ))
    return CashSummaryOut(holdings=out, total_tl=total_tl.quantize(Decimal("0.01")))


@router.post("", response_model=CashOut, status_code=status.HTTP_201_CREATED)
async def create_cash(
    payload: CashCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    holding = CashHolding(
        user_id=current_user.id,
        label=payload.label,
        amount=payload.amount,
        currency=payload.currency,
        notes=payload.notes,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    tl = await _amount_to_tl(holding.amount, holding.currency)
    return CashOut(
        id=holding.id, label=holding.label, amount=holding.amount,
        currency=holding.currency, notes=holding.notes,
        updated_at=holding.updated_at, amount_tl=tl,
    )


@router.put("/{cash_id}", response_model=CashOut)
async def update_cash(
    cash_id: int,
    payload: CashUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    holding = (await db.execute(
        select(CashHolding).where(
            CashHolding.id == cash_id, CashHolding.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=404, detail="Nakit kaydı bulunamadı")
    if payload.label is not None:
        holding.label = payload.label
    if payload.amount is not None:
        holding.amount = payload.amount
    if payload.currency is not None:
        holding.currency = payload.currency
    if payload.notes is not None:
        holding.notes = payload.notes
    await db.commit()
    await db.refresh(holding)
    tl = await _amount_to_tl(holding.amount, holding.currency)
    return CashOut(
        id=holding.id, label=holding.label, amount=holding.amount,
        currency=holding.currency, notes=holding.notes,
        updated_at=holding.updated_at, amount_tl=tl,
    )


@router.delete("/{cash_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cash(
    cash_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        delete(CashHolding).where(
            CashHolding.id == cash_id, CashHolding.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Nakit kaydı bulunamadı")
    await db.commit()
