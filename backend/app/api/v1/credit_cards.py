"""Kredi kartı CRUD endpoint'leri (tanım + dönem içi borç)."""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.credit_card import CreditCard
from app.models.user import User
from app.schemas.credit_card import (
    CreditCardCreate,
    CreditCardOut,
    CreditCardSummaryOut,
    CreditCardUpdate,
)

router = APIRouter(prefix="/credit-cards", tags=["credit-cards"])


@router.get("", response_model=CreditCardSummaryOut)
async def list_credit_cards(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tüm kartları + toplam dönem içi borç özeti."""
    result = await db.execute(
        select(CreditCard)
        .where(CreditCard.user_id == current_user.id)
        .order_by(CreditCard.name)
    )
    cards = result.scalars().all()
    total_debt = sum((Decimal(c.current_period_debt) for c in cards), Decimal(0))
    return CreditCardSummaryOut(
        cards=cards,
        total_current_period_debt=total_debt,
    )


@router.post("", response_model=CreditCardOut, status_code=status.HTTP_201_CREATED)
async def create_credit_card(
    payload: CreditCardCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    card = CreditCard(
        user_id=current_user.id,
        name=payload.name,
        bank_name=payload.bank_name,
        last_4=payload.last_4,
        credit_limit=payload.credit_limit,
        statement_day=payload.statement_day,
        payment_due_day=payload.payment_due_day,
        current_period_debt=payload.current_period_debt,
        notes=payload.notes,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.put("/{card_id}", response_model=CreditCardOut)
async def update_credit_card(
    card_id: int,
    payload: CreditCardUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(CreditCard).where(
            CreditCard.id == card_id, CreditCard.user_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kart bulunamadı")

    for attr in ("name", "bank_name", "last_4", "credit_limit",
                 "statement_day", "payment_due_day", "current_period_debt", "notes"):
        v = getattr(payload, attr)
        if v is not None:
            setattr(card, attr, v)

    await db.commit()
    await db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credit_card(
    card_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(CreditCard).where(
            CreditCard.id == card_id, CreditCard.user_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kart bulunamadı")
    await db.delete(card)
    await db.commit()
