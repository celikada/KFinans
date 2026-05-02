from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User

router = APIRouter(prefix="/user/goal", tags=["goal"])

FREEDOM_MULTIPLIER = 300


class GoalIn(BaseModel):
    monthly_expense_goal: Decimal = Field(..., gt=0, le=9_999_999.99)


class GoalOut(BaseModel):
    monthly_expense_goal: Decimal | None
    freedom_target: Decimal | None        # monthly × 300
    portfolio_value: Decimal | None       # son snapshot
    passive_income_potential: Decimal | None  # portfolio / 300
    progress_pct: float | None            # portfolio / freedom_target × 100
    months_covered: float | None          # portfolio / monthly (kaç ay karşılıyor)


@router.get("", response_model=GoalOut)
async def get_goal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    goal = current_user.monthly_expense_goal

    # Son snapshot'tan portföy değeri
    snap_q = await db.execute(
        select(PortfolioSnapshot.total_value_tl)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    row = snap_q.scalar_one_or_none()
    portfolio = Decimal(str(row)) if row is not None else None

    if goal is None:
        return GoalOut(
            monthly_expense_goal=None,
            freedom_target=None,
            portfolio_value=portfolio,
            passive_income_potential=portfolio / FREEDOM_MULTIPLIER if portfolio else None,
            progress_pct=None,
            months_covered=None,
        )

    freedom_target = goal * FREEDOM_MULTIPLIER
    passive_income = (portfolio / FREEDOM_MULTIPLIER) if portfolio else None
    progress_pct = (float(portfolio) / float(freedom_target) * 100) if portfolio else None
    months_covered = (float(portfolio) / float(goal)) if portfolio else None

    return GoalOut(
        monthly_expense_goal=goal,
        freedom_target=freedom_target,
        portfolio_value=portfolio,
        passive_income_potential=passive_income,
        progress_pct=round(progress_pct, 2) if progress_pct is not None else None,
        months_covered=round(months_covered, 1) if months_covered is not None else None,
    )


@router.put("", response_model=GoalOut)
async def set_goal(
    payload: GoalIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.monthly_expense_goal = payload.monthly_expense_goal
    await db.commit()
    await db.refresh(current_user)
    return await get_goal(current_user, db)
