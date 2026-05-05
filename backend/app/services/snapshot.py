"""Portfoy snapshot servisi.

Bir kullanicinin tum varlik kaynaklarindan veriyi paralel olarak ceker,
TL'ye normalize eder ve PortfolioSnapshot + AssetPosition kayitlari olusturur.

Hem APScheduler haftalik job'i hem de manuel /portfolio/snapshot endpoint'i
bu modulu kullanir.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

# Snapshot tarihi kullanıcı saatine göre belirlenmeli — UTC backend'de gece 03:00'a
# kadar "dün" gösterirdi. Türkiye yerel saatiyle çalış.
_ISTANBUL = ZoneInfo("Europe/Istanbul")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.models.bes import BesHolding
from app.models.integration import Integration, WalletAddress
from app.models.manual_crypto import ManualCryptoHolding
from app.models.portfolio import AssetPosition, PortfolioSnapshot
from app.models.stock import StockHolding
from app.models.tefas import TefasHolding
from app.services.aggregator import (
    fetch_gbp_to_usd,
    fetch_spot_prices,
    fetch_usd_to_tl,
    lookup_usd_price,
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


async def _gather_crypto_assets(
    integrations: list[Integration],
    issues: list[dict],
) -> list[AssetData]:
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
            issues.append({
                "source": "crypto",
                "provider": intg.provider,
                "code": "fetch_failed",
                "msg": str(e)[:200],
            })
    return out


async def _gather_wallet_assets(
    wallets: list[WalletAddress],
    issues: list[dict],
) -> list[AssetData]:
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
            assets = await svc.fetch()
            if not assets:
                # Servis exception fırlatmadı ama 0 asset döndü — uyarı kaydet
                issues.append({
                    "source": "wallet",
                    "chain": wallet.chain,
                    "address": wallet.address[:14] + "…",
                    "code": "empty_result",
                    "msg": "Cüzdan bakiyesi 0 veya tarama tamamlanamadı",
                })
            return assets
        except Exception as e:
            logger.warning("Snapshot: cuzdan fetch hatasi [%s:%s]: %s", wallet.chain, wallet.address[:10], e)
            issues.append({
                "source": "wallet",
                "chain": wallet.chain,
                "address": wallet.address[:14] + "…",
                "code": "fetch_failed",
                "msg": str(e)[:200],
            })
            return []

    results = await asyncio.gather(*[_fetch_one(w) for w in wallets])
    return [a for r in results for a in r]


async def _gather_tefas_assets(
    holdings: list[TefasHolding],
    issues: list[dict],
) -> list[AssetData]:
    if not holdings:
        return []
    payload = [{"code": h.code, "quantity": float(h.quantity), "name": h.name} for h in holdings]
    try:
        return await TefasService(payload).fetch()
    except Exception as e:
        logger.warning("Snapshot: tefas fetch hatasi: %s", e)
        issues.append({
            "source": "tefas",
            "code": "fetch_failed",
            "msg": str(e)[:200],
        })
        return []


async def _gather_cash_assets(
    holdings: list, usd_tl: Decimal, issues: list[dict],
) -> list[AssetData]:
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
            issues.append({
                "source": "cash",
                "label": h.label,
                "code": "rate_unavailable",
                "msg": f"USD kuru alınamadığı için {h.currency} hesabı dahil edilmedi",
            })
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


async def _gather_commodity_assets(
    holdings: list, issues: list[dict],
) -> list[AssetData]:
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
        issues.append({
            "source": "commodity",
            "code": "metal_price_failed",
            "msg": f"Altın/Gümüş fiyatı çekilemedi: {str(exc)[:150]}",
        })
        return []

    gold_price = prices.get("gold", Decimal("0"))
    silver_price = prices.get("silver", Decimal("0"))
    if gold_price <= 0:
        issues.append({"source": "commodity", "code": "gold_zero", "msg": "Altın fiyatı 0 — pozisyonlar dahil edilmedi"})
    if silver_price <= 0 and any(h.metal == "silver" for h in holdings):
        issues.append({"source": "commodity", "code": "silver_zero", "msg": "Gümüş fiyatı 0 — gümüş pozisyonlar dahil edilmedi"})

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


def _gather_manual_crypto_assets(
    holdings: list[ManualCryptoHolding],
) -> list[AssetData]:
    """Manuel girilmiş kripto bakiyeleri AssetData'ya çevirir.

    Fiyat enjekte edilmez — `compute_and_save_snapshot` içindeki ortak fiyat
    enrichment loop'u (fetch_spot_prices + lookup_usd_price) bunu da yakalar.
    Provider 'manual:{exchange}' formatında saklanır (ör. 'manual:binancetr').
    """
    out: list[AssetData] = []
    for h in holdings:
        out.append(AssetData(
            symbol=h.symbol,
            name=h.label or f"{h.exchange} {h.symbol}",
            provider=f"manual:{h.exchange}",
            asset_type="crypto",
            source_type="manual",
            liquid_quantity=Decimal(str(h.quantity)),
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
    holdings: list[StockHolding], usd_tl: Decimal, gbp_usd: Decimal,
    issues: list[dict],
) -> list[AssetData]:
    if not holdings:
        return []
    tickers = [h.ticker for h in holdings]
    try:
        quotes = await fetch_stock_quotes(tickers)
    except Exception as e:
        logger.warning("Snapshot: hisse fetch hatasi: %s", e)
        issues.append({
            "source": "stocks",
            "code": "fetch_failed",
            "msg": str(e)[:200],
        })
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


async def compute_and_save_snapshot(
    user_id: uuid.UUID,
    db: AsyncSession,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> PortfolioSnapshot | dict:
    """Tek bir kullanici icin tum varlik kaynaklarindan snapshot alir.

    Ayni gune ait mevcut snapshot varsa silinir (idempotent — manuel
    tetiklemeler veya yeniden cagri durumunda zincirleme kayit olusmaz).

    dry_run=True: gather yapar, total + issues döndürür ama DB'ye yazmaz
                  (kullanıcıya onay popup'ı için).
                  Dönüş: {"total_value_tl", "asset_count", "issues",
                          "usd_try_rate"}
    force=True:   issues olsa bile DB'ye yaz (kullanıcı onayladı).
                  dry_run=False ise zaten yazılır; force, semantik flag.
    """
    today = datetime.now(_ISTANBUL).date()

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

    intg_q, wallet_q, tefas_q, stock_q, bes_q, commodity_q, cash_q, manual_q = await asyncio.gather(
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
        db.execute(select(ManualCryptoHolding).where(ManualCryptoHolding.user_id == user_id)),
    )
    integrations = intg_q.scalars().all()
    wallets = wallet_q.scalars().all()
    tefas_holdings = tefas_q.scalars().all()
    stock_holdings = stock_q.scalars().all()
    bes_holdings = bes_q.scalars().all()
    commodity_holdings = commodity_q.scalars().all()
    cash_holdings = cash_q.scalars().all()
    manual_crypto_holdings = manual_q.scalars().all()

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
    issues: list[dict] = []
    crypto_assets, wallet_assets, tefas_assets, stock_assets, commodity_assets, cash_assets = await asyncio.gather(
        _gather_crypto_assets(integrations, issues),
        _gather_wallet_assets(wallets, issues),
        _gather_tefas_assets(tefas_holdings, issues),
        _gather_stock_assets(stock_holdings, usd_tl, gbp_usd, issues),
        _gather_commodity_assets(commodity_holdings, issues),
        _gather_cash_assets(cash_holdings, usd_tl, issues),
    )
    bes_assets = _gather_bes_assets(bes_holdings)  # Sync — DB'den cekilen lokal veri
    manual_crypto_assets = _gather_manual_crypto_assets(manual_crypto_holdings)  # Sync
    all_assets: list[AssetData] = (
        list(crypto_assets)
        + list(wallet_assets)
        + list(tefas_assets)
        + list(stock_assets)
        + list(bes_assets)
        + list(commodity_assets)
        + list(cash_assets)
        + list(manual_crypto_assets)
    )

    # Blockchain ve kripto asset'lerine spot fiyat enjekte et
    # (servisler sadece miktar döner, fiyat ayrıca lookup'lanır)
    needs_pricing = [a for a in all_assets if a.unit_price_tl == 0 and a.unit_price_usd == 0]
    if needs_pricing:
        unique_symbols = list({a.symbol for a in needs_pricing})
        try:
            spot_prices = await fetch_spot_prices(unique_symbols)
        except Exception as exc:
            logger.warning("Snapshot: spot fiyat çekilemedi: %s", exc)
            spot_prices = {}
        for a in needs_pricing:
            usd_price = lookup_usd_price(a.symbol, spot_prices)
            if usd_price > 0:
                a.unit_price_usd = usd_price
            else:
                # Fiyatsız blockchain pozisyonu = sıfır değer = sağlık uyarısı
                qty = a.liquid_quantity + a.staked_quantity + a.pending_rewards
                if qty > 0:
                    issues.append({
                        "source": a.provider,
                        "symbol": a.symbol,
                        "code": "no_spot_price",
                        "msg": f"{a.symbol} için Binance USDT pariteni bulunamadı, snapshot'a 0 değerle eklendi",
                    })

    # Toplam degeri hesapla (weight_pct icin gerekli)
    total_tl = Decimal(0)
    for a in all_assets:
        price_tl = a.unit_price_tl if a.unit_price_tl > 0 else a.unit_price_usd * usd_tl
        qty = a.liquid_quantity + a.staked_quantity + a.pending_rewards
        total_tl += qty * price_tl

    # Dry-run her zaman dict döndürür, asla DB'ye yazmaz
    if dry_run:
        return {
            "total_value_tl": str(total_tl.quantize(Decimal("0.01"))),
            "asset_count": len(all_assets),
            "issues": issues,
            "usd_try_rate": str(usd_tl.quantize(Decimal("0.000001"))) if usd_tl > 0 else None,
            "saved": False,
        }

    # Snapshot olustur — usd_try_rate snapshot anındaki kuru saklar (geçmiş USD eğimi için)
    snapshot = PortfolioSnapshot(
        user_id=user_id,
        snapshot_date=today,
        total_value_tl=total_tl.quantize(Decimal("0.01")),
        usd_try_rate=usd_tl.quantize(Decimal("0.000001")) if usd_tl > 0 else None,
        health_issues=issues if issues else None,
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
