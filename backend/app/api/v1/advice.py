from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.models.advice import InvestmentAdvice
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.schemas.advice import AdviceGenerateRequest, AdviceOut

router = APIRouter(prefix="/advice", tags=["advice"])


@router.get("", response_model=list[AdviceOut])
async def list_advice(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InvestmentAdvice)
        .where(InvestmentAdvice.user_id == current_user.id)
        .order_by(desc(InvestmentAdvice.generated_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/generate", response_model=AdviceOut, status_code=status.HTTP_201_CREATED)
async def generate_advice(
    payload: AdviceGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload
    from app.services.advisor import AdvisorService

    snapshot_result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    snapshot = snapshot_result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tavsiye üretmek için önce portföy verisi gerekiyor")

    advisor = AdvisorService()
    advice = await advisor.generate(
        user=current_user,
        snapshot=snapshot,
        horizon=payload.horizon,
    )
    db.add(advice)
    await db.commit()
    await db.refresh(advice)
    return advice
