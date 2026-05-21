"""Portfoy snapshot servisi.

Bir kullanicinin tum varlik kaynaklarindan veriyi paralel olarak ceker,
TL'ye normalize eder ve PortfolioSnapshot + AssetPosition kayitlari olusturur.

Hem APScheduler haftalik job'i hem de manuel /portfolio/snapshot endpoint'i
bu modulu kullanir.
"""

import asyncio
import logging
import uuid
from datetime import date, datetime
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
    fetch_combined_prices,
    fetch_gbp_to_usd,
    fetch_tcmb_rates,
    fetch_usd_to_tl,
    lookup_usd_price,
    to_asset_position,
)
from app.services.base import AssetData
from app.services.blockchain.algorand import AlgorandService
from app.services.blockchain.avalanche import AvalancheCChainService, AvalanchePChainService
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
            issues.append(
                {
                    "source": "crypto",
                    "provider": intg.provider,
                    "code": "fetch_failed",
                    "msg": str(e)[:200],
                }
            )
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
                issues.append(
                    {
                        "source": "wallet",
                        "chain": wallet.chain,
                        "address": wallet.address[:14] + "…",
                        "code": "empty_result",
                        "msg": "Cüzdan bakiyesi 0 veya tarama tamamlanamadı",
                    }
                )
            return assets
        except Exception as e:
            logger.warning(
                "Snapshot: cuzdan fetch hatasi [%s:%s]: %s", wallet.chain, wallet.address[:10], e
            )
            issues.append(
                {
                    "source": "wallet",
                    "chain": wallet.chain,
                    "address": wallet.address[:14] + "…",
                    "code": "fetch_failed",
                    "msg": str(e)[:200],
                }
            )
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
        issues.append(
            {
                "source": "tefas",
                "code": "fetch_failed",
                "msg": str(e)[:200],
            }
        )
        return []


async def _gather_cash_assets(
    holdings: list,
    usd_tl: Decimal,
    tcmb_rates: dict[str, Decimal],
    issues: list[dict],
) -> list[AssetData]:
    """Nakit/banka hesabı bakiyelerini AssetData'ya çevirir.

    FIN-007 (FAZ H): EUR/GBP/CHF gibi para birimleri TCMB kurlarindan dogru
    cevrilir. Rates dict'inde currency yoksa USD/TRY ile fallback + warning.
    TCMB cekilemezse (rates bos) sadece TRY ve USD kabul edilir.
    """
    if not holdings:
        return []
    out: list[AssetData] = []
    for h in holdings:
        amount = Decimal(str(h.amount))
        currency = h.currency.upper()

        if currency == "TRY":
            tl = amount
        elif currency in tcmb_rates and tcmb_rates[currency] > 0:
            tl = (amount * tcmb_rates[currency]).quantize(Decimal("0.01"))
        elif currency == "USD" and usd_tl > 0:
            # TCMB cekilemediyse exchangerate-api fallback ile gelen USD kuru
            tl = (amount * usd_tl).quantize(Decimal("0.01"))
        elif usd_tl > 0:
            # TCMB rates yok + USD/TRY var → tahmini USD eşdeğeri olarak çevir
            # (1:1 USD varsayim) ve issue'a uyari ekle
            tl = (amount * usd_tl).quantize(Decimal("0.01"))
            issues.append(
                {
                    "source": "cash",
                    "label": h.label,
                    "code": "currency_rate_missing",
                    "msg": f"{currency} kuru bulunamadi, USD/TRY ile yaklasik cevrildi (gercek deger farkli olabilir)",
                }
            )
        else:
            issues.append(
                {
                    "source": "cash",
                    "label": h.label,
                    "code": "rate_unavailable",
                    "msg": f"{currency} kuru hicbir kaynaktan alinamadi, hesap dahil edilmedi",
                }
            )
            continue
        if tl <= 0:
            continue
        out.append(
            AssetData(
                symbol=currency,
                name=h.label,
                provider="cash",
                asset_type="cash",
                source_type="manual",
                liquid_quantity=Decimal("1"),
                unit_price_tl=tl,
            )
        )
    return out


