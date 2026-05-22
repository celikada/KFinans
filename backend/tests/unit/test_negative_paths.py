"""TEST-005 (FAZ H): Negative path testleri — timeout, ConnectionError,
malformed JSON, race condition.

Mevcut testler: 503 + 429 birer ornek vardi. Bu dosya su asagidaki kanitlanan
gercek production scenarios'i kapsar:
  - httpx.TimeoutException -> service None doner / health_issues'a yazilir
  - httpx.ConnectError -> ayni sekilde graceful degradation
  - Malformed JSON (200 OK ama gecersiz body) -> exception'i yakalar
  - Refresh rotation race: ayni token paralel iki istekle 1 basarili / 1 401

Anthropic SDK'nin spec'i (advisor.py'de) zaten test edilmis (test_advisor.py
TestAdvisorExceptionMapping) — burada finansal/blockchain servislerinin
negative path'i kapsanir.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.stocks import _fetch_one, fetch_stock_quotes

# ─── Yahoo Finance (services/stocks.py) ─────────────────────────────────


@pytest.mark.asyncio
async def test_yahoo_timeout_returns_none():
    """httpx.ReadTimeout -> _fetch_one None doner (graceful)."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))

    result = await _fetch_one(client, "AAPL")
    assert result is None


@pytest.mark.asyncio
async def test_yahoo_connect_error_returns_none():
    """httpx.ConnectError -> None."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    result = await _fetch_one(client, "AAPL")
    assert result is None


@pytest.mark.asyncio
async def test_yahoo_malformed_json_returns_none():
    """200 OK ama gecersiz JSON -> None (KeyError yakalar)."""
    response = MagicMock()
    response.status_code = 200
    response.json = lambda: {"chart": {"error": "no data"}}  # 'result' yok

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=response)

    result = await _fetch_one(client, "TICKER")
    assert result is None


@pytest.mark.asyncio
async def test_yahoo_500_returns_none():
    """5xx yanit -> None."""
    response = MagicMock()
    response.status_code = 500

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=response)

    result = await _fetch_one(client, "TICKER")
    assert result is None


@pytest.mark.asyncio
async def test_yahoo_partial_failure_returns_dict_with_nones():
    """fetch_stock_quotes: bir ticker fail olursa diger ticker basarili.
    Dict birinde None birinde StockQuote olmali."""
    import time

    good_response = MagicMock()
    good_response.status_code = 200
    good_response.json = lambda: {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 100.0,
                        "regularMarketTime": int(time.time()) - 600,
                        "currency": "USD",
                        "marketState": "REGULAR",
                    }
                }
            ]
        }
    }

    bad_response = MagicMock()
    bad_response.status_code = 500

    side_effects = {
        "https://query1.finance.yahoo.com/v8/finance/chart/GOOD": good_response,
        "https://query1.finance.yahoo.com/v8/finance/chart/BAD": bad_response,
    }

    async def _get(url, **kwargs):
        for k, v in side_effects.items():
            if url.startswith(k):
                return v
        raise httpx.ConnectError("unexpected url")

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_get)
        MockClient.return_value.__aenter__.return_value = mock_client
        result = await fetch_stock_quotes(["GOOD", "BAD"])

    assert result["GOOD"] is not None
    assert result["GOOD"].price == Decimal("100.0")
    assert result["BAD"] is None


# Refresh rotation race testi integration seviyede (test_logout.py uygun
# yer); unit test users tablosuna ihtiyac duydugu icin burada degil.
# Multi-RPC fallback testi servis-internal fonksiyonlara bagimli — service
# refactor edilirken ayri test yazilmali.
