"""Faz 3 kredi sistemi endpoint'leri.

Asama 1 (mevcut): GET /credits — bakiye + sayfalanan kredi defteri (IDOR korumali).
Asama 2 (iyzico key gelince): POST /credits/checkout + POST /credits/webhook.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.credit_transaction import CreditTransaction
from app.models.user import User
from app.schemas.credit import CreditBalanceOut, CreditTransactionOut
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("", response_model=CreditBalanceOut)
async def get_credits(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Kullanicinin anlik kredi bakiyesi + sayfalanan hareket gecmisi.

    IDOR korumasi: daima current_user.id filtresi — kullanici yalnizca kendi
    defterini gorur. PERF-001: PaginatedResponse[T] (items + total_count + has_next).
    """
    base = select(CreditTransaction).where(CreditTransaction.user_id == current_user.id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    items = (await db.execute(base.order_by(desc(CreditTransaction.created_at)).offset(offset).limit(limit))).scalars().all()

    return CreditBalanceOut(
        balance=current_user.credit_balance or 0,
        transactions=PaginatedResponse[CreditTransactionOut](
            items=[CreditTransactionOut.model_validate(i) for i in items],
            total_count=total,
            limit=limit,
            offset=offset,
            has_next=(offset + len(items)) < total,
        ),
    )
