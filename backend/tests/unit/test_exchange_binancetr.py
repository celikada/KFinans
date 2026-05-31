"""TEST-020: services/exchange/binancetr.py — Binance TR HTTP wrapper testleri.

Iki mod: (1) API key + HMAC spot/earn, (2) session_token (cid cookie) ile
/bapi tek endpoint. respx ile mock; gercek Binance TR API'ye gidilmez.
"""

import hashlib
import hmac
from decimal import Decimal
from urllib.parse import urlencode

import httpx
import pytest
import respx

from app.services.exchange.binancetr import (
    _BASE_GLOBAL,
    _BASE_TR,
    _STABLECOIN_USD,
    BinanceTRService,
)


def test_stablecoin_constants():
    assert _STABLECOIN_USD["USDT"] == Decimal("1")
    assert _STABLECOIN_USD["FDUSD"] == Decimal("1")
    assert _STABLECOIN_USD["TRY"] == Decimal("0")


def test_init_strips_session_token():
    svc = BinanceTRService("k", "s", session_token="  abc  ")
    assert svc.session_token == "abc"
    assert svc._time_offset_ms == 0


def test_init_default_no_session_token():
    svc = BinanceTRService("k", "s")
    assert svc.session_token == ""


def test_sign_creates_hmac_signature():
    svc = BinanceTRService("k", "s")
    params = svc._sign({"foo": "bar"})
    assert "timestamp" in params
    assert params["recvWindow"] == 60000
    assert len(params["signature"]) == 64


def test_sign_hmac_correctness():
    svc = BinanceTRService("k", "mysecret")
    signed = svc._sign({"a": "1"})
    query = urlencode({k: v for k, v in signed.items() if k != "signature"})
    expected = hmac.new(b"mysecret", query.encode(), hashlib.sha256).hexdigest()
    assert signed["signature"] == expected


def test_auth_header():
    svc = BinanceTRService("MY-KEY", "s")
    assert svc._auth_header() == {"X-MBX-APIKEY": "MY-KEY"}


@pytest.mark.asyncio
@respx.mock
async def test_sync_time_uses_timestamp_field():
    import time as t

    fake = int(t.time() * 1000) + 4000
    respx.get(f"{_BASE_TR}/open/v1/common/time").mock(return_value=httpx.Response(200, json={"timestamp": fake}))
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        await svc._sync_time(client)
    assert 3000 <= svc._time_offset_ms <= 5000


@pytest.mark.asyncio
@respx.mock
async def test_sync_time_falls_back_when_no_timestamp():
    """timestamp alani yoksa offset ~0."""
    respx.get(f"{_BASE_TR}/open/v1/common/time").mock(return_value=httpx.Response(200, json={}))
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        await svc._sync_time(client)
    assert -1000 <= svc._time_offset_ms <= 1000


# ---------------------------------------------------------------------------
# _get_balances (spot, API key modu)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_balances_parses_accountassets():
    respx.get(f"{_BASE_TR}/open/v1/account/spot").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "accountAssets": [
                        {"asset": "BTC", "free": "0.5", "locked": "0.1"},
                        {"asset": "ETH", "free": "0", "locked": "0"},  # 0 -> atla
                        {"asset": "", "free": "5", "locked": "0"},  # bos -> atla
                    ]
                },
            },
        )
    )
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_balances(client)
    assert bal["BTC"] == Decimal("0.6")
    assert "ETH" not in bal
    assert "" not in bal


@pytest.mark.asyncio
@respx.mock
async def test_get_balances_data_as_list():
    """data dogrudan liste ise (accountAssets sarmali yok)."""
    respx.get(f"{_BASE_TR}/open/v1/account/spot").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "data": [{"asset": "USDT", "free": "100", "locked": "0"}]},
        )
    )
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_balances(client)
    assert bal["USDT"] == Decimal("100")


@pytest.mark.asyncio
@respx.mock
async def test_get_balances_raises_on_error_code():
    respx.get(f"{_BASE_TR}/open/v1/account/spot").mock(return_value=httpx.Response(200, json={"code": -1, "msg": "Yetkisiz"}))
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="Yetkisiz"):
            await svc._get_balances(client)


