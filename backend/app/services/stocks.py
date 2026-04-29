import asyncio
import logging
from decimal import Decimal
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


@dataclass
class StockQuote:
    ticker: str
    name: str
    price: Decimal
    currency: str


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
        price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
        if not price:
            return None
        return StockQuote(
            ticker=ticker,
            name=meta.get("longName") or meta.get("shortName") or ticker,
            price=Decimal(str(price)),
            currency=meta.get("currency", "USD"),
        )
    except Exception:
        return None


async def fetch_stock_quotes(tickers: list[str]) -> dict[str, StockQuote | None]:
    """Verilen ticker'lar için Yahoo Finance'ten anlık fiyat çeker."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, t) for t in tickers])
    return {ticker: quote for ticker, quote in zip(tickers, results)}
