"""TEST-020 (FAZ H): services/exchange/binance.py — CCXT/HTTP wrapper testleri.

HMAC sign + price_of conversion + LD* receipt filter + endpoint mock.
Gercek Binance API'ye gidilmez; respx mock'lanir.
"""

import hashlib
import hmac
from decimal import Decimal

import httpx
import pytest
import respx

from app.services.exchange.binance import (
    _STABLECOIN_USD,
    BinanceService,
)


def test_stablecoin_constants():
    """USDT/USDC/BUSD = $1; TRY $0 (Binance USDTRY pariteleri ayri)."""
    assert _STABLECOIN_USD["USDT"] == Decimal("1")
    assert _STABLECOIN_USD["USDC"] == Decimal("1")
    assert _STABLECOIN_USD["TRY"] == Decimal("0")


def test_sign_creates_hmac_signature():
    """_sign HMAC-SHA256 imza ekler."""
    svc = BinanceService("test_key", "test_secret")
    params = svc._sign({"foo": "bar"})

    assert "timestamp" in params
    assert "recvWindow" in params
    assert "signature" in params
    # Imza 64 char hex
    assert len(params["signature"]) == 64
    assert all(c in "0123456789abcdef" for c in params["signature"])


def test_sign_hmac_correctness():
    """Sabit secret + sabit timestamp ile bilinen HMAC sonucu uretilir."""
    svc = BinanceService("k", "s")
    svc._time_offset_ms = 0
    # Determinist test icin time monkey patch yerine sign sonrasi dogru
    # algorithm uygulandigini dogrularz
    params = {"a": "1", "b": "2"}
    signed = svc._sign(params.copy())
    # Manuel hesapla
    from urllib.parse import urlencode

    query = urlencode({k: v for k, v in signed.items() if k != "signature"})
    expected = hmac.new(b"s", query.encode(), hashlib.sha256).hexdigest()
    assert signed["signature"] == expected


def test_auth_header_uses_api_key():
    svc = BinanceService("MY-KEY", "secret")
    h = svc._auth_header()
    assert h == {"X-MBX-APIKEY": "MY-KEY"}


@pytest.mark.asyncio
@respx.mock
async def test_get_all_prices_returns_decimal_dict():
    """Ticker price endpoint -> {symbol: Decimal} mapping."""
    respx.get("https://api.binance.com/api/v3/ticker/price").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"symbol": "BTCUSDT", "price": "65000.50"},
                {"symbol": "ETHUSDT", "price": "3500.25"},
            ],
        )
    )
    svc = BinanceService("k", "s")
    async with httpx.AsyncClient() as client:
        prices = await svc._get_all_prices(client)
    assert prices["BTCUSDT"] == Decimal("65000.50")
    assert prices["ETHUSDT"] == Decimal("3500.25")


@pytest.mark.asyncio
@respx.mock
async def test_get_spot_balances_filters_ld_receipt_tokens():
    """LD* receipt tokenlari (Simple Earn placeholder) atilmali."""
    respx.get("https://api.binance.com/api/v3/account").mock(
        return_value=httpx.Response(
            200,
            json={
                "balances": [
                    {"asset": "BTC", "free": "0.5", "locked": "0"},
                    {"asset": "LDBTC", "free": "0.1", "locked": "0"},  # LD receipt -> SKIP
                    {"asset": "ETH", "free": "2", "locked": "0.5"},
                    {"asset": "DUST", "free": "0", "locked": "0"},  # 0 balance -> SKIP
                ],
            },
        )
    )
    svc = BinanceService("k", "s")
    async with httpx.AsyncClient() as client:
        balances = await svc._get_spot_balances(client)
    # BTC + ETH (free + locked) gozukmeli; LD* ve 0 atilmali
    assert "BTC" in balances and balances["BTC"] == Decimal("0.5")
    assert "ETH" in balances and balances["ETH"] == Decimal("2.5")  # 2 + 0.5
    assert "LDBTC" not in balances
    assert "DUST" not in balances


@pytest.mark.asyncio
@respx.mock
async def test_sync_time_calculates_offset():
    """Server time'a gore offset hesaplanir (clock skew duzelt)."""
    import time as t

    fake_server_ms = int(t.time() * 1000) + 5000  # 5sn ileride
    respx.get("https://api.binance.com/api/v3/time").mock(return_value=httpx.Response(200, json={"serverTime": fake_server_ms}))
    svc = BinanceService("k", "s")
    async with httpx.AsyncClient() as client:
        await svc._sync_time(client)
    # Offset yaklasik +5000ms (us bazinda dalgalanma var, +- 100ms tolerans)
    assert 4000 <= svc._time_offset_ms <= 6000


@pytest.mark.asyncio
@respx.mock
async def test_health_check_true_on_200():
    """200 -> health True."""
    respx.get("https://api.binance.com/api/v3/account").mock(return_value=httpx.Response(200, json={"balances": []}))
    svc = BinanceService("k", "s")
    assert await svc.health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_false_on_401():
    """Yetkisiz API key -> health False (exception yakalar)."""
    respx.get("https://api.binance.com/api/v3/account").mock(return_value=httpx.Response(401, json={"code": -2014, "msg": "API-key invalid"}))
    svc = BinanceService("bad_key", "bad_secret")
    assert await svc.health_check() is False


@pytest.mark.asyncio
@respx.mock
async def test_health_check_false_on_network_error():
    """Network exception graceful -> False."""
    respx.get("https://api.binance.com/api/v3/account").mock(side_effect=httpx.ConnectError("network down"))
    svc = BinanceService("k", "s")
    assert await svc.health_check() is False
