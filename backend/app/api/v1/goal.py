from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.services import currency as currency_svc
from app.services import live_cache as live_cache_svc

router = APIRouter(prefix="/user/goal", tags=["goal"])

FREEDOM_MULTIPLIER = 300
GoalCurrency = Literal["TRY", "USD", "EUR", "GBP"]
SUPPORTED_CURRENCIES: tuple[str, ...] = ("TRY", "USD", "EUR", "GBP")


async def _rate_to_tl(currency: str) -> Decimal:
    """Verilen para biriminin TL karsiligi (1 birim = X TL).

    v0.3.0: ortak `services/currency.py` util'inden kur haritasi alir (DRY).
    fetch_rates eksik kur icin USD fallback uygular; yine de bulunamazsa
    (TRY haricinde) 503 — goal hesabi kur olmadan yanlis olur.
    """
    if currency == "TRY":
        return Decimal("1")
    # fallback=False: goal hesabi kur olmadan yanlis olacagindan USD yaklasik
    # cevrim istemiyoruz — TCMB ilgili dovizi vermiyorsa 503 (eski davranis).
    rates = await currency_svc.fetch_rates(fallback=False)
    rate = rates.get(currency)
    if not rate or rate <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{currency}/TRY kuru alınamadı",
        )
    return rate


class GoalIn(BaseModel):
    amount: Decimal = Field(..., gt=0, le=99_999_999.99)
    currency: GoalCurrency = "TRY"


class GoalOut(BaseModel):
    goal_amount: Decimal | None = None  # orijinal para biriminde
    goal_currency: str
    rate_to_tl: Decimal | None = None  # 1 birim = X TL
    monthly_tl: Decimal | None = None  # TL karsiligi
    freedom_target_tl: Decimal | None = None  # monthly_tl × 300
    portfolio_value: Decimal | None = None  # son snapshot TL
    passive_income_tl: Decimal | None = None  # portfolio / 300
    passive_income_foreign: Decimal | None = None  # pasif gelir / kur (hedef para biriminde)
    progress_pct: float | None = None
    months_covered: float | None = None


@router.get("", response_model=GoalOut)
async def get_goal(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Goal ilerlemesi CANLI portföy toplamından hesaplanır (dashboard "Toplam Portföy"
    # ile birebir: 6 ağır bölüm + BES + Nakit), snapshot beklemeden güncel kalır.
    # Bug (2026-06-23): eskiden yalnız son SNAPSHOT kullanılıyordu; kullanıcı yeni
    # snapshot almadıkça goal eski/küçük değerde takılıyordu (ör. canlı %22 iken %5).
    # `preview_snapshot_from_cache` cache+DB'den dış-çağrısız tam toplamı verir;
    # cache yok/bozuksa son snapshot'a fallback (eski davranış, geriye uyumlu).
    portfolio_dec: Decimal | None = None
    try:
        preview = await live_cache_svc.preview_snapshot_from_cache(current_user.id, db)
        total_str = preview.get("total_value_tl")
        if total_str is not None:
            val = Decimal(str(total_str))
            if val > 0:
                portfolio_dec = val
    except Exception:
        portfolio_dec = None

    if portfolio_dec is None:
        snap_q = await db.execute(
            select(PortfolioSnapshot.total_value_tl)
            .where(PortfolioSnapshot.user_id == current_user.id)
            .order_by(desc(PortfolioSnapshot.snapshot_date))
            .limit(1)
        )
        portfolio = snap_q.scalar_one_or_none()
        portfolio_dec = Decimal(str(portfolio)) if portfolio is not None else None

    amount = current_user.goal_amount
    currency = current_user.goal_currency or "TRY"

    if amount is None:
        passive = (portfolio_dec / FREEDOM_MULTIPLIER) if portfolio_dec else None
        return GoalOut(
            goal_amount=None,
            goal_currency=currency,
            rate_to_tl=None,
            monthly_tl=None,
            freedom_target_tl=None,
            portfolio_value=portfolio_dec,
            passive_income_tl=passive,
            passive_income_foreign=None,
            progress_pct=None,
            months_covered=None,
        )

    rate = await _rate_to_tl(currency)
    monthly_tl = (amount * rate).quantize(Decimal("0.01"))
    freedom_target = (monthly_tl * FREEDOM_MULTIPLIER).quantize(Decimal("0.01"))
    passive_tl = (portfolio_dec / FREEDOM_MULTIPLIER).quantize(Decimal("0.01")) if portfolio_dec else None
    passive_foreign = (passive_tl / rate).quantize(Decimal("0.01")) if passive_tl else None
    progress_pct = round(float(portfolio_dec) / float(freedom_target) * 100, 2) if portfolio_dec else None
    months_covered = round(float(portfolio_dec) / float(monthly_tl), 1) if portfolio_dec else None

    return GoalOut(
        goal_amount=amount,
        goal_currency=currency,
        rate_to_tl=rate,
        monthly_tl=monthly_tl,
        freedom_target_tl=freedom_target,
        portfolio_value=portfolio_dec,
        passive_income_tl=passive_tl,
        passive_income_foreign=passive_foreign,
        progress_pct=progress_pct,
        months_covered=months_covered,
    )


@router.put("", response_model=GoalOut)
async def set_goal(
    payload: GoalIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    current_user.goal_amount = payload.amount
    current_user.goal_currency = payload.currency
    await db.commit()
    await db.refresh(current_user)
    return await get_goal(current_user, db)
