"""TEST-020: services/exchange/icrypex.py — iCrypex OAuth2 ROPC testleri.

email->api_key, password->api_secret. Token grant + spot + earn + tickers.
respx ile mock; gercek iCrypex API'ye gidilmez.
"""

from decimal import Decimal

import httpx
import pytest
import respx

from app.services.exchange.icrypex import (
    _EARN_URL,
    _SPOT_URL,
    _STABLECOIN_USD,
    _TICKERS_URL,
    _TOKEN_URL,
    ICrypexService,
)


def test_init_stores_credentials():
    svc = ICrypexService("user@example.com", "pw")
    assert svc._email == "user@example.com"
    assert svc._password == "pw"


def test_stablecoin_constants():
    assert _STABLECOIN_USD["USDT"] == Decimal("1")
    assert _STABLECOIN_USD["DAI"] == Decimal("1")


# ---------------------------------------------------------------------------
# _get_access_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_success():
    respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok-123"}))
    svc = ICrypexService("e", "p")
    async with httpx.AsyncClient() as client:
        token = await svc._get_access_token(client)
    assert token == "tok-123"


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_raises_on_auth_failure():
    respx.post(_TOKEN_URL).mock(return_value=httpx.Response(400, text="invalid_grant"))
    svc = ICrypexService("e", "bad")
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="iCrypex oturum açılamadı"):
            await svc._get_access_token(client)


# ---------------------------------------------------------------------------
# _parse_spot
# ---------------------------------------------------------------------------


def test_parse_spot_list_form():
    svc = ICrypexService("e", "p")
    data = [
        {"asset": "btc", "total": "1.0", "available": "0.8"},  # lowercase -> upper
        {"asset": "ETH", "total": "2.0"},  # available yok -> total
        {"asset": "ZERO", "total": "0"},  # 0 -> atla
        {"asset": "", "total": "5"},  # bos -> atla
    ]
    bal = svc._parse_spot(data)
    assert bal["BTC"] == {"liquid": Decimal("0.8"), "staked": Decimal("0.2")}
    assert bal["ETH"] == {"liquid": Decimal("2.0"), "staked": Decimal("0")}
    assert "ZERO" not in bal
    assert "" not in bal


def test_parse_spot_content_wrapper():
    svc = ICrypexService("e", "p")
    data = {"content": [{"asset": "USDT", "total": "100", "available": "100"}]}
    bal = svc._parse_spot(data)
    assert bal["USDT"]["liquid"] == Decimal("100")
    assert bal["USDT"]["staked"] == Decimal("0")


# ---------------------------------------------------------------------------
# _apply_earn
# ---------------------------------------------------------------------------


def test_apply_earn_adds_to_existing_and_new():
    svc = ICrypexService("e", "p")
    balances = {"BTC": {"liquid": Decimal("1"), "staked": Decimal("0")}}
    earn = [
        {"status": "Earn", "assetSymbol": "btc", "quantity": "0.5", "rewardQuantity": "0.1"},
        {"status": "Redemption", "assetSymbol": "ETH", "quantity": "2", "rewardQuantity": "0"},
        {"status": "Completed", "assetSymbol": "ADA", "quantity": "100"},  # haric tutulur
        {"status": "Earn", "assetSymbol": "", "quantity": "5"},  # bos -> atla
        {"status": "Earn", "assetSymbol": "DOT", "quantity": "0", "rewardQuantity": "0"},  # 0 -> atla
    ]
    svc._apply_earn(balances, earn)
    assert balances["BTC"]["staked"] == Decimal("0.6")  # mevcut'a eklendi
    assert balances["ETH"] == {"liquid": Decimal("0"), "staked": Decimal("2")}  # yeni
    assert "ADA" not in balances  # Completed haric
    assert "DOT" not in balances


# ---------------------------------------------------------------------------
# _price
# ---------------------------------------------------------------------------


def test_price_stablecoin():
    svc = ICrypexService("e", "p")
    assert svc._price("USDT", {}) == Decimal("1")