async def _gather_commodity_assets(
    holdings: list,
    issues: list[dict],
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
        issues.append(
            {
                "source": "commodity",
                "code": "metal_price_failed",
                "msg": f"Altın/Gümüş fiyatı çekilemedi: {str(exc)[:150]}",
            }
        )
        return []

    gold_price = prices.get("gold", Decimal("0"))
    silver_price = prices.get("silver", Decimal("0"))
    if gold_price <= 0:
        issues.append(
            {
                "source": "commodity",
                "code": "gold_zero",
                "msg": "Altın fiyatı 0 — pozisyonlar dahil edilmedi",
            }
        )
    if silver_price <= 0 and any(h.metal == "silver" for h in holdings):
        issues.append(
            {
                "source": "commodity",
                "code": "silver_zero",
                "msg": "Gümüş fiyatı 0 — gümüş pozisyonlar dahil edilmedi",
            }
        )

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
                "ceyrek": "Çeyrek",
                "yarim": "Yarım",
                "tam": "Tam",
                "cumhuriyet": "Cumhuriyet",
                "resat": "Reşat",
                "ata": "Ata",
            }.get(h.coin_type, h.coin_type)
            name = f"{coin_label} Altın"
        out.append(
            AssetData(
                symbol=symbol,
                name=name,
                provider="commodity",
                asset_type="commodity",
                source_type="manual",
                liquid_quantity=Decimal("1"),
                unit_price_tl=val["total_value_tl"],
            )
        )
    return out


