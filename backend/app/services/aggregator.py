import logging
import time
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

import httpx

from app.models.portfolio import AssetPosition, PortfolioSnapshot
from app.schemas.portfolio import PortfolioBreakdown, PortfolioChanges, StakingPosition
from app.services.base import AssetData

logger = logging.getLogger(__name__)

TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
EXCHANGERATE_API_USD = "https://api.exchangerate-api.com/v4/latest/USD"
EXCHANGERATE_API_GBP = "https://api.exchangerate-api.com/v4/latest/GBP"

# TCMB tek bir cagri ile tum kurlari donduruyor; ayni snapshot icinde tekrar
# tekrar cekmemek icin kisa sureli in-memory cache.
_TCMB_CACHE_TTL_SEC = 300
_tcmb_cache: tuple[float, dict[str, Decimal]] | None = None


def parse_tcmb_xml(content: bytes) -> dict[str, Decimal]:
    """TCMB kur XML icerigini {döviz: 1 birim = X TL} haritasina cevirir.

    'ForexBuying' (efektif alis) kullanilir; `Unit` ile per-1-birim normalize
    (JPY/KRW gibi 100 birim bazinda gelenler tek birime indirilir). Hem guncel
    (`today.xml`) hem tarihsel (`YYYYMM/DDMMYYYY.xml`) XML ayni semaya sahip
    oldugundan ortak parse noktasi (DRY) — historical_rates servisi de kullanir.
    """
    root = ET.fromstring(content)
    rates: dict[str, Decimal] = {}
    for currency in root.findall("Currency"):
        code = currency.get("CurrencyCode")
        unit_text = currency.findtext("Unit") or "1"
        buying = currency.findtext("ForexBuying")
        if not code or not buying:
            continue
        try:
            unit = Decimal(unit_text)
            rate = Decimal(buying)
            # JPY, KRW gibi birimler 100/USD bazinda donuyor; tek birime normalize
            if unit > 0:
                rates[code] = (rate / unit).quantize(Decimal("0.000001"))
        except (InvalidOperation, ValueError):
            continue
    return rates


async def fetch_tcmb_rates() -> dict[str, Decimal]:
    """TCMB kurlarinin public alias'i (snapshot, cash multi-currency)."""
    return await _fetch_tcmb_rates()


async def _fetch_tcmb_rates() -> dict[str, Decimal]:
    """TCMB resmi gunluk kurlari (XML). 'ForexBuying' (efektif alis) kullanilir.

    Hafta sonu/tatilde TCMB son is gununun XML'ini servis eder, bu da bizim
    icin kabul edilebilir (snapshot dogrulugu icin).
    """
    global _tcmb_cache
    now = time.time()
    if _tcmb_cache and now - _tcmb_cache[0] < _TCMB_CACHE_TTL_SEC:
        return _tcmb_cache[1]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(TCMB_URL)
        resp.raise_for_status()
        rates = parse_tcmb_xml(resp.content)

    _tcmb_cache = (now, rates)
    return rates


async def _fetch_rate_from_exchangerate_api(url: str, target: str) -> Decimal:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return Decimal(str(data["rates"][target]))


async def fetch_usd_to_tl() -> Decimal:
    """USD/TL kurunu doner. Oncelik: TCMB -> exchangerate-api.

    Her iki kaynak da basarisiz olursa RuntimeError firlatir; cagiran tarafta
    yakalanip gerekirse son bilinen DB degeri kullanilabilir.
    """
    try:
        rates = await _fetch_tcmb_rates()
        if "USD" in rates:
            return rates["USD"]
        logger.warning("TCMB yanitinda USD bulunamadi, fallback'e geciliyor")
    except Exception as e:
        logger.warning("TCMB USD kuru cekilemedi (%s), fallback'e geciliyor", e)

    try:
        return await _fetch_rate_from_exchangerate_api(EXCHANGERATE_API_USD, "TRY")
    except Exception as e:
        logger.error("Exchangerate-api USD kuru cekilemedi: %s", e)
        raise RuntimeError("USD/TRY kuru hicbir kaynaktan cekilemedi") from e


