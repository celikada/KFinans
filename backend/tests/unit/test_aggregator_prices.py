"""Aggregator fiyat fetch fonksiyonlari — Binance spot + CoinGecko fallback.

respx ile dis HTTP mock'lanir; DB gerekmez. fetch_spot_prices,
fetch_coingecko_prices, fetch_coingecko_prices_by_ids, fetch_combined_prices,
_get_coingecko_id_map ve lookup_usd_price kapsanir.
"""

from decimal import Decimal

import pytest
import respx
from httpx import Response

from app.services import aggregator
from app.services.aggregator import (
    _BINANCE_PRICE_URL,
    _COINGECKO_LIST_URL,
    _COINGECKO_PRICE_URL,
    fetch_coingecko_prices,
    fetch_coingecko_prices_by_ids,
    fetch_combined_prices,
    fetch_spot_prices,
    lookup_usd_price,
)


@pytest.fixture(autouse=True)
def _clear_cg_cache():
    aggregator._coingecko_list_cache = None
    # 429 retry backoff'unu testlerde 0'la (gerçek sleep(1.5) yavaşlatmasın) + sakla/geri-yükle.
    _saved_backoff = aggregator._CG_RETRY_BACKOFF_SEC
    aggregator._CG_RETRY_BACKOFF_SEC = 0
    yield
    aggregator._coingecko_list_cache = None
    aggregator._CG_RETRY_BACKOFF_SEC = _saved_backoff


# ─── fetch_spot_prices ────────────────────────────────────────────────────────
class TestFetchSpotPrices:
    @pytest.mark.asyncio
    async def test_returns_usdt_pair_prices(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_BINANCE_PRICE_URL).mock(return_value=Response(200, json=[{"symbol": "BTCUSDT", "price": "60000"}, {"symbol": "ETHUSDT", "price": "3000"}]))
            out = await fetch_spot_prices(["BTC", "ETH", "MISSING"])
        assert out["BTC"] == Decimal("60000")
        assert out["ETH"] == Decimal("3000")
        assert out["MISSING"] == Decimal("0")


# ─── _get_coingecko_id_map + fetch_coingecko_prices ──────────────────────────
class TestCoinGeckoPrices:
    _LIST = [
        {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        {"id": "icrypex-token", "symbol": "icpx", "name": "iCrypex"},
        {"id": "duplicate-first", "symbol": "dup", "name": "First"},
        {"id": "duplicate-second", "symbol": "dup", "name": "Second"},
    ]

    @pytest.mark.asyncio
    async def test_maps_symbols_and_overrides(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=self._LIST))
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(200, json={"bitcoin": {"usd": 60000.0}, "icrypex-token": {"usd": 0.5}}))
            out = await fetch_coingecko_prices(["BTC", "ICPX"])
        assert out["BTC"] == Decimal("60000.0")
        # ICPX override → icrypex-token
        assert out["ICPX"] == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_first_symbol_wins_for_duplicates(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=self._LIST))
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(200, json={"duplicate-first": {"usd": 1.0}}))
            out = await fetch_coingecko_prices(["DUP"])
        assert out["DUP"] == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_empty_symbols_returns_empty(self):
        assert await fetch_coingecko_prices([]) == {}

    @pytest.mark.asyncio
    async def test_list_fetch_failure_returns_empty(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(500))
            out = await fetch_coingecko_prices(["BTC"])
        assert out == {}

    @pytest.mark.asyncio
    async def test_no_known_symbols_returns_empty(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=self._LIST))
            out = await fetch_coingecko_prices(["UNKNOWNXYZ"])
        assert out == {}

    @pytest.mark.asyncio
    async def test_price_fetch_failure_returns_empty(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=self._LIST))
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(500))
            out = await fetch_coingecko_prices(["BTC"])
        assert out == {}

    @pytest.mark.asyncio
    async def test_id_map_cache_avoids_second_list_call(self):
        with respx.mock(assert_all_called=False) as rsx:
            route = rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=self._LIST))
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(200, json={"bitcoin": {"usd": 1.0}}))
            await fetch_coingecko_prices(["BTC"])
            await fetch_coingecko_prices(["BTC"])
        assert route.call_count == 1