async def _gather_manual_crypto_assets(
    holdings: list[ManualCryptoHolding],
    issues: list[dict],
) -> list[AssetData]:
    """Manuel girilmiş kripto bakiyeleri AssetData'ya çevirir.

    price_source bazlı:
    - 'auto'   → unit_price_tl=0; ortak enrichment loop'u Binance+CoinGecko'dan doldurur
    - 'manual' → kullanıcının manual_unit_price_tl
    - 'linked' → linked_source dispatch:
                 commodity (XAU/XAG), binance:SYMBOL, coingecko:ID, tefas:CODE
    Eksik fiyat durumunda snapshot health 'issues' listesine uyarı eklenir.
    """
    if not holdings:
        return []

    # Linked kayıtlar için kaynak başına ID toplama
    linked = [h for h in holdings if h.price_source == "linked"]
    needs_commodity = any(h.linked_source == "commodity" for h in linked)
    binance_ids = [h.linked_id for h in linked if h.linked_source == "binance" and h.linked_id]
    cg_ids = list({h.linked_id for h in linked if h.linked_source == "coingecko" and h.linked_id})
    tefas_codes = list({h.linked_id for h in linked if h.linked_source == "tefas" and h.linked_id})

    metal_prices: dict[str, Decimal] = {}
    if needs_commodity:
        try:
            from app.services.commodity import fetch_metal_prices

            metal_prices = await fetch_metal_prices()
        except Exception as exc:
            logger.warning("Snapshot manuel kripto: metal fiyatları çekilemedi: %s", exc)
            issues.append(
                {
                    "source": "manual_crypto",
                    "code": "metal_price_failed",
                    "msg": f"Altın/Gümüş fiyatı çekilemedi: {str(exc)[:150]}",
                }
            )

    binance_prices: dict[str, Decimal] = {}
    if binance_ids:
        try:
            binance_prices = await fetch_combined_prices(list(set(binance_ids)))
        except Exception as exc:
            logger.warning("Snapshot manuel kripto: Binance linked fiyatları çekilemedi: %s", exc)

    cg_prices: dict[str, Decimal] = {}
    if cg_ids:
        try:
            from app.services.aggregator import fetch_coingecko_prices_by_ids

            cg_prices = await fetch_coingecko_prices_by_ids(cg_ids)
        except Exception as exc:
            logger.warning("Snapshot manuel kripto: CoinGecko linked fiyatları çekilemedi: %s", exc)

    tefas_prices: dict[str, Decimal] = {}
    if tefas_codes:
        try:
            # ARC-001 (FAZ H): API katmaninda olan fonksiyon services/tefas.py'a tasindi.
            from app.services.tefas import fetch_tefas_prices_by_codes

            tefas_prices = await fetch_tefas_prices_by_codes(tefas_codes)
        except Exception as exc:
            logger.warning("Snapshot manuel kripto: TEFAS linked fiyatları çekilemedi: %s", exc)

    # USD/TL — linked binance/coingecko için unit_tl hesabında lazım; üst loop zaten alıyor
    # ama bu fonksiyon bağımsız çağrıldığında da çalışsın
    try:
        usd_tl = await fetch_usd_to_tl()
    except Exception:
        usd_tl = Decimal(0)

    out: list[AssetData] = []
    for h in holdings:
        unit_tl = Decimal(0)

        if h.price_source == "manual":
            if h.manual_unit_price_tl and h.manual_unit_price_tl > 0:
                unit_tl = Decimal(str(h.manual_unit_price_tl))
                # Bilgi: kullanıcının manuel girdiği fiyat, otomatik fiyat değil
                issues.append(
                    {
                        "level": "info",
                        "source": "manual_crypto",
                        "exchange": h.exchange,
                        "symbol": h.symbol,
                        "code": "info_manual_price",
                        "msg": f"{h.exchange} {h.symbol}: manuel girilmiş fiyat ({unit_tl} ₺) — anlık piyasa değeri değil",
                    }
                )
            else:
                issues.append(
                    {
                        "level": "warn",
                        "source": "manual_crypto",
                        "exchange": h.exchange,
                        "symbol": h.symbol,
                        "code": "manual_price_missing",
                        "msg": f"{h.exchange} {h.symbol}: 'manual' fiyat seçili ama manual_unit_price_tl boş",
                    }
                )

        elif h.price_source == "linked":
            ls = h.linked_source
            lid = h.linked_id or ""
            if ls == "commodity":
                key = (
                    "gold" if lid.upper() == "XAU" else ("silver" if lid.upper() == "XAG" else None)
                )
                unit_tl = metal_prices.get(key, Decimal(0)) if key else Decimal(0)
            elif ls == "binance":
                u = lookup_usd_price(lid, binance_prices)
                unit_tl = (
                    (u * usd_tl).quantize(Decimal("0.0001"))
                    if (u > 0 and usd_tl > 0)
                    else Decimal(0)
                )
            elif ls == "coingecko":
                u = cg_prices.get(lid, Decimal(0))
                unit_tl = (
                    (u * usd_tl).quantize(Decimal("0.0001"))
                    if (u > 0 and usd_tl > 0)
                    else Decimal(0)
                )
            elif ls == "tefas":
                unit_tl = tefas_prices.get(lid, Decimal(0))
            else:
                issues.append(
                    {
                        "level": "warn",
                        "source": "manual_crypto",
                        "exchange": h.exchange,
                        "symbol": h.symbol,
                        "code": "linked_invalid",
                        "msg": f"{h.exchange} {h.symbol}: 'linked' seçili ama linked_source/linked_id geçersiz",
                    }
                )

            if unit_tl > 0:
                # Bilgi: bu pozisyon başka bir varlığın fiyatına peg edilmiş
                issues.append(
                    {
                        "level": "info",
                        "source": "manual_crypto",
                        "exchange": h.exchange,
                        "symbol": h.symbol,
                        "code": "info_linked",
                        "msg": f"{h.exchange} {h.symbol}: {ls}:{lid} fiyatına bağlı (anlık {unit_tl} ₺/birim)",
                    }
                )
            elif ls in ("commodity", "binance", "coingecko", "tefas"):
                issues.append(
                    {
                        "level": "warn",
                        "source": "manual_crypto",
                        "exchange": h.exchange,
                        "symbol": h.symbol,
                        "code": f"linked_{ls}_no_price",
                        "msg": f"{h.exchange} {h.symbol}: linked={ls}:{lid} fiyatı çekilemedi/bulunamadı",
                    }
                )
        # auto için unit_tl=0 — ortak enrichment loop yakalar

        out.append(
            AssetData(
                symbol=h.symbol,
                name=h.label or f"{h.exchange} {h.symbol}",
                provider=f"manual:{h.exchange}",
                asset_type="crypto",
                source_type="manual",
                liquid_quantity=Decimal(str(h.quantity)),
                unit_price_tl=unit_tl,
            )
        )
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
    holdings: list[StockHolding],
    usd_tl: Decimal,
    gbp_usd: Decimal,
    issues: list[dict],
) -> list[AssetData]:
    if not holdings:
        return []
    tickers = [h.ticker for h in holdings]
    try:
        quotes = await fetch_stock_quotes(tickers)
    except Exception as e:
        logger.warning("Snapshot: hisse fetch hatasi: %s", e)
        issues.append(
            {
                "source": "stocks",
                "code": "fetch_failed",
                "msg": str(e)[:200],
            }
        )
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
        # FIN-004 (FAZ H): Stale fiyat kullaniciya rozet + health_issues uyarisi.
        # halted/delisted hisseler haftalarca ayni fiyatta sabitlenir; kullanici
        # "anlik" zannedip yanlis pozisyon hesaplamasin.
        if q.is_stale:
            issues.append(
                {
                    "source": "stocks",
                    "code": "stale_price",
                    "msg": f"{h.ticker}: anlik fiyat alinamadi, son bilinen kapanis kullanildi",
                    "level": "warn",
                    "symbol": h.ticker,
                    "provider": q.market_state or "unknown",
                }
            )
        out.append(
            AssetData(
                symbol=q.ticker,
                name=h.name or q.name,
                provider="stock",
                asset_type="stock",
                source_type="stock",
                liquid_quantity=Decimal(str(h.quantity)),
                unit_price_tl=price_tl.quantize(Decimal("0.0001")),
            )
        )
    return out


