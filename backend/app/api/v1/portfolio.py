import asyncio
import logging
from datetime import date
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
from app.services.aggregator import fetch_usd_to_tl, fetch_combined_prices, lookup_usd_price
from app.services.exchange.binance import BinanceService
from app.services.exchange.binancetr import BinanceTRService
from app.services.exchange.icrypex import ICrypexService
from app.services.blockchain.sonic import SonicService
from app.services.blockchain.avalanche import AvalanchePChainService, AvalancheCChainService
from app.services.blockchain.ethereum import EthereumService
from app.services.blockchain.algorand import AlgorandService
from app.services.blockchain.bitcoin import BitcoinService
from app.services.blockchain.cardano import CardanoService
from app.services.blockchain.litecoin import LitecoinService
from app.services.blockchain.polkadot import PolkadotService
from app.services.blockchain.solana import SolanaService
from app.services.snapshot import compute_and_save_snapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/usd-rate")
async def get_usd_rate(
    _: User = Depends(get_current_user),
):
    """Anlık USD/TRY kuru (TCMB → Yahoo Finance fallback). Frontend USD karşılığı
    göstermek için kullanır. 5 dk in-memory cache (aggregator katmanında)."""
    rate = await fetch_usd_to_tl()
    return {"usd_try": str(rate)}


@router.post("/snapshot/preview")
async def preview_snapshot(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Snapshot öncesi sağlık kontrolü.

    Tüm kaynakları gather edip toplam + issues döndürür ama **DB'ye yazmaz**.
    Frontend bunu kullanır: issue varsa kullanıcıya popup gösterip onay alır.
    Onay sonrası `POST /portfolio/snapshot` (force=True) ile gerçek kayıt.

    Issues yoksa frontend doğrudan kayıt yapabilir (popup atlanabilir).
    """
    try:
        result = await compute_and_save_snapshot(current_user.id, db, dry_run=True)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Snapshot ön kontrol başarısız: {e}",
        )
    # dry_run=True her zaman dict döner, asla DB'ye yazmaz
    return result


@router.post("/snapshot", response_model=SnapshotOut, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mevcut kullanici icin manuel olarak portfoy snapshot'i alir.

    Otomatik haftalik job (Pazar 23:00) ile ayni mantigi calistirir; ayni gun
    icinde tekrar cagrilirsa eski snapshot silinip yenisi olusturulur.

    `force=true` query parametresi: kullanıcı uyarıları onayladıktan sonra
    bu endpoint çağrılır. force=false (varsayılan) için preview endpoint'i
    önce çağrılmalı; issue varsa popup'ta onay alınır.
    """
    try:
        snapshot = await compute_and_save_snapshot(current_user.id, db, force=force)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Snapshot alinamadi: {e}",
        )
    if isinstance(snapshot, dict):
        # dry_run değil ama somehow dict döndü — beklenmeyen durum
        raise HTTPException(status_code=500, detail="Snapshot kaydedilemedi")
    # Asset position'lari donulen response icin tekrar yukle
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.id == snapshot.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
    )
    return result.scalar_one()


@router.delete("/snapshot/{snapshot_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snapshot(
    snapshot_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirli bir tarihteki snapshot'i siler. Yanlış kaydedilmiş (ör. timezone)
    snapshot'ları temizlemek için. Cascade ile asset_positions da silinir."""
    result = await db.execute(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == current_user.id,
            PortfolioSnapshot.snapshot_date == snapshot_date,
        )
    )
    snap = result.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot bulunamadı")
    await db.delete(snap)
    await db.commit()


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
        fetch_combined_prices([
            "S", "AVAX", "ETH", "BTC", "SOL", "ADA", "DOT", "ALGO", "LTC",
            "LINK", "USDT", "USDC",
        ]),
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
            elif wallet.chain == "bitcoin":
                svc = BitcoinService(wallet.address, wid)
            elif wallet.chain == "solana":
                svc = SolanaService(wallet.address, wid)
            elif wallet.chain == "litecoin":
                svc = LitecoinService(wallet.address, wid)
            elif wallet.chain == "algorand":
                svc = AlgorandService(wallet.address, wid)
            elif wallet.chain == "cardano":
                svc = CardanoService(wallet.address, wid)
            elif wallet.chain == "polkadot":
                svc = PolkadotService(wallet.address, wid)
            else:
                return []
            assets = await svc.fetch()
            out = []
            for a in assets:
                usd = lookup_usd_price(a.symbol, prices)
                # Snapshot ile tutarlı: pending_rewards da toplama dahil
                total_qty = a.liquid_quantity + a.staked_quantity + a.pending_rewards
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
