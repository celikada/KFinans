"""Kıymetli maden (altın/gümüş) CRUD endpoint'leri."""
import logging
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.commodity import CommodityHolding
from app.models.user import User
from app.schemas.commodity import (
    CommodityCreate,
    CommodityOut,
    CommodityPositionOut,
    CommoditySummaryOut,
    CommodityUpdate,
)
from app.services.commodity import calculate_holding_value, fetch_metal_prices

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio/commodities", tags=["commodities"])


@router.get("", response_model=CommoditySummaryOut)
async def list_commodities(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommoditySummaryOut:
    """Kullanıcının tüm kıymetli maden varlıklarını anlık fiyatlarla döndürür."""
    result = await db.execute(
        select(CommodityHolding)
        .where(CommodityHolding.user_id == current_user.id)
        .order_by(CommodityHolding.created_at)
    )
    holdings = result.scalars().all()

    prices = await fetch_metal_prices()
    gold_price = prices["gold"]
    silver_price = prices["silver"]

    positions: list[CommodityPositionOut] = []
    total_gold_gram = Decimal("0")
    total_silver_gram = Decimal("0")
    total_value_tl = Decimal("0")

    for h in holdings:
        try:
            val = calculate_holding_value(h, gold_price, silver_price)
        except ValueError as exc:
            logger.error("Holding %d değer hesaplanamadı: %s", h.id, exc)
            continue

        gram_eq = val["gram_equivalent"]
        value_tl = val["total_value_tl"]

        if h.metal == "gold":
            total_gold_gram += gram_eq
        else:
            total_silver_gram += gram_eq
        total_value_tl += value_tl

        positions.append(
            CommodityPositionOut(
                id=h.id,
                unit_type=h.unit_type,
                metal=h.metal,
                biga_code=h.biga_code,
                coin_type=h.coin_type,
                quantity=h.quantity,
                notes=h.notes,
                created_at=h.created_at,
                gram_equivalent=gram_eq,
                total_value_tl=value_tl,
                gold_price_tl=gold_price,
                silver_price_tl=silver_price,
            )
        )

    return CommoditySummaryOut(
        positions=positions,
        total_gold_gram=total_gold_gram.quantize(Decimal("0.0001")),
        total_silver_gram=total_silver_gram.quantize(Decimal("0.0001")),
        total_value_tl=total_value_tl.quantize(Decimal("0.01")),
        gold_price_tl=gold_price,
        silver_price_tl=silver_price,
    )


@router.post("", response_model=CommodityOut, status_code=status.HTTP_201_CREATED)
async def create_commodity(
    payload: CommodityCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommodityHolding:
    """Yeni kıymetli maden varlığı ekler."""
    holding = CommodityHolding(
        user_id=current_user.id,
        unit_type=payload.unit_type,
        metal=payload.metal,
        biga_code=payload.biga_code,
        coin_type=payload.coin_type,
        quantity=payload.quantity,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


@router.put("/{holding_id}", response_model=CommodityOut)
async def update_commodity(
    holding_id: int,
    payload: CommodityUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommodityHolding:
    """Kıymetli maden varlığının miktar ve notunu günceller."""
    result = await db.execute(
        select(CommodityHolding).where(
            CommodityHolding.id == holding_id,
            CommodityHolding.user_id == current_user.id,
        )
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")

    if payload.quantity is not None:
        holding.quantity = payload.quantity
    if payload.notes is not None:
        holding.notes = payload.notes.strip() or None

    await db.commit()
    await db.refresh(holding)
    return holding


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commodity(
    holding_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Kıymetli maden varlığını siler."""
    result = await db.execute(
        select(CommodityHolding).where(
            CommodityHolding.id == holding_id,
            CommodityHolding.user_id == current_user.id,
        )
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")
    await db.delete(holding)
    await db.commit()
