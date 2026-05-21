"""FIN-004 (FAZ H): Yahoo Finance stale price + halted/delisted detection.

Mock Yahoo Finance response. _fetch_one'a httpx mock client geçirilir.
"""

import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.stocks import _STALE_THRESHOLD_SECONDS, _fetch_one


def _yf_response(meta: dict) -> MagicMock:
    """Yahoo Finance Chart API formatinda mock response."""
    response = MagicMock()
    response.status_code = 200
    response.json = lambda: {"chart": {"result": [{"meta": meta}]}}
    return response


@pytest.mark.asyncio
async def test_fresh_price_not_stale():
    """regularMarketPrice mevcut + regularMarketTime yakin -> is_stale=False."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_yf_response(
            {
                "regularMarketPrice": 150.5,
                "regularMarketTime": int(time.time()) - 3600,  # 1 saat once
                "currency": "USD",
                "marketState": "REGULAR",
            }
        )
    )

    quote = await _fetch_one(client, "AAPL")
    assert quote is not None
    assert quote.price == Decimal("150.5")
    assert quote.is_stale is False
    assert quote.market_state == "REGULAR"


@pytest.mark.asyncio
async def test_fallback_to_previous_close_marks_stale():
    """regularMarketPrice yok, chartPreviousClose'a dustuk -> is_stale=True."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_yf_response(
            {
                # regularMarketPrice yok
                "chartPreviousClose": 100.0,
                "regularMarketTime": int(time.time()) - 3600,
                "currency": "USD",
                "marketState": "CLOSED",
            }
        )
    )

    quote = await _fetch_one(client, "TICKER1")
    assert quote is not None
    assert quote.price == Decimal("100.0")
    assert quote.is_stale is True


@pytest.mark.asyncio
async def test_old_market_time_marks_stale():
    """regularMarketTime > 30 saat -> is_stale=True (halted/delisted ihtimali)."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_yf_response(
            {
                "regularMarketPrice": 50.0,
                "regularMarketTime": int(time.time()) - _STALE_THRESHOLD_SECONDS - 3600,  # 31 saat once
                "currency": "USD",
                "marketState": "POSTPOST",
            }
        )
    )

    quote = await _fetch_one(client, "HALTED1")
    assert quote is not None
    assert quote.price == Decimal("50.0")
    assert quote.is_stale is True


@pytest.mark.asyncio
async def test_recent_market_time_not_stale():
    """regularMarketTime < 30 saat (overnight normal) -> is_stale=False."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        return_value=_yf_response(
            {
                "regularMarketPrice": 75.0,
                "regularMarketTime": int(time.time()) - 25 * 3600,  # 25 saat once (esik altinda)
                "currency": "TRY",
                "marketState": "CLOSED",
            }
        )
    )

    quote = await _fetch_one(client, "BIST.IS")
    assert quote is not None
    assert quote.is_stale is False