def test_price_from_ticker():
    svc = ICrypexService("e", "p")
    tickers = {"BTCUSDT": {"last": "61000.5"}}
    assert svc._price("BTC", tickers) == Decimal("61000.5")


def test_price_zero_when_missing():
    svc = ICrypexService("e", "p")
    assert svc._price("XYZ", {}) == Decimal("0")


# ---------------------------------------------------------------------------
# fetch()
# ---------------------------------------------------------------------------


def _mock_token():
    respx.post(_TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "tok"}))


@pytest.mark.asyncio
@respx.mock
async def test_fetch_combines_spot_earn_tickers():
    _mock_token()
    respx.get(_SPOT_URL).mock(
        return_value=httpx.Response(200, json=[{"asset": "BTC", "total": "1.0", "available": "1.0"}, {"asset": "USDT", "total": "500", "available": "500"}])
    )
    respx.get(_EARN_URL).mock(return_value=httpx.Response(200, json=[{"status": "Earn", "assetSymbol": "BTC", "quantity": "0.5", "rewardQuantity": "0.05"}]))
    respx.get(_TICKERS_URL).mock(return_value=httpx.Response(200, json=[{"symbol": "BTCUSDT", "last": "60000"}]))

    svc = ICrypexService("e", "p")
    assets = await svc.fetch()
    by = {a.symbol: a for a in assets}
    assert by["BTC"].liquid_quantity == Decimal("1.0")
    assert by["BTC"].staked_quantity == Decimal("0.55")  # 0.5 + 0.05 reward
    assert by["BTC"].unit_price_usd == Decimal("60000")
    assert by["USDT"].unit_price_usd == Decimal("1")
    for a in assets:
        assert a.provider == "icrypex"
        assert a.asset_type == "crypto"
        assert a.source_type == "exchange"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_ignores_earn_when_non_200():
    """Earn endpoint 200 disi ise sadece spot kullanilir."""
    _mock_token()
    respx.get(_SPOT_URL).mock(return_value=httpx.Response(200, json=[{"asset": "ETH", "total": "3", "available": "3"}]))
    respx.get(_EARN_URL).mock(return_value=httpx.Response(403))
    respx.get(_TICKERS_URL).mock(return_value=httpx.Response(200, json=[{"symbol": "ETHUSDT", "last": "3000"}]))
    svc = ICrypexService("e", "p")
    assets = await svc.fetch()
    eth = next(a for a in assets if a.symbol == "ETH")
    assert eth.liquid_quantity == Decimal("3")
    assert eth.staked_quantity == Decimal("0")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_raises_when_spot_http_error():
    _mock_token()
    respx.get(_SPOT_URL).mock(return_value=httpx.Response(500))
    respx.get(_EARN_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.get(_TICKERS_URL).mock(return_value=httpx.Response(200, json=[]))
    svc = ICrypexService("e", "p")
    with pytest.raises(httpx.HTTPStatusError):
        await svc.fetch()


@pytest.mark.asyncio
@respx.mock
async def test_fetch_empty_balances():
    _mock_token()
    respx.get(_SPOT_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.get(_EARN_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.get(_TICKERS_URL).mock(return_value=httpx.Response(200, json=[]))
    svc = ICrypexService("e", "p")
    assets = await svc.fetch()
    assert assets == []


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_health_check_true_on_200():
    _mock_token()
    respx.get(_SPOT_URL).mock(return_value=httpx.Response(200, json=[]))
    svc = ICrypexService("e", "p")
    assert await svc.health_check() is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_false_on_token_failure():
    respx.post(_TOKEN_URL).mock(return_value=httpx.Response(400, text="bad"))
    svc = ICrypexService("e", "bad")
    assert await svc.health_check() is False


@pytest.mark.asyncio
@respx.mock
async def test_health_check_false_on_network_error():
    respx.post(_TOKEN_URL).mock(side_effect=httpx.ConnectError("down"))
    svc = ICrypexService("e", "p")
    assert await svc.health_check() is False