async def _last_known_usd_price(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str,
) -> tuple[Decimal | None, date | None]:
    """FIN-005 (FAZ H): Bir sembol icin son bilinen USD fiyatini doner.

    Onceki snapshot'larda saklanan unit_price_tl + usd_try_rate'ten USD
    fiyat hesaplar (snapshot anindaki kura bagli, bu sayede TCMB degisiklikleri
    eski fiyati bozmaz).

    Doner: (last_usd_price, snapshot_date) — bulunamazsa (None, None).
    """
    q = (
        select(
            AssetPosition.unit_price_tl,
            PortfolioSnapshot.usd_try_rate,
            PortfolioSnapshot.snapshot_date,
        )
        .join(PortfolioSnapshot, AssetPosition.snapshot_id == PortfolioSnapshot.id)
        .where(
            PortfolioSnapshot.user_id == user_id,
            AssetPosition.symbol == symbol,
            AssetPosition.unit_price_tl > 0,
            PortfolioSnapshot.usd_try_rate.is_not(None),
        )
        .order_by(PortfolioSnapshot.snapshot_date.desc())
        .limit(1)
    )
    row = (await db.execute(q)).first()
    if row is None:
        return None, None
    unit_price_tl, usd_rate, snap_date = row
    if usd_rate is None or Decimal(usd_rate) <= 0:
        return None, None
    return (Decimal(unit_price_tl) / Decimal(usd_rate)).quantize(Decimal("0.000001")), snap_date


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
    # TCMB rates EUR/CHF/JPY... cash holding multi-currency icin (FIN-007).
    rate_results = await asyncio.gather(
        fetch_usd_to_tl(),
        fetch_gbp_to_usd(),
        fetch_tcmb_rates(),
        return_exceptions=True,
    )
    usd_tl, gbp_usd, tcmb_rates = rate_results
    if isinstance(usd_tl, BaseException):
        logger.error("Snapshot: USD/TL kuru hicbir kaynaktan cekilemedi, iptal: %s", usd_tl)
        raise usd_tl
    if isinstance(gbp_usd, BaseException):
        logger.warning("Snapshot: GBP/USD cekilemedi, UK hisseleri 0 deger: %s", gbp_usd)
        gbp_usd = Decimal("0")
    if isinstance(tcmb_rates, BaseException):
        logger.warning(
            "Snapshot: TCMB rates cekilemedi, cash USD/TRY ile cevrilecek: %s", tcmb_rates
        )
        tcmb_rates = {}

    # Tum kaynaklardan asset'leri topla (paralel)
    issues: list[dict] = []
    (
        crypto_assets,
        wallet_assets,
        tefas_assets,
        stock_assets,
        commodity_assets,
        cash_assets,
    ) = await asyncio.gather(
        _gather_crypto_assets(integrations, issues),
        _gather_wallet_assets(wallets, issues),
        _gather_tefas_assets(tefas_holdings, issues),
        _gather_stock_assets(stock_holdings, usd_tl, gbp_usd, issues),
        _gather_commodity_assets(commodity_holdings, issues),
        _gather_cash_assets(cash_holdings, usd_tl, tcmb_rates, issues),
    )
    bes_assets = _gather_bes_assets(bes_holdings)  # Sync — DB'den cekilen lokal veri
    manual_crypto_assets = await _gather_manual_crypto_assets(manual_crypto_holdings, issues)
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
            spot_prices = await fetch_combined_prices(unique_symbols)
        except Exception as exc:
            logger.warning("Snapshot: spot fiyat çekilemedi: %s", exc)
            spot_prices = {}
        for a in needs_pricing:
            usd_price = lookup_usd_price(a.symbol, spot_prices)
            if usd_price > 0:
                a.unit_price_usd = usd_price
            else:
                # FIN-005 (FAZ H): Spot fiyat alinamadi — onceki snapshot'tan
                # son bilinen fiyati lookup et (gorunmez kayip onleme).
                qty = a.liquid_quantity + a.staked_quantity + a.pending_rewards
                if qty > 0:
                    last_usd_price, last_snap_date = await _last_known_usd_price(
                        db,
                        user_id,
                        a.symbol,
                    )
                    if last_usd_price is not None and last_usd_price > 0:
                        a.unit_price_usd = last_usd_price
                        issues.append(
                            {
                                "source": a.provider,
                                "symbol": a.symbol,
                                "code": "stale_price",
                                "msg": (
                                    f"{a.symbol} icin spot fiyat alinamadi, son bilinen "
                                    f"fiyat ({last_snap_date}) kullanildi"
                                ),
                            }
                        )
                    else:
                        issues.append(
                            {
                                "source": a.provider,
                                "symbol": a.symbol,
                                "code": "no_spot_price",
                                "msg": f"{a.symbol} için Binance USDT pariteni bulunamadı, snapshot'a 0 değerle eklendi",
                            }
                        )

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