# ─── fetch_coingecko_prices_by_ids ───────────────────────────────────────────
class TestCoinGeckoPricesByIds:
    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        assert await fetch_coingecko_prices_by_ids([]) == {}

    @pytest.mark.asyncio
    async def test_returns_prices_for_ids(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(200, json={"tether-gold": {"usd": 2500.0}, "ripple": {"usd": 0.6}}))
            out = await fetch_coingecko_prices_by_ids(["tether-gold", "ripple", "missing"])
        assert out["tether-gold"] == Decimal("2500.0")
        assert out["ripple"] == Decimal("0.6")
        assert "missing" not in out

    @pytest.mark.asyncio
    async def test_http_failure_returns_empty(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(500))
            out = await fetch_coingecko_prices_by_ids(["bitcoin"])
        assert out == {}

    @pytest.mark.asyncio
    async def test_429_falls_back_to_last_good(self):
        """Önce başarı (son-iyi'yi doldurur), sonra 429 → son-iyi fiyat korunur (0 DEĞİL)."""
        # 1) Başarılı çekim — son-iyi'ye yaz
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(200, json={"silver-rstock": {"usd": 0.39987}}))
            ok = await fetch_coingecko_prices_by_ids(["silver-rstock"])
        assert ok["silver-rstock"] == Decimal("0.39987")

        # 2) 429 (retry de 429) → son-iyi fiyat dönmeli, boş/0 değil
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(429))
            fallback = await fetch_coingecko_prices_by_ids(["silver-rstock"])
        assert fallback["silver-rstock"] == Decimal("0.39987")

    @pytest.mark.asyncio
    async def test_429_then_retry_succeeds(self):
        """İlk 429, retry'da 200 → fiyat döner (backoff fixture'da 0'lanmış)."""
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_COINGECKO_PRICE_URL).mock(side_effect=[Response(429), Response(200, json={"ripple": {"usd": 0.6}})])
            out = await fetch_coingecko_prices_by_ids(["ripple"])
        assert out["ripple"] == Decimal("0.6")


# ─── fetch_combined_prices ────────────────────────────────────────────────────
class TestFetchCombinedPrices:
    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        assert await fetch_combined_prices([]) == {}

    @pytest.mark.asyncio
    async def test_all_on_binance_skips_coingecko(self):
        with respx.mock(assert_all_called=False) as rsx:
            binance = rsx.get(_BINANCE_PRICE_URL).mock(return_value=Response(200, json=[{"symbol": "BTCUSDT", "price": "60000"}]))
            cg = rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=[]))
            out = await fetch_combined_prices(["BTC"])
        assert out["BTC"] == Decimal("60000")
        assert binance.called
        assert not cg.called

    @pytest.mark.asyncio
    async def test_falls_back_to_coingecko_for_missing(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_BINANCE_PRICE_URL).mock(return_value=Response(200, json=[{"symbol": "BTCUSDT", "price": "60000"}]))
            rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=[{"id": "icrypex-token", "symbol": "icpx", "name": "i"}]))
            rsx.get(_COINGECKO_PRICE_URL).mock(return_value=Response(200, json={"icrypex-token": {"usd": 0.5}}))
            out = await fetch_combined_prices(["BTC", "ICPX"])
        assert out["BTC"] == Decimal("60000")
        assert out["ICPX"] == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_stablecoins_not_sent_to_coingecko(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(_BINANCE_PRICE_URL).mock(return_value=Response(200, json=[]))
            cg_list = rsx.get(_COINGECKO_LIST_URL).mock(return_value=Response(200, json=[]))
            out = await fetch_combined_prices(["USDT"])
        # USDT binance'te 0 ama stablecoin → CoinGecko'ya gitmez
        assert out["USDT"] == Decimal("0")
        assert not cg_list.called


# ─── lookup_usd_price ─────────────────────────────────────────────────────────
class TestLookupUsdPrice:
    def test_stablecoin_returns_one(self):
        assert lookup_usd_price("USDT", {}) == Decimal("1")
        assert lookup_usd_price("DAI", {}) == Decimal("1")

    def test_direct_price(self):
        assert lookup_usd_price("BTC", {"BTC": Decimal("60000")}) == Decimal("60000")

    def test_alias_resolution(self):
        # stETH → ETH alias
        assert lookup_usd_price("STETH", {"ETH": Decimal("3000")}) == Decimal("3000")
        assert lookup_usd_price("WBTC", {"BTC": Decimal("60000")}) == Decimal("60000")

    def test_alias_missing_returns_zero(self):
        assert lookup_usd_price("SAVAX", {}) == Decimal("0")

    def test_unknown_returns_zero(self):
        assert lookup_usd_price("FOOBAR", {}) == Decimal("0")
