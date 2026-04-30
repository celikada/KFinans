"""Portfoy snapshot servisi.

Bir kullanicinin tum varlik kaynaklarindan veriyi paralel olarak ceker,
TL'ye normalize eder ve PortfolioSnapshot + AssetPosition kayitlari olusturur.

Hem APScheduler haftalik job'i hem de manuel /portfolio/snapshot endpoint'i
bu modulu kullanir.
"""
import asyncio
import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.models.integration import Integration, WalletAddress
from app.models.portfolio import AssetPosition, PortfolioSnapshot
from app.models.stock import StockHolding
from app.models.tefas import TefasHolding
from app.services.aggregator import (
    fetch_gbp_to_usd,
    fetch_usd_to_tl,
    to_asset_position,
)
from app.services.base import AssetData
from app.services.blockchain.avalanche import AvalancheCChainService, AvalanchePChainService
from app.services.blockchain.ethereum import EthereumService
from app.services.blockchain.sonic import SonicService
from app.services.exchange.binance import BinanceService
from app.services.exchange.binancetr import BinanceTRService
from app.services.exchange.icrypex import ICrypexService
from app.services.stocks import fetch_stock_quotes
from app.services.tefas import TefasService

logger = logging.getLogger(__name__)


async def _gather_crypto_assets(integrations: list[Integration]) -> list[AssetData]:
    out: list[AssetData] = []
    for intg in integrations:
        try:
            api_key = decrypt_secret(intg.encrypted_key)
            api_secret = decrypt_secret(intg.encrypted_secret) if intg.encrypted_secret else ""
            if intg.provider == "binance":
                svc = BinanceService(api_key, api_secret)
            elif intg.provider == "binancetr":
                session_token = decrypt_secret(intg.encrypted_extra) if intg.encrypted_extra else ""
                svc = BinanceTRService(api_key, api_secret, session_token)
            elif intg.provider == "icrypex":
                svc = ICrypexService(api_key, api_secret)
            else:
                continue
            out.extend(await svc.fetch())
        except Exception as e:
            logger.warning("Snapshot: kripto fetch hatasi [%s]: %s", intg.provider, e)
    return out


async def _gather_wallet_assets(wallets: list[WalletAddress]) -> list[AssetData]:
    async def _fetch_one(wallet: WalletAddress) -> list[AssetData]:
        wid = str(wallet.id)
        try:
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
            return await svc.fetch()
        except Exception as e:
            logger.warning("Snapshot: cuzdan fetch hatasi [%s:%s]: %s", wallet.chain, wallet.address[:10], e)
            return []

    results = await asyncio.gather(*[_fetch_one(w) for w in wallets])
    return [a for r in results for a in r]


async def _gather_tefas_assets(holdings: list[TefasHolding]) -> list[AssetData]:
    if not holdings:
        return []
    payload = [{"code": h.code, "quantity": float(h.quantity), "name": h.name} for h in holdings]
    try:
        return await TefasService(payload).fetch()
    except Exception as e:
        logger.warning("Snapshot: tefas fetch hatasi: %s", e)
        return []


async def _gather_stock_assets(
    holdings: list[StockHolding], usd_tl: Decimal, gbp_usd: Decimal
) -> list[AssetData]:
    if not holdings:
        return []
    tickers = [h.ticker for h in holdings]
    try:
        quotes = await fetch_stock_quotes(tickers)
    except Exception as e:
        logger.warning("Snapshot: hisse fetch hatasi: %s", e)
        return []

    out: list[AssetData] = []
    for h in holdings:
        q = quotes.get(h.ticker)
        if not q:
            continue
        if q.currency == "TRY":
            price_tl = q.price
        elif q.currency == "GBp":
            price_tl = (q.price / Decimal("100")) * gbp_usd * usd_tl
        else:
            price_tl = q.price * usd_tl
        out.append(AssetData(
            symbol=q.ticker,
            name=h.name or q.name,
            provider="stock",
            asset_type="stock",
            source_type="stock",
            liquid_quantity=Decimal(str(h.quantity)),
            unit_price_tl=price_tl.quantize(Decimal("0.0001")),
        ))
    return out


async def compute_and_save_snapshot(user_id: uuid.UUID, db: AsyncSession) -> PortfolioSnapshot:
    """Tek bir kullanici icin tum varlik kaynaklarindan snapshot alir.

    Ayni gune ait mevcut snapshot varsa silinir (idempotent — manuel
    tetiklemeler veya yeniden cagri durumunda zincirleme kayit olusmaz).
    """
    today = date.today()

    # Mevcut bugune ait snapshot'i temizle (cascade ile asset_positions da silinir)
    existing_q = await db.execute(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.snapshot_date == today,
        )
    )
    for old in existing_q.scalars().all():
        await db.delete(old)
    await db.flush()

    # Tum kaynaklari paralel cek
    intg_q, wallet_q, tefas_q, stock_q = await asyncio.gather(
        db.execute(
            select(Integration).where(
                Integration.user_id == user_id, Integration.is_active.is_(True)
            )
        ),
        db.execute(
            select(WalletAddress).where(
                WalletAddress.user_id == user_id, WalletAddress.is_active.is_(True)
            )
        ),
        db.execute(select(TefasHolding).where(TefasHolding.user_id == user_id)),
        db.execute(select(StockHolding).where(StockHolding.user_id == user_id)),
    )
    integrations = intg_q.scalars().all()
    wallets = wallet_q.scalars().all()
    tefas_holdings = tefas_q.scalars().all()
    stock_holdings = stock_q.scalars().all()

    # Doviz kurlari
    try:
        usd_tl, gbp_usd = await asyncio.gather(fetch_usd_to_tl(), fetch_gbp_to_usd())
    except Exception as e:
        logger.warning("Snapshot: doviz kuru cekilemedi, fallback 1.0: %s", e)
        usd_tl, gbp_usd = Decimal("1"), Decimal("1")

    # Tum kaynaklardan asset'leri topla (paralel)
    crypto_assets, wallet_assets, tefas_assets, stock_assets = await asyncio.gather(
        _gather_crypto_assets(integrations),
        _gather_wallet_assets(wallets),
        _gather_tefas_assets(tefas_holdings),
        _gather_stock_assets(stock_holdings, usd_tl, gbp_usd),
    )
    all_assets: list[AssetData] = (
        list(crypto_assets) + list(wallet_assets) + list(tefas_assets) + list(stock_assets)
    )

    # Toplam degeri hesapla (weight_pct icin gerekli)
    total_tl = Decimal(0)
    for a in all_assets:
        price_tl = a.unit_price_tl if a.unit_price_tl > 0 else a.unit_price_usd * usd_tl
        qty = a.liquid_quantity + a.staked_quantity + a.pending_rewards
        total_tl += qty * price_tl

    # Snapshot olustur
    snapshot = PortfolioSnapshot(
        user_id=user_id,
        snapshot_date=today,
        total_value_tl=total_tl.quantize(Decimal("0.01")),
    )
    db.add(snapshot)
    await db.flush()

    # AssetPosition'lari ekle
    for asset in all_assets:
        pos = to_asset_position(asset, snapshot.id, usd_tl, total_tl)
        db.add(pos)

    await db.commit()
    await db.refresh(snapshot)
    logger.info(
        "Snapshot olusturuldu: user_id=%s, total_tl=%s, asset=%d",
        user_id,
        snapshot.total_value_tl,
        len(all_assets),
    )
    return snapshot