async def fetch_gbp_to_usd() -> Decimal:
    """GBP/USD kurunu doner. Oncelik: TCMB (GBP/TRY ile USD/TRY orani) -> exchangerate-api.

    UK hisselerinin (GBp pence cinsinden) TL'ye donusumunde kullanilir.
    """
    try:
        rates = await _fetch_tcmb_rates()
        gbp_try = rates.get("GBP")
        usd_try = rates.get("USD")
        if gbp_try and usd_try and usd_try > 0:
            return (gbp_try / usd_try).quantize(Decimal("0.000001"))
        logger.warning("TCMB yanitinda GBP veya USD eksik, fallback'e geciliyor")
    except Exception as e:
        logger.warning("TCMB GBP kuru cekilemedi (%s), fallback'e geciliyor", e)

    try:
        return await _fetch_rate_from_exchangerate_api(EXCHANGERATE_API_GBP, "USD")
    except Exception as e:
        logger.error("Exchangerate-api GBP kuru cekilemedi: %s", e)
        raise RuntimeError("GBP/USD kuru hicbir kaynaktan cekilemedi") from e


_BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"


async def fetch_spot_prices(symbols: list[str]) -> dict[str, Decimal]:
    """Binance'ten USDT pariteli spot fiyatları çeker. Bulunamayanlar 0 döner."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_BINANCE_PRICE_URL)
        resp.raise_for_status()
        all_prices = {t["symbol"]: Decimal(t["price"]) for t in resp.json()}

    result: dict[str, Decimal] = {}
    for sym in symbols:
        result[sym] = all_prices.get(f"{sym}USDT", Decimal(0))
    return result


# CoinGecko fallback — Binance USDT paritesi bulunmayan token'lar için
# (iCrypex'e özel ICPX, XAGX gibi). Free tier ~30 istek/dk, /coins/list
# 24 saat cache'lenir (yaklaşık 17K coin, ~5MB), /simple/price her çağrıda.
_COINGECKO_LIST_URL = "https://api.coingecko.com/api/v3/coins/list"
_COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
_COINGECKO_LIST_TTL_SEC = 24 * 3600
_coingecko_list_cache: tuple[float, dict[str, str]] | None = None

# Çoklu eşleşmelerde (örn. "BTC" birden fazla coin'de) bu override öncelikli.
# Genel kural: id_map'te ilk gelen kabul edilir (CoinGecko alfabetik dönüyor).
COINGECKO_SYMBOL_OVERRIDES: dict[str, str] = {
    "ICPX": "icrypex-token",
    # XAGX/OILX gibi diğerleri /coins/list'te yakalanırsa orada — yoksa
    # eklemek için: https://api.coingecko.com/api/v3/search?query=XAGX
}


async def _get_coingecko_id_map() -> dict[str, str]:
    """CoinGecko /coins/list → uppercase symbol → coin id mapping. 24 saat cache."""
    global _coingecko_list_cache
    now = time.time()
    if _coingecko_list_cache and now - _coingecko_list_cache[0] < _COINGECKO_LIST_TTL_SEC:
        return _coingecko_list_cache[1]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_COINGECKO_LIST_URL)
        resp.raise_for_status()
        data = resp.json()

    # Çoklu eşleşmelerde ilkini al (CoinGecko sıralaması market cap odaklı değil ama
    # popüler coinler genelde önce gelir). Override map ile ezilebilir.
    mapping: dict[str, str] = {}
    for c in data:
        sym = c.get("symbol", "").upper()
        if sym and sym not in mapping:
            mapping[sym] = c.get("id", "")
    mapping.update(COINGECKO_SYMBOL_OVERRIDES)

    _coingecko_list_cache = (now, mapping)
    return mapping


async def fetch_coingecko_prices_by_ids(ids: list[str]) -> dict[str, Decimal]:
    """CoinGecko coin ID'lerinin USD fiyatlarını çeker (asset-catalog linkleri için).
    Dönüş: {id: usd}. Bulunmayan ID dict'te yer almaz."""
    if not ids:
        return {}
    unique = ",".join(sorted(set(ids)))
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                _COINGECKO_PRICE_URL,
                params={"ids": unique, "vs_currencies": "usd"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("CoinGecko ID-bazlı fiyat çekilemedi: %s", e)
        return {}

    result: dict[str, Decimal] = {}
    for cg_id in ids:
        usd = data.get(cg_id, {}).get("usd")
        if usd:
            result[cg_id] = Decimal(str(usd))
    return result


async def fetch_coingecko_prices(symbols: list[str]) -> dict[str, Decimal]:
    """Verilen sembollerin USD fiyatlarını CoinGecko'dan çeker.
    Bulunmayanlar dict'te yer almaz (0 anlamına gelir).
    """
    if not symbols:
        return {}
    try:
        id_map = await _get_coingecko_id_map()
    except Exception as e:
        logger.warning("CoinGecko /coins/list çekilemedi: %s", e)
        return {}

    symbol_to_id = {}
    for s in symbols:
        cg_id = id_map.get(s.upper())
        if cg_id:
            symbol_to_id[s] = cg_id

    if not symbol_to_id:
        return {}

    unique_ids = ",".join(sorted(set(symbol_to_id.values())))
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                _COINGECKO_PRICE_URL,
                params={"ids": unique_ids, "vs_currencies": "usd"},
            )
            resp.raise_for_status()
            prices = resp.json()
    except Exception as e:
        logger.warning("CoinGecko fiyat çekilemedi: %s", e)
        return {}

    result: dict[str, Decimal] = {}
    for sym, cg_id in symbol_to_id.items():
        usd = prices.get(cg_id, {}).get("usd")
        if usd:
            result[sym] = Decimal(str(usd))
    return result


