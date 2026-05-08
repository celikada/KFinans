from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.deps import get_db, get_current_user
from app.models.advice import InvestmentAdvice
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.schemas.advice import AdviceGenerateRequest, AdviceOut
from app.services.audit import AuditAction, log_audit

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
    request: Request,
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

    # AI-004 (FAZ H): Audit log — KVKK m.12 uclu taraf veri aktarimi izleme.
    # Anthropic API'ye portfoy ozeti gonderildigi icin her uretim audit'lenmeli.
    await log_audit(
        db, request,
        action=AuditAction.ADVICE_GENERATE,
        user_id=current_user.id,
        resource=f"advice:snapshot={snapshot.id}",
        extra={
            "horizon": payload.horizon,
            "model": settings.claude_model,
            "prompt_tokens": advice.prompt_tokens,
            "completion_tokens": advice.completion_tokens,
            "snapshot_date": snapshot.snapshot_date.isoformat(),
        },
    )

    await db.commit()
    await db.refresh(advice)
    return advice
