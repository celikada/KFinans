"""Asset catalog endpoint — fiyat kaynaklarına bağlanabilir varlıklar.

Manuel kripto modülü için linked_source/linked_id seçimi sırasında frontend
bu endpoint'i çağırır, autocomplete sonuç döner. Kaynaklar:
- commodity (statik): XAU, XAG
- binance: USDT pariteli base symbol'ler (~500, 5 dk cache)
- coingecko: tüm coinler (~17K, 24 saat cache — aggregator zaten tutar)
- tefas: aktif fonlar (~600, 1 saat cache)
"""
import logging
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.manual_crypto import AssetCatalogItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/asset-catalog", tags=["asset-catalog"])


_BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"
_TEFAS_EXPORT_URL = "https://www.tefas.gov.tr/api/fund-returns/export"
_TEFAS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.tefas.gov.tr/",
    "Content-Type": "application/json",
}

# Cache (TTL'ler)
_BINANCE_LIST_TTL_SEC = 300        # 5 dk
_TEFAS_LIST_TTL_SEC = 3600         # 1 saat
_binance_cache: tuple[float, list[str]] | None = None
_tefas_cache: tuple[float, list[dict]] | None = None

# Statik commodity listesi (TR + EN tag'leriyle aramada bulunsun)
_COMMODITY_STATIC: list[AssetCatalogItem] = [
    AssetCatalogItem(source="commodity", id="XAU", symbol="XAU", name="Altın gr / Gold (TRY/g)"),
    AssetCatalogItem(source="commodity", id="XAG", symbol="XAG", name="Gümüş gr / Silver (TRY/g)"),
]


async def _get_binance_symbols() -> list[str]:
    """Binance USDT pariteli base symbol'leri (BTC, ETH, ...). 5 dk cache."""
    global _binance_cache
    now = time.monotonic()
    if _binance_cache and now - _binance_cache[0] < _BINANCE_LIST_TTL_SEC:
        return _binance_cache[1]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_BINANCE_PRICE_URL)
            resp.raise_for_status()
            tickers = resp.json()
    except Exception as e:
        logger.warning("Binance ticker listesi çekilemedi: %s", e)
        return _binance_cache[1] if _binance_cache else []

    bases = sorted({
        t["symbol"][:-4]  # 'BTCUSDT' -> 'BTC'
        for t in tickers
        if t.get("symbol", "").endswith("USDT") and len(t["symbol"]) > 4
    })
    _binance_cache = (now, bases)
    return bases


async def _get_tefas_funds() -> list[dict]:
    """TEFAS aktif fon listesi: [{code, name}]. 1 saat cache."""
    global _tefas_cache
    now = time.monotonic()
    if _tefas_cache and now - _tefas_cache[0] < _TEFAS_LIST_TTL_SEC:
        return _tefas_cache[1]
    payload = {
        "format": "json",
        "listingType": "size",
        "fundType": "YAT",
        "locale": "tr",
        "filters": {"calismaTipi": 1},
    }
    try:
        async with httpx.AsyncClient(timeout=20, headers=_TEFAS_HEADERS) as client:
            resp = await client.post(_TEFAS_EXPORT_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("TEFAS fon listesi çekilemedi: %s", e)
        return _tefas_cache[1] if _tefas_cache else []

    funds = [
        {"code": row.get("fonKodu", "").strip(), "name": (row.get("fonUnvan") or "").strip()}
        for row in data
        if row.get("fonKodu")
    ]
    _tefas_cache = (now, funds)
    return funds


def _matches(query: str, *fields: str) -> bool:
    """Case-insensitive substring match. Boş query → True (tümü)."""
    if not query:
        return True
    ql = query.lower()
    return any(f and ql in f.lower() for f in fields)


def _search_commodity(q: str, remaining: int) -> list[AssetCatalogItem]:
    out: list[AssetCatalogItem] = []
    for it in _COMMODITY_STATIC:
        if len(out) >= remaining:
            break
        if _matches(q, it.id, it.symbol, it.name):
            out.append(it)
    return out


async def _search_binance(q: str, remaining: int) -> list[AssetCatalogItem]:
    if remaining <= 0:
        return []
    bases = await _get_binance_symbols()
    out: list[AssetCatalogItem] = []
    for sym in bases:
        if len(out) >= remaining:
            break
        if _matches(q, sym):
            out.append(AssetCatalogItem(source="binance", id=sym, symbol=sym, name=sym))
    return out


async def _search_coingecko(q: str, remaining: int) -> list[AssetCatalogItem]:
    if remaining <= 0:
        return []
    from app.services.aggregator import _get_coingecko_id_map
    id_map = await _get_coingecko_id_map()
    out: list[AssetCatalogItem] = []
    for sym, cg_id in id_map.items():
        if len(out) >= remaining:
            break
        if _matches(q, sym, cg_id):
            out.append(AssetCatalogItem(source="coingecko", id=cg_id, symbol=sym, name=cg_id))
    return out


async def _search_tefas(q: str, remaining: int) -> list[AssetCatalogItem]:
    if remaining <= 0:
        return []
    funds = await _get_tefas_funds()
    out: list[AssetCatalogItem] = []
    for f in funds:
        if len(out) >= remaining:
            break
        if _matches(q, f.get("code"), f.get("name")):
            out.append(AssetCatalogItem(
                source="tefas",
                id=f["code"],
                symbol=f["code"],
                name=f.get("name") or f["code"],
            ))
    return out


@router.get("", response_model=list[AssetCatalogItem])
async def search_catalog(
    _user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(max_length=100, description="Arama terimi (boş = popüler ilkler)")] = "",
    source: Annotated[str | None, Query(description="Filtre: binance|coingecko|tefas|commodity")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Asset catalog araması. Source filtresi yoksa 4 kaynaktan da çekilir;
    sırasıyla commodity, binance, coingecko, tefas. Toplam `limit` ile sınırlı."""
    sources = [source] if source else ["commodity", "binance", "coingecko", "tefas"]
    items: list[AssetCatalogItem] = []

    handlers = {
        "commodity": _search_commodity,  # sync
        "binance":   _search_binance,    # async
        "coingecko": _search_coingecko,  # async
        "tefas":     _search_tefas,      # async
    }
    for src in sources:
        handler = handlers.get(src)
        if not handler:
            continue
        remaining = limit - len(items)
        if remaining <= 0:
            break
        result = handler(q, remaining)
        items.extend(await result if hasattr(result, "__await__") else result)

    return items[:limit]