async def fetch_combined_prices(symbols: list[str]) -> dict[str, Decimal]:
    """Binance + CoinGecko fallback. Binance'te bulunamayanlar CoinGecko'dan denenir.
    Snapshot ve manuel kripto preview'unde kullanılır.
    """
    if not symbols:
        return {}
    binance = await fetch_spot_prices(symbols)
    missing = [s for s in symbols if binance.get(s, Decimal(0)) <= 0 and s not in USD_STABLE_SYMBOLS and s not in SYMBOL_PRICE_ALIASES]
    if not missing:
        return binance

    cg = await fetch_coingecko_prices(missing)
    for sym, price in cg.items():
        if price > 0:
            binance[sym] = price
    return binance


# ETH peg'li staking tokenları + WBTC + AVAX peg'li → Binance USDT pariteli base symbol
SYMBOL_PRICE_ALIASES: dict[str, str] = {
    "STETH": "ETH",
    "stETH": "ETH",
    "psETH": "ETH",
    "PSETH": "ETH",
    "lcETH": "ETH",
    "LCETH": "ETH",
    "rETH": "ETH",
    "cbETH": "ETH",
    "wstETH": "ETH",
    "WBTC": "BTC",
    "sAVAX": "AVAX",
    "SAVAX": "AVAX",
}
USD_STABLE_SYMBOLS: set[str] = {
    "USDT",
    "USDC",
    "DAI",
    "BUSD",
    "TUSD",
    "FRAX",
    "mstkeUSDT",
    "MSTKEUSDT",
}


def lookup_usd_price(symbol: str, prices: dict) -> Decimal:
    """Token symbol → USD fiyat. Curated alias + stablecoin desteği."""
    if symbol in USD_STABLE_SYMBOLS:
        return Decimal("1")
    direct = prices.get(symbol)
    if direct and direct > 0:
        return direct
    aliased = SYMBOL_PRICE_ALIASES.get(symbol)
    if aliased:
        return prices.get(aliased, Decimal(0))
    return Decimal(0)