# ---------------------------------------------------------------------------
# _get_all_assets_via_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_all_assets_via_session_parses_free_locked_freeze():
    respx.post(f"{_BASE_TR}/bapi/asset/v3/private/asset-service/asset/get-user-asset").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": "000000",
                "data": [
                    {"asset": "BTC", "free": "1", "locked": "0.5", "freeze": "0.25"},
                    {"asset": "ZERO", "free": "0", "locked": "0", "freeze": "0"},
                ],
            },
        )
    )
    svc = BinanceTRService("k", "s", session_token="cid-token")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_all_assets_via_session(client)
    assert bal["BTC"] == Decimal("1.75")
    assert "ZERO" not in bal


@pytest.mark.asyncio
@respx.mock
async def test_get_all_assets_via_session_raises_on_non_200():
    respx.post(f"{_BASE_TR}/bapi/asset/v3/private/asset-service/asset/get-user-asset").mock(return_value=httpx.Response(401))
    svc = BinanceTRService("k", "s", session_token="expired")
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="session token"):
            await svc._get_all_assets_via_session(client)


@pytest.mark.asyncio
@respx.mock
async def test_get_all_assets_via_session_raises_on_error_code():
    respx.post(f"{_BASE_TR}/bapi/asset/v3/private/asset-service/asset/get-user-asset").mock(
        return_value=httpx.Response(200, json={"code": "100002", "message": "Imza hatasi"})
    )
    svc = BinanceTRService("k", "s", session_token="bad")
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="Imza hatasi"):
            await svc._get_all_assets_via_session(client)


# ---------------------------------------------------------------------------
# Earn endpoint'leri (sapi)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_flexible_earn_aggregates_and_paginates():
    route = respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/flexible/position")
    route.side_effect = [
        httpx.Response(200, json={"rows": [{"asset": "BTC", "totalAmount": "0.1"}], "hasNextPage": True}),
        httpx.Response(200, json={"rows": [{"asset": "BTC", "totalAmount": "0.2"}], "hasNextPage": False}),
    ]
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_flexible_earn(client)
    assert bal["BTC"] == Decimal("0.3")


@pytest.mark.asyncio
@respx.mock
async def test_get_flexible_earn_breaks_on_non_200():
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/flexible/position").mock(return_value=httpx.Response(404))
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_flexible_earn(client)
    assert bal == {}


@pytest.mark.asyncio
@respx.mock
async def test_get_flexible_earn_swallows_exception():
    """Network hatasi -> except branch -> bos dict."""
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/flexible/position").mock(side_effect=httpx.ConnectError("down"))
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_flexible_earn(client)
    assert bal == {}


@pytest.mark.asyncio
@respx.mock
async def test_get_locked_earn_aggregates():
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/locked/position").mock(
        return_value=httpx.Response(
            200,
            json={"rows": [{"asset": "DOT", "amount": "10"}, {"asset": "DOT", "amount": "5"}], "hasNextPage": False},
        )
    )
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_locked_earn(client)
    assert bal["DOT"] == Decimal("15")


@pytest.mark.asyncio
@respx.mock
async def test_get_locked_earn_breaks_on_non_200():
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/locked/position").mock(return_value=httpx.Response(403))
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_locked_earn(client)
    assert bal == {}


@pytest.mark.asyncio
@respx.mock
async def test_get_locked_earn_swallows_exception():
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/locked/position").mock(side_effect=httpx.ConnectError("down"))
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        bal = await svc._get_locked_earn(client)
    assert bal == {}


@pytest.mark.asyncio
@respx.mock
async def test_get_prices():
    respx.get(f"{_BASE_GLOBAL}/api/v3/ticker/price").mock(return_value=httpx.Response(200, json=[{"symbol": "BTCUSDT", "price": "60000"}]))
    svc = BinanceTRService("k", "s")
    async with httpx.AsyncClient() as client:
        prices = await svc._get_prices(client)
    assert prices["BTCUSDT"] == Decimal("60000")


# ---------------------------------------------------------------------------
# fetch() — iki mod
# ---------------------------------------------------------------------------


def _mock_time_and_prices(extra_prices=None):
    import time as t

    respx.get(f"{_BASE_TR}/open/v1/common/time").mock(return_value=httpx.Response(200, json={"timestamp": int(t.time() * 1000)}))
    rows = [{"symbol": "BTCUSDT", "price": "60000"}, {"symbol": "ETHUSDT", "price": "3000"}]
    if extra_prices:
        rows.extend(extra_prices)
    respx.get(f"{_BASE_GLOBAL}/api/v3/ticker/price").mock(return_value=httpx.Response(200, json=rows))


