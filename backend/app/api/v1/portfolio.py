import asyncio
import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.core.security import decrypt_secret
from app.models.integration import Integration, WalletAddress
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.schemas.portfolio import (
    CryptoPositionOut,
    CryptoResponse,
    PortfolioBreakdown,
    PortfolioChanges,
    SnapshotOut,
    StakingPosition,
    WalletPositionOut,
    WalletResponse,
)
from app.services.aggregator import fetch_usd_to_tl, fetch_spot_prices
from app.services.exchange.binance import BinanceService
from app.services.exchange.binancetr import BinanceTRService
from app.services.exchange.icrypex import ICrypexService
from app.services.blockchain.sonic import SonicService
from app.services.blockchain.avalanche import AvalanchePChainService, AvalancheCChainService
from app.services.blockchain.ethereum import EthereumService

logger = logging.getLogger(__name__)
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


@router.get("/crypto", response_model=CryptoResponse)
async def get_crypto_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.provider.in_(["binance", "binancetr", "icrypex"]),
            Integration.is_active.is_(True),
        )
    )
    integrations = result.scalars().all()
    if not integrations:
        return CryptoResponse(positions=[], errors={})

    usd_tl = await fetch_usd_to_tl()
    all_assets = []
    errors: dict[str, str] = {}

    for intg in integrations:
        try:
            api_key = decrypt_secret(intg.encrypted_key)
            api_secret = decrypt_secret(intg.encrypted_secret) if intg.encrypted_secret else ""
            if intg.provider == "binance":
                svc = BinanceService(api_key, api_secret)
            elif intg.provider == "binancetr":
                session_token = decrypt_secret(intg.encrypted_extra) if intg.encrypted_extra else ""
                svc = BinanceTRService(api_key, api_secret, session_token)
            else:
                svc = ICrypexService(api_key, api_secret)
            assets = await svc.fetch()
            all_assets.extend(assets)
        except Exception as e:
            logger.error("Kripto fetch hatası [%s]: %s", intg.provider, e)
            errors[intg.provider] = str(e)

    positions = [
        CryptoPositionOut(
            provider=a.provider,
            symbol=a.symbol,
            liquid_quantity=a.liquid_quantity,
            staked_quantity=a.staked_quantity,
            unit_price_usd=a.unit_price_usd,
            unit_price_tl=(a.unit_price_usd * usd_tl).quantize(Decimal("0.01")),
            total_value_tl=(
                (a.liquid_quantity + a.staked_quantity) * a.unit_price_usd * usd_tl
            ).quantize(Decimal("0.01")),
        )
        for a in all_assets
    ]
    return CryptoResponse(positions=positions, errors=errors)


@router.get("/wallets", response_model=WalletResponse)
async def get_wallet_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WalletAddress).where(
            WalletAddress.user_id == current_user.id,
            WalletAddress.is_active.is_(True),
        )
    )
    wallets = result.scalars().all()
    if not wallets:
        return WalletResponse(positions=[], errors={})

    usd_tl, prices = await asyncio.gather(
        fetch_usd_to_tl(),
        fetch_spot_prices(["S", "AVAX", "ETH"]),
    )

    all_positions: list[WalletPositionOut] = []
    errors: dict[str, str] = {}

    async def fetch_wallet(wallet: WalletAddress) -> list[WalletPositionOut]:
        try:
            wid = str(wallet.id)
            if wallet.chain == "sonic":
                svc = SonicService(wallet.address, wid)
            elif wallet.chain == "avalanche_p":
                svc = AvalanchePChainService(wallet.address, wid)
            elif wallet.chain == "avalanche_c":
                svc = AvalancheCChainService(wallet.address, wid)
            elif wallet.chain == "ethereum":
                svc = EthereumService(wallet.address, wid)
            else:
                return []
            assets = await svc.fetch()
            out = []
            for a in assets:
                usd = prices.get(a.symbol, Decimal(0))
                total_qty = a.liquid_quantity + a.staked_quantity
                out.append(WalletPositionOut(
                    wallet_id=wid,
                    chain=wallet.chain,
                    address=wallet.address,
                    label=wallet.label,
                    symbol=a.symbol,
                    liquid_quantity=a.liquid_quantity,
                    staked_quantity=a.staked_quantity,
                    pending_rewards=a.pending_rewards,
                    unit_price_usd=usd,
                    unit_price_tl=(usd * usd_tl).quantize(Decimal("0.01")),
                    total_value_tl=(total_qty * usd * usd_tl).quantize(Decimal("0.01")),
                ))
            return out
        except Exception as e:
            key = f"{wallet.chain}:{wallet.address[:10]}"
            logger.error("Cüzdan fetch hatası [%s]: %s", key, e)
            errors[key] = str(e)
            return []

    results = await asyncio.gather(*[fetch_wallet(w) for w in wallets])
    for r in results:
        all_positions.extend(r)

    return WalletResponse(positions=all_positions, errors=errors)


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
