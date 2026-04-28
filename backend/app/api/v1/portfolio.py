from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.schemas.portfolio import SnapshotOut, PortfolioChanges, PortfolioBreakdown, StakingPosition

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=SnapshotOut)
async def get_current_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Henüz portföy verisi yok")
    return snapshot


@router.get("/history", response_model=list[SnapshotOut])
async def get_portfolio_history(
    limit: int = 12,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/changes", response_model=PortfolioChanges)
async def get_portfolio_changes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Son 5 snapshot yeterli (WoW + MoM için)
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(5)
    )
    snapshots = result.scalars().all()
    if not snapshots:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Henüz portföy verisi yok")

    from app.services.aggregator import calculate_changes
    return calculate_changes(snapshots)


@router.get("/breakdown", response_model=PortfolioBreakdown)
async def get_portfolio_breakdown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Henüz portföy verisi yok")

    from app.services.aggregator import calculate_breakdown
    return calculate_breakdown(snapshot)


class TefasHolding(BaseModel):
    code: str
    quantity: float
    name: str = ""


class TefasPositionOut(BaseModel):
    code: str
    name: str
    quantity: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal


@router.post("/tefas/preview", response_model=list[TefasPositionOut])
async def tefas_preview(
    holdings: list[TefasHolding],
    _: Annotated[User, Depends(get_current_user)],
):
    """Girilen fon kodları için TEFAS'tan canlı fiyat çeker, kaydetmez."""
    from app.services.tefas import TefasService
    svc = TefasService([{"code": h.code, "quantity": h.quantity, "name": h.name} for h in holdings])
    try:
        assets = await svc.fetch()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return [
        TefasPositionOut(
            code=a.symbol,
            name=a.name,
            quantity=a.liquid_quantity,
            unit_price_tl=a.unit_price_tl,
            total_value_tl=a.liquid_quantity * a.unit_price_tl,
        )
        for a in assets
    ]


@router.get("/staking", response_model=list[StakingPosition])
async def get_staking_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Henüz portföy verisi yok")

    from app.services.aggregator import extract_staking_positions
    return extract_staking_positions(snapshot)