@pytest.mark.asyncio
@respx.mock
async def test_fetch_session_token_mode():
    """session_token modunda /bapi tek endpoint kullanilir; earn cagrilmaz."""
    _mock_time_and_prices(extra_prices=[{"symbol": "ADABTC", "price": "0.00001"}])
    respx.post(f"{_BASE_TR}/bapi/asset/v3/private/asset-service/asset/get-user-asset").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": "000000",
                "data": [
                    {"asset": "BTC", "free": "1", "locked": "0", "freeze": "0"},
                    {"asset": "USDT", "free": "100", "locked": "0", "freeze": "0"},
                    {"asset": "ADA", "free": "1000", "locked": "0", "freeze": "0"},  # BTC pariteli
                ],
            },
        )
    )
    svc = BinanceTRService("k", "s", session_token="cid-token")
    assets = await svc.fetch()
    by = {a.symbol: a for a in assets}
    assert by["BTC"].liquid_quantity == Decimal("1")
    assert by["BTC"].unit_price_usd == Decimal("60000")
    assert by["USDT"].unit_price_usd == Decimal("1")
    assert by["ADA"].unit_price_usd == Decimal("0.60000000")
    for a in assets:
        assert a.provider == "binancetr"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_api_key_mode_combines_spot_and_earn():
    """session_token yoksa spot + earn birlestirilir."""
    _mock_time_and_prices()
    respx.get(f"{_BASE_TR}/open/v1/account/spot").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "data": {"accountAssets": [{"asset": "ETH", "free": "2", "locked": "0"}]}},
        )
    )
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/flexible/position").mock(
        return_value=httpx.Response(200, json={"rows": [{"asset": "ETH", "totalAmount": "0.5"}], "hasNextPage": False})
    )
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/locked/position").mock(return_value=httpx.Response(200, json={"rows": [], "hasNextPage": False}))
    svc = BinanceTRService("k", "s")
    assets = await svc.fetch()
    eth = next(a for a in assets if a.symbol == "ETH")
    assert eth.liquid_quantity == Decimal("2")
    assert eth.staked_quantity == Decimal("0.5")
    assert eth.unit_price_usd == Decimal("3000")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_skips_unknown_price_token():
    _mock_time_and_prices()
    respx.get(f"{_BASE_TR}/open/v1/account/spot").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"accountAssets": [{"asset": "BTC", "free": "1", "locked": "0"}, {"asset": "NOPRICE", "free": "5", "locked": "0"}]},
            },
        )
    )
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/flexible/position").mock(return_value=httpx.Response(200, json={"rows": [], "hasNextPage": False}))
    respx.get(f"{_BASE_TR}/sapi/v1/simple-earn/locked/position").mock(return_value=httpx.Response(200, json={"rows": [], "hasNextPage": False}))
    svc = BinanceTRService("k", "s")
    assets = await svc.fetch()
    syms = {a.symbol for a in assets}
    assert "BTC" in syms
    assert "NOPRICE" not in syms


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_health_check_true_on_code_zero():
    import time as t

    respx.get(f"{_BASE_TR}/open/v1/common/time").mock(return_value=httpx.Response(200, json={"timestamp": int(t.time() * 1000)}))
    respx.get(f"{_BASE_TR}/open/v1/account/spot").mock(return_value=httpx.Response(200, json={"code": 0, "data": {}}))
    svc = BinanceTRService("k", "s")
    assert await svc.health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_false_on_error_code():
    import time as t

    respx.get(f"{_BASE_TR}/open/v1/common/time").mock(return_value=httpx.Response(200, json={"timestamp": int(t.time() * 1000)}))
    respx.get(f"{_BASE_TR}/open/v1/account/spot").mock(return_value=httpx.Response(200, json={"code": -1, "msg": "bad"}))
    svc = BinanceTRService("bad", "key")
    assert await svc.health_check() is False


@pytest.mark.asyncio
@respx.mock
async def test_health_check_false_on_network_error():
    respx.get(f"{_BASE_TR}/open/v1/common/time").mock(side_effect=httpx.ConnectError("down"))
    svc = BinanceTRService("k", "s")
    assert await svc.health_check() is False
