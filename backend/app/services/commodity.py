"""Kıymetli maden (altın/gümüş) fiyat çekme ve değer hesaplama servisi."""
import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

import httpx

from app.models.commodity import CommodityHolding

logger = logging.getLogger(__name__)

TROY_OZ_TO_GRAM = Decimal("31.1034768")
TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"

# Yahoo Finance Chart API — anlık fiyat için regularMarketPrice
_YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

COIN_GRAM_WEIGHTS: dict[str, Decimal] = {
    "ceyrek": Decimal("1.7517"),
    "yarim": Decimal("3.5033"),
    "tam": Decimal("7.0166"),
    "cumhuriyet": Decimal("7.2164"),
    "resat": Decimal("7.2164"),
    "ata": Decimal("7.2164"),
}

BIGA_GRAM_WEIGHTS: dict[str, Decimal] = {
    "A01": Decimal("1"),
    "A02": Decimal("5"),
    "A03": Decimal("10"),
    "A04": Decimal("50"),
    "A05": Decimal("100"),
    "A06": Decimal("250"),
    "A07": Decimal("500"),
    "A08": Decimal("1000"),
    "G01": Decimal("1"),
    "G02": Decimal("5"),
    "G03": Decimal("10"),
    "G04": Decimal("50"),
    "G05": Decimal("100"),
    "G06": Decimal("500"),
    "G07": Decimal("1000"),
}

BIGA_METAL: dict[str, str] = {
    k: "gold" for k in ("A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08")
}
BIGA_METAL.update({k: "silver" for k in ("G01", "G02", "G03", "G04", "G05", "G06", "G07")})

# 5 dakika in-memory cache
_PRICE_CACHE_TTL_SEC = 300
_price_cache_lock = asyncio.Lock()
_price_cache: tuple[float, dict[str, Decimal]] | None = None


async def _fetch_tcmb_usd_try() -> Decimal:
    """TCMB XML'den USD/TRY (ForexBuying) döndürür."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(TCMB_URL)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

    for currency in root.findall("Currency"):
        code = currency.get("CurrencyCode")
        if code != "USD":
            continue
        unit_text = currency.findtext("Unit") or "1"
        buying = currency.findtext("ForexBuying")
        if not buying:
            break
        try:
            unit = Decimal(unit_text)
            rate = Decimal(buying)
            if unit > 0:
                return (rate / unit).quantize(Decimal("0.000001"))
        except (InvalidOperation, ValueError):
            break

    raise RuntimeError("TCMB XML'den USD/TRY kuru alınamadı")


async def _fetch_yahoo_price_usd(symbol: str) -> Decimal:
    """Yahoo Finance Chart API'den USD cinsinden anlık fiyat çeker."""
    url = _YAHOO_CHART_URL.format(symbol=symbol)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        resp = await client.get(url, params={"interval": "1d", "range": "1d"})
        resp.raise_for_status()
        data = resp.json()

    try:
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        return Decimal(str(price))
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Yahoo Finance'ten {symbol} fiyatı alınamadı") from exc


async def _fetch_silver_usd() -> Decimal:
    """Gümüş için XAG=X dener, başarısız olursa SI=F (futures) fallback eder.

    Her ikisi de başarısız olursa Decimal('0') döner — gümüş eksik olabilir,
    sayfa altın için çalışmaya devam etmeli.
    """
    for symbol in ("XAG=X", "SI=F"):
        try:
            return await _fetch_yahoo_price_usd(symbol)
        except Exception as exc:
            logger.warning("Gümüş fiyatı %s sembolünden alınamadı: %s", symbol, exc)
    logger.error("Tüm gümüş sembolleri başarısız — silver=0 dönülüyor")
    return Decimal("0")


async def fetch_metal_prices() -> dict[str, Decimal]:
    """Anlık altın ve gümüş fiyatlarını TRY/gram cinsinden döndürür.

    Sonuç 5 dakika in-memory cache'de tutulur.
    Dönüş: {"gold": Decimal, "silver": Decimal}

    Altın ve USD/TRY kritik — başarısız olursa exception yükselir.
    Gümüş best-effort — başarısız olursa 0 döner.
    """
    global _price_cache

    async with _price_cache_lock:
        now = time.monotonic()
        if _price_cache is not None and now - _price_cache[0] < _PRICE_CACHE_TTL_SEC:
            return _price_cache[1]

        try:
            xau_usd, xag_usd, usd_try = await asyncio.gather(
                _fetch_yahoo_price_usd("XAU=X"),
                _fetch_silver_usd(),
                _fetch_tcmb_usd_try(),
            )
        except Exception as exc:
            logger.error("Altın veya USD/TRY çekilemedi: %s", exc)
            raise

        gold_try_per_gram = (xau_usd / TROY_OZ_TO_GRAM * usd_try).quantize(Decimal("0.0001"))
        silver_try_per_gram = (
            (xag_usd / TROY_OZ_TO_GRAM * usd_try).quantize(Decimal("0.0001"))
            if xag_usd > 0
            else Decimal("0")
        )

        prices = {"gold": gold_try_per_gram, "silver": silver_try_per_gram}
        _price_cache = (now, prices)
        return prices


def calculate_holding_value(
    holding: CommodityHolding,
    gold_tl_per_gram: Decimal,
    silver_tl_per_gram: Decimal,
) -> dict[str, Decimal]:
    """Bir varlığın gram eşdeğerini ve TRY değerini hesaplar.

    Dönüş: {"gram_equivalent": Decimal, "total_value_tl": Decimal}
    """
    metal_price = gold_tl_per_gram if holding.metal == "gold" else silver_tl_per_gram

    if holding.unit_type == "gram":
        gram_eq = holding.quantity
        total = holding.quantity * metal_price

    elif holding.unit_type == "biga":
        if not holding.biga_code or holding.biga_code not in BIGA_GRAM_WEIGHTS:
            raise ValueError(f"Geçersiz BiGA kodu: {holding.biga_code}")
        gram_weight = BIGA_GRAM_WEIGHTS[holding.biga_code]
        gram_eq = holding.quantity * gram_weight
        total = gram_eq * metal_price

    elif holding.unit_type == "coin":
        if not holding.coin_type or holding.coin_type not in COIN_GRAM_WEIGHTS:
            raise ValueError(f"Geçersiz sikke türü: {holding.coin_type}")
        gram_weight = COIN_GRAM_WEIGHTS[holding.coin_type]
        gram_eq = holding.quantity * gram_weight
        # Sikke her zaman altın
        total = gram_eq * gold_tl_per_gram

    else:
        raise ValueError(f"Geçersiz unit_type: {holding.unit_type}")

    return {
        "gram_equivalent": gram_eq.quantize(Decimal("0.0001")),
        "total_value_tl": total.quantize(Decimal("0.01")),
    }
