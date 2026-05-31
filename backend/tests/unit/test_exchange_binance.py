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


# ---------------------------------------------------------------------------
# Simple Earn (flexible + locked) endpoint testleri
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_flexible_earn_paginates_and_aggregates():
    """hasNextPage=True iken sayfa atlanir; ayni asset toplanir."""
    route = respx.get("https://api.binance.com/sapi/v1/simple-earn/flexible/position")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "rows": [
                    {"asset": "BTC", "totalAmount": "0.1"},
                    {"asset": "ETH", "totalAmount": "1.0"},
                    {"asset": "ZERO", "totalAmount": "0"},  # 0 -> atla
                    {"asset": "", "totalAmount": "5"},  # bos asset -> atla
                ],
                "hasNextPage": True,
            },
        ),
        httpx.Response(
            200,
            json={"rows": [{"asset": "BTC", "totalAmount": "0.2"}], "hasNextPage": False},
        ),
    ]
    svc = BinanceService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_flexible_earn(client)
    assert bal["BTC"] == Decimal("0.3")  # 0.1 + 0.2 (iki sayfa)
    assert bal["ETH"] == Decimal("1.0")
    assert "ZERO" not in bal
    assert "" not in bal


@pytest.mark.asyncio
@respx.mock
async def test_get_flexible_earn_breaks_on_non_200():
    """200 disi cevap -> dongu kirilir, bos dict."""
    respx.get("https://api.binance.com/sapi/v1/simple-earn/flexible/position").mock(return_value=httpx.Response(403, json={"msg": "no permission"}))
    svc = BinanceService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_flexible_earn(client)
    assert bal == {}


@pytest.mark.asyncio
@respx.mock
async def test_get_locked_earn_aggregates():
    """Locked earn 'amount' alanindan toplanir."""
    respx.get("https://api.binance.com/sapi/v1/simple-earn/locked/position").mock(
        return_value=httpx.Response(
            200,
            json={
                "rows": [
                    {"asset": "BNB", "amount": "3.5"},
                    {"asset": "BNB", "amount": "1.5"},
                    {"asset": "DOT", "amount": "0"},
                ],
                "hasNextPage": False,
            },
        )
    )
    svc = BinanceService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_locked_earn(client)
    assert bal["BNB"] == Decimal("5.0")
    assert "DOT" not in bal


@pytest.mark.asyncio
@respx.mock
async def test_get_locked_earn_breaks_on_non_200():
    respx.get("https://api.binance.com/sapi/v1/simple-earn/locked/position").mock(return_value=httpx.Response(401))
    svc = BinanceService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_locked_earn(client)
    assert bal == {}


# ---------------------------------------------------------------------------
# fetch() full integration — tum endpoint'ler mock'lanir
# ---------------------------------------------------------------------------


def _mock_time():
    import time as t

    respx.get("https://api.binance.com/api/v3/time").mock(return_value=httpx.Response(200, json={"serverTime": int(t.time() * 1000)}))


def _mock_empty_earn():
    respx.get("https://api.binance.com/sapi/v1/simple-earn/flexible/position").mock(return_value=httpx.Response(200, json={"rows": [], "hasNextPage": False}))
    respx.get("https://api.binance.com/sapi/v1/simple-earn/locked/position").mock(return_value=httpx.Response(200, json={"rows": [], "hasNextPage": False}))


@pytest.mark.asyncio
@respx.mock
async def test_fetch_builds_assets_with_price_conversion():
    """fetch() spot + earn + price'i birlestirir; USDT, BTC-pair, stablecoin fiyatlama."""
    _mock_time()
    respx.get("https://api.binance.com/api/v3/ticker/price").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"symbol": "BTCUSDT", "price": "60000"},
                {"symbol": "ETHUSDT", "price": "3000"},
                # ADA sadece BTC pariteli -> BTC uzerinden cevrilecek
                {"symbol": "ADABTC", "price": "0.00001"},
            ],
        )
    )
    respx.get("https://api.binance.com/api/v3/account").mock(
        return_value=httpx.Response(
            200,
            json={
                "balances": [
                    {"asset": "BTC", "free": "1", "locked": "0"},
                    {"asset": "ETH", "free": "2", "locked": "0"},
                    {"asset": "ADA", "free": "100", "locked": "0"},
                    {"asset": "USDT", "free": "500", "locked": "0"},
                ]
            },
        )
    )
    # flexible earn ETH ekler -> staked
    respx.get("https://api.binance.com/sapi/v1/simple-earn/flexible/position").mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"asset": "ETH", "totalAmount": "0.5"}], "hasNextPage": False},
        )
    )
    respx.get("https://api.binance.com/sapi/v1/simple-earn/locked/position").mock(return_value=httpx.Response(200, json={"rows": [], "hasNextPage": False}))

    svc = BinanceService("k", "s")
    assets = await svc.fetch()
    by_sym = {a.symbol: a for a in assets}

    assert by_sym["BTC"].unit_price_usd == Decimal("60000")
    assert by_sym["BTC"].liquid_quantity == Decimal("1")
    assert by_sym["ETH"].liquid_quantity == Decimal("2")
    assert by_sym["ETH"].staked_quantity == Decimal("0.5")
    assert by_sym["USDT"].unit_price_usd == Decimal("1")
    # ADA: 0.00001 * 60000 = 0.6 (BTC pariteli cevrim)
    assert by_sym["ADA"].unit_price_usd == Decimal("0.60000000")
    for a in assets:
        assert a.provider == "binance"
        assert a.asset_type == "crypto"
        assert a.source_type == "exchange"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_skips_unknown_price_tokens():
    """Fiyati bilinmeyen (USDT/BTC pariteli olmayan) token atilir."""
    _mock_time()
    respx.get("https://api.binance.com/api/v3/ticker/price").mock(return_value=httpx.Response(200, json=[{"symbol": "BTCUSDT", "price": "60000"}]))
    respx.get("https://api.binance.com/api/v3/account").mock(
        return_value=httpx.Response(
            200,
            json={
                "balances": [
                    {"asset": "BTC", "free": "1", "locked": "0"},
                    {"asset": "WEIRDTOKEN", "free": "1000", "locked": "0"},  # fiyat yok -> atla
                ]
            },
        )
    )
    _mock_empty_earn()
    svc = BinanceService("k", "s")
    assets = await svc.fetch()
    syms = {a.symbol for a in assets}
    assert "BTC" in syms
    assert "WEIRDTOKEN" not in syms


@pytest.mark.asyncio
@respx.mock
async def test_fetch_empty_when_no_balances():
    """Hic bakiye yoksa bos liste."""
    _mock_time()
    respx.get("https://api.binance.com/api/v3/ticker/price").mock(return_value=httpx.Response(200, json=[{"symbol": "BTCUSDT", "price": "60000"}]))
    respx.get("https://api.binance.com/api/v3/account").mock(return_value=httpx.Response(200, json={"balances": []}))
    _mock_empty_earn()
    svc = BinanceService("k", "s")
    assets = await svc.fetch()
    assert assets == []
