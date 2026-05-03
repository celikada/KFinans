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
        root = ET.fromstring(resp.content)

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
    totals = {"crypto": Decimal(0), "staked_crypto": Decimal(0), "fund": Decimal(0), "pension": Decimal(0), "cash": Decimal(0)}
    for pos in snapshot.asset_positions:
        totals[pos.asset_type] = totals.get(pos.asset_type, Decimal(0)) + pos.total_value_tl

    total = snapshot.total_value_tl or Decimal(1)
    pct = lambda v: (v / total * 100).quantize(Decimal("0.01"))

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