def to_asset_position(asset: AssetData, snapshot_id, usd_tl_rate: Decimal, total_value_tl: Decimal) -> AssetPosition:
    if asset.unit_price_tl > 0:
        price_tl = asset.unit_price_tl
    else:
        price_tl = asset.unit_price_usd * usd_tl_rate

    total_qty = asset.liquid_quantity + asset.staked_quantity + asset.pending_rewards
    value_tl = total_qty * price_tl
    weight = (value_tl / total_value_tl * 100) if total_value_tl > 0 else Decimal(0)

    return AssetPosition(
        snapshot_id=snapshot_id,
        source_type=asset.source_type,
        provider=asset.provider,
        asset_type=asset.asset_type,
        symbol=asset.symbol,
        name=asset.name,
        liquid_quantity=asset.liquid_quantity,
        staked_quantity=asset.staked_quantity,
        pending_rewards=asset.pending_rewards,
        unit_price_tl=price_tl,
        total_value_tl=value_tl,
        weight_pct=weight.quantize(Decimal("0.01")),
        wallet_address_id=asset.wallet_address_id,
    )


def calculate_changes(snapshots: list[PortfolioSnapshot]) -> PortfolioChanges:
    current = snapshots[0]
    wow_change_tl = Decimal(0)
    wow_change_pct = Decimal(0)
    mom_change_tl = Decimal(0)
    mom_change_pct = Decimal(0)

    if len(snapshots) >= 2:
        prev_week = snapshots[1]
        wow_change_tl = current.total_value_tl - prev_week.total_value_tl
        wow_change_pct = (wow_change_tl / prev_week.total_value_tl * 100) if prev_week.total_value_tl else Decimal(0)

    if len(snapshots) >= 5:
        prev_month = snapshots[4]
        mom_change_tl = current.total_value_tl - prev_month.total_value_tl
        mom_change_pct = (mom_change_tl / prev_month.total_value_tl * 100) if prev_month.total_value_tl else Decimal(0)

    return PortfolioChanges(
        current_value_tl=current.total_value_tl,
        wow_change_tl=wow_change_tl,
        wow_change_pct=wow_change_pct.quantize(Decimal("0.01")),
        mom_change_tl=mom_change_tl,
        mom_change_pct=mom_change_pct.quantize(Decimal("0.01")),
        snapshot_date=current.snapshot_date,
    )


def calculate_breakdown(snapshot: PortfolioSnapshot) -> PortfolioBreakdown:
    totals = {
        "crypto": Decimal(0),
        "staked_crypto": Decimal(0),
        "fund": Decimal(0),
        "pension": Decimal(0),
        "cash": Decimal(0),
    }
    for pos in snapshot.asset_positions:
        totals[pos.asset_type] = totals.get(pos.asset_type, Decimal(0)) + pos.total_value_tl

    total = snapshot.total_value_tl or Decimal(1)

    def pct(v: Decimal) -> Decimal:
        return (v / total * 100).quantize(Decimal("0.01"))

    top_assets = sorted(snapshot.asset_positions, key=lambda p: p.total_value_tl, reverse=True)[:5]

    return PortfolioBreakdown(
        crypto_pct=pct(totals["crypto"]),
        staked_crypto_pct=pct(totals["staked_crypto"]),
        fund_pct=pct(totals["fund"]),
        pension_pct=pct(totals["pension"]),
        cash_pct=pct(totals["cash"]),
        top_assets=top_assets,
    )


def extract_staking_positions(snapshot: PortfolioSnapshot) -> list[StakingPosition]:
    return [
        StakingPosition(
            provider=pos.provider,
            symbol=pos.symbol,
            name=pos.name,
            staked_quantity=pos.staked_quantity,
            pending_rewards=pos.pending_rewards,
            staked_value_tl=(pos.staked_quantity * pos.unit_price_tl).quantize(Decimal("0.01")),
            rewards_value_tl=(pos.pending_rewards * pos.unit_price_tl).quantize(Decimal("0.01")),
        )
        for pos in snapshot.asset_positions
        if pos.staked_quantity > 0
    ]
