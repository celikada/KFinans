import asyncio
import logging
import time
from decimal import Decimal
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# FIN-004 (FAZ H): regularMarketTime'dan kac saniye gec ise stale say.
# Yahoo cuma kapanis 21:00 UTC, pazartesi 13:30 UTC acilis -> ~64 saat hafta sonu;
# normal hafta ici overnight ~13 saat. 30 saat esigi: hafta sonu/tatil normaldir,
# ama hafta ici 30+ saatlik gecmis fiyat halted/delisted isaretidir.
_STALE_THRESHOLD_SECONDS = 30 * 3600


@dataclass
class StockQuote:
    ticker: str
    name: str
    price: Decimal
    currency: str
    # FIN-004: Eski fiyat (chartPreviousClose fallback ya da regularMarketTime > 30 saat)
    # is_stale=True ise UI rozet + snapshot health_issues "stocks:stale_price" eklenir.
    is_stale: bool = False
    market_state: str | None = None  # 'REGULAR'|'CLOSED'|'PRE'|'POST'|None


async def _fetch_one(client: httpx.AsyncClient, ticker: str) -> StockQuote | None:
    try:
        r = await client.get(
            _YF_URL.format(ticker=ticker),
            params={"interval": "1d", "range": "1d"},
            headers=_YF_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        result = data.get("chart", {}).get("result")
        if not result:
            return None
        meta = result[0]["meta"]
        # FIN-004: regularMarketPrice yoksa chartPreviousClose'a dus, ama is_stale=True isaretle.
        regular = meta.get("regularMarketPrice")
        previous = meta.get("chartPreviousClose")
        price = regular if regular is not None else previous
        if not price:
            return None

        is_stale = regular is None  # fallback'e dustuk
        # regularMarketTime epoch (saniye); 30+ saatten eski ise halted/delisted ihtimali
        market_time = meta.get("regularMarketTime")
        if market_time:
            age = time.time() - market_time
            if age > _STALE_THRESHOLD_SECONDS:
                is_stale = True
                logger.info(
                    "Yahoo stale price: ticker=%s, age=%dh, marketState=%s",
                    ticker, age // 3600, meta.get("marketState"),
                )

        return StockQuote(
            ticker=ticker,
            name=meta.get("longName") or meta.get("shortName") or ticker,
            price=Decimal(str(price)),
            currency=meta.get("currency", "USD"),
            is_stale=is_stale,
            market_state=meta.get("marketState"),
        )
    except Exception:
        return None


async def fetch_stock_quotes(tickers: list[str]) -> dict[str, StockQuote | None]:
    """Verilen ticker'lar için Yahoo Finance'ten anlık fiyat çeker."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, t) for t in tickers])
    return {ticker: quote for ticker, quote in zip(tickers, results)}
