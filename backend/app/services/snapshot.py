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
from app.models.bes import BesHolding
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
from app.services.blockchain.algorand import AlgorandService
from app.services.blockchain.bitcoin import BitcoinService
from app.services.blockchain.cardano import CardanoService
from app.services.blockchain.ethereum import EthereumService
from app.services.blockchain.litecoin import LitecoinService
from app.services.blockchain.polkadot import PolkadotService
from app.services.blockchain.solana import SolanaService
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


async def _gather_cash_assets(holdings: list, usd_tl: Decimal) -> list[AssetData]:
    """Nakit/banka hesabı bakiyelerini AssetData'ya çevirir.
    USD/EUR/GBP → TRY dönüşümü USD/TRY üzerinden yapılır (basit yaklaşım)."""
    if not holdings:
        return []
    out: list[AssetData] = []
    for h in holdings:
        amount = Decimal(str(h.amount))
        if h.currency == "TRY":
            tl = amount
        elif usd_tl > 0:
            tl = (amount * usd_tl).quantize(Decimal("0.01"))
        else:
            continue
        if tl <= 0:
            continue
        out.append(AssetData(
            symbol=h.currency, name=h.label,
            provider="cash", asset_type="cash", source_type="manual",
            liquid_quantity=Decimal("1"),
            unit_price_tl=tl,
        ))
    return out


async def _gather_commodity_assets(holdings: list) -> list[AssetData]:
    """CommodityHolding'leri (altın/gümüş gram/BiGA/sikke) AssetData'ya çevirir.
    Anlık metal fiyatlarıyla TL değer hesaplanır. Yahoo başarısız olursa
    metal fiyatı 0 → o pozisyon snapshot'a eklenmez (uyarı log).
    """
    if not holdings:
        return []
    from app.services.commodity import calculate_holding_value, fetch_metal_prices

    try:
        prices = await fetch_metal_prices()
    except Exception as exc:
        logger.warning("Snapshot: metal fiyatları çekilemedi: %s", exc)
        return []

    gold_price = prices.get("gold", Decimal("0"))
    silver_price = prices.get("silver", Decimal("0"))

    out: list[AssetData] = []
    for h in holdings:
        try:
            val = calculate_holding_value(h, gold_price, silver_price)
        except Exception as exc:
            logger.warning("Snapshot: commodity %d hesaplanamadı: %s", h.id, exc)
            continue
        if val["total_value_tl"] <= 0:
            continue
        symbol = "XAU" if h.metal == "gold" else "XAG"
        name = "Altın" if h.metal == "gold" else "Gümüş"
        if h.unit_type == "biga" and h.biga_code:
            name = f"{name} ({h.biga_code})"
        elif h.unit_type == "coin" and h.coin_type:
            coin_label = {
                "ceyrek": "Çeyrek", "yarim": "Yarım", "tam": "Tam",
                "cumhuriyet": "Cumhuriyet", "resat": "Reşat", "ata": "Ata",
            }.get(h.coin_type, h.coin_type)
            name = f"{coin_label} Altın"
        out.append(AssetData(
            symbol=symbol, name=name,
            provider="commodity", asset_type="commodity", source_type="manual",
            liquid_quantity=Decimal("1"),
            unit_price_tl=val["total_value_tl"],
        ))
    return out


def _gather_bes_assets(holdings: list[BesHolding]) -> list[AssetData]:
    """BES holdinglerini AssetData'ya cevirir.

    Toplam = paid_principal + paid_returns + govt_contribution + govt_returns
    (4 metric BesHolding modelinde ayri alanlar; snapshot'a tek pension
    pozisyonu olarak girer, toplam degeri unit_price_tl olarak tasinir).
    Asset_type='pension', provider='bes'.
    """
    return [
        AssetData(
            symbol=f"BES-{i + 1}",
            name=h.plan_name,
            provider="bes",
            asset_type="pension",
            source_type="bes",
            liquid_quantity=Decimal("1"),
            unit_price_tl=Decimal(str(h.total_value_tl)),
        )
        for i, h in enumerate(holdings)
    ]


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
    from app.models.cash import CashHolding
    from app.models.commodity import CommodityHolding

    intg_q, wallet_q, tefas_q, stock_q, bes_q, commodity_q, cash_q = await asyncio.gather(
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
        db.execute(select(BesHolding).where(BesHolding.user_id == user_id)),
        db.execute(select(CommodityHolding).where(CommodityHolding.user_id == user_id)),
        db.execute(select(CashHolding).where(CashHolding.user_id == user_id)),
    )
    integrations = intg_q.scalars().all()
    wallets = wallet_q.scalars().all()
    tefas_holdings = tefas_q.scalars().all()
    stock_holdings = stock_q.scalars().all()
    bes_holdings = bes_q.scalars().all()
    commodity_holdings = commodity_q.scalars().all()
    cash_holdings = cash_q.scalars().all()

    # Doviz kurlari — aggregator TCMB -> exchangerate-api cascading fallback yapar.
    # USD/TL kritiktir (kripto + USD hisse + cuzdanlar); cekilemezse snapshot iptal.
    # GBP/USD sadece UK hisseleri icin; cekilemezse 0 ile devam (UK hisseler 0 deger).
    rate_results = await asyncio.gather(
        fetch_usd_to_tl(),
        fetch_gbp_to_usd(),
        return_exceptions=True,
    )
    usd_tl, gbp_usd = rate_results
    if isinstance(usd_tl, BaseException):
        logger.error("Snapshot: USD/TL kuru hicbir kaynaktan cekilemedi, iptal: %s", usd_tl)
        raise usd_tl
    if isinstance(gbp_usd, BaseException):
        logger.warning("Snapshot: GBP/USD cekilemedi, UK hisseleri 0 deger: %s", gbp_usd)
        gbp_usd = Decimal("0")

    # Tum kaynaklardan asset'leri topla (paralel)
    crypto_assets, wallet_assets, tefas_assets, stock_assets, commodity_assets, cash_assets = await asyncio.gather(
        _gather_crypto_assets(integrations),
        _gather_wallet_assets(wallets),
        _gather_tefas_assets(tefas_holdings),
        _gather_stock_assets(stock_holdings, usd_tl, gbp_usd),
        _gather_commodity_assets(commodity_holdings),
        _gather_cash_assets(cash_holdings, usd_tl),
    )
    bes_assets = _gather_bes_assets(bes_holdings)  # Sync — DB'den cekilen lokal veri
    all_assets: list[AssetData] = (
        list(crypto_assets)
        + list(wallet_assets)
        + list(tefas_assets)
        + list(stock_assets)
        + list(bes_assets)
        + list(commodity_assets)
        + list(cash_assets)
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
