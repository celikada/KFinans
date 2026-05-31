"""Commodity servisi (app/services/commodity.py) icin ek birim testler.

TCMB USD/TRY parse yollari, Yahoo fiyat cekme + fallback chain, cache TTL
kisaltma davranisi ve calculate_holding_value validasyon dallari respx + monkeypatch
ile kapsanir. DB gerekmez.
"""

import time
from decimal import Decimal
from types import SimpleNamespace

import pytest
import respx
from httpx import Response

import app.services.commodity as svc
from app.services.commodity import (
    TCMB_URL,
    _fetch_tcmb_usd_try,
    _fetch_yahoo_price_usd,
    _try_yahoo_symbols,
    calculate_holding_value,
    fetch_metal_prices,
)


@pytest.fixture(autouse=True)
def _reset_price_cache():
    svc._price_cache = None
    yield
    svc._price_cache = None


def _holding(**kw):
    defaults = dict(unit_type="gram", metal="gold", biga_code=None, coin_type=None, quantity=Decimal("1"))
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ─── _fetch_tcmb_usd_try ──────────────────────────────────────────────────────
class TestFetchTcmbUsdTry:
    @pytest.mark.asyncio
    async def test_skips_non_usd_then_finds_usd(self):
        xml = b"""<?xml version="1.0"?><Tarih_Date>
          <Currency CurrencyCode="EUR"><Unit>1</Unit><ForexBuying>44.0</ForexBuying></Currency>
          <Currency CurrencyCode="USD"><Unit>1</Unit><ForexBuying>40.0</ForexBuying></Currency>
        </Tarih_Date>"""
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=xml))
            rate = await _fetch_tcmb_usd_try()
        assert rate == Decimal("40.000000")

    @pytest.mark.asyncio
    async def test_raises_when_usd_missing(self):
        xml = b"""<?xml version="1.0"?><Tarih_Date>
          <Currency CurrencyCode="EUR"><Unit>1</Unit><ForexBuying>44.0</ForexBuying></Currency>
        </Tarih_Date>"""
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=xml))
            with pytest.raises(RuntimeError, match="USD/TRY"):
                await _fetch_tcmb_usd_try()

    @pytest.mark.asyncio
    async def test_raises_when_usd_has_no_buying(self):
        xml = b"""<?xml version="1.0"?><Tarih_Date>
          <Currency CurrencyCode="USD"><Unit>1</Unit></Currency>
        </Tarih_Date>"""
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=xml))
            with pytest.raises(RuntimeError):
                await _fetch_tcmb_usd_try()

    @pytest.mark.asyncio
    async def test_raises_on_invalid_unit(self):
        xml = b"""<?xml version="1.0"?><Tarih_Date>
          <Currency CurrencyCode="USD"><Unit>abc</Unit><ForexBuying>40.0</ForexBuying></Currency>
        </Tarih_Date>"""
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=xml))
            with pytest.raises(RuntimeError):
                await _fetch_tcmb_usd_try()


# ─── _fetch_yahoo_price_usd ───────────────────────────────────────────────────
class TestFetchYahooPriceUsd:
    @pytest.mark.asyncio
    async def test_regular_market_price(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(url__regex=r".*/chart/XAU=X.*").mock(return_value=Response(200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 3000.0}}]}}))
            price = await _fetch_yahoo_price_usd("XAU=X")
        assert price == Decimal("3000.0")

    @pytest.mark.asyncio
    async def test_falls_back_to_previous_close(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(url__regex=r".*/chart/X.*").mock(return_value=Response(200, json={"chart": {"result": [{"meta": {"previousClose": 2900.0}}]}}))
            price = await _fetch_yahoo_price_usd("XAU=X")
        assert price == Decimal("2900.0")

    @pytest.mark.asyncio
    async def test_malformed_response_raises(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(url__regex=r".*/chart/X.*").mock(return_value=Response(200, json={"chart": {"result": []}}))
            with pytest.raises(RuntimeError, match="alınamadı"):
                await _fetch_yahoo_price_usd("XAU=X")


# ─── _try_yahoo_symbols ───────────────────────────────────────────────────────
class TestTryYahooSymbols:
    @pytest.mark.asyncio
    async def test_first_symbol_fails_second_succeeds(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(url__regex=r".*/chart/XAU=X.*").mock(return_value=Response(500))
            rsx.get(url__regex=r".*/chart/GC=F.*").mock(return_value=Response(200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 3100.0}}]}}))
            price = await _try_yahoo_symbols(("XAU=X", "GC=F"), "Altın")
        assert price == Decimal("3100.0")

    @pytest.mark.asyncio
    async def test_all_fail_returns_zero(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(url__regex=r".*/chart/.*").mock(return_value=Response(500))
            price = await _try_yahoo_symbols(("XAU=X", "GC=F"), "Altın")
        assert price == Decimal("0")


# ─── fetch_metal_prices cache TTL shortening ──────────────────────────────────
class TestFetchMetalPricesCache:
    _TCMB = b"""<?xml version="1.0"?><Tarih_Date>
      <Currency CurrencyCode="USD"><Unit>1</Unit><ForexBuying>40.0</ForexBuying></Currency>
    </Tarih_Date>"""

    @pytest.mark.asyncio
    async def test_zero_prices_shorten_cache_ttl(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=self._TCMB))
            rsx.get(url__regex=r".*/chart/.*").mock(return_value=Response(500))  # tum metaller 0
            prices = await fetch_metal_prices()
        assert prices["gold"] == Decimal("0")
        assert prices["silver"] == Decimal("0")
        # cache TTL kisaltilmis olmali (now - TTL + 30) → cache yaslandirilmis
        assert svc._price_cache is not None
        cached_ts = svc._price_cache[0]
        assert cached_ts < time.monotonic() - 200  # 5dk-30sn geriye cekilmis

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_second_call(self):
        with respx.mock(assert_all_called=False) as rsx:
            tcmb = rsx.get(TCMB_URL).mock(return_value=Response(200, content=self._TCMB))
            rsx.get(url__regex=r".*/chart/XAU=X.*").mock(return_value=Response(200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 3000.0}}]}}))
            rsx.get(url__regex=r".*/chart/XAG=X.*").mock(return_value=Response(200, json={"chart": {"result": [{"meta": {"regularMarketPrice": 35.0}}]}}))
            await fetch_metal_prices()
            await fetch_metal_prices()
        assert tcmb.call_count == 1

    @pytest.mark.asyncio
    async def test_tcmb_failure_raises(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(503))
            with pytest.raises(Exception):
                await fetch_metal_prices()


# ─── calculate_holding_value validation ───────────────────────────────────────
class TestCalculateHoldingValue:
    G = Decimal("1000")
    S = Decimal("50")

    def test_gram(self):
        v = calculate_holding_value(_holding(unit_type="gram", quantity=Decimal("10")), self.G, self.S)
        assert v["gram_equivalent"] == Decimal("10.0000")
        assert v["total_value_tl"] == Decimal("10000.00")

    def test_biga_valid(self):
        v = calculate_holding_value(_holding(unit_type="biga", biga_code="A02", quantity=Decimal("2")), self.G, self.S)
        # A02 = 5 gram, 2 adet = 10 gram * 1000 = 10000
        assert v["total_value_tl"] == Decimal("10000.00")

    def test_biga_invalid_raises(self):
        with pytest.raises(ValueError, match="BiGA"):
            calculate_holding_value(_holding(unit_type="biga", biga_code="ZZZ"), self.G, self.S)

    def test_biga_none_code_raises(self):
        with pytest.raises(ValueError):
            calculate_holding_value(_holding(unit_type="biga", biga_code=None), self.G, self.S)

    def test_coin_valid(self):
        v = calculate_holding_value(_holding(unit_type="coin", coin_type="tam", quantity=Decimal("1")), self.G, self.S)
        # tam = 7.0166 gram * 1000 (altın)
        assert v["total_value_tl"] == Decimal("7016.60")

    def test_coin_invalid_raises(self):
        with pytest.raises(ValueError, match="sikke"):
            calculate_holding_value(_holding(unit_type="coin", coin_type="altin"), self.G, self.S)

    def test_invalid_unit_type_raises(self):
        with pytest.raises(ValueError, match="unit_type"):
            calculate_holding_value(_holding(unit_type="bogus"), self.G, self.S)

    def test_silver_gram_uses_silver_price(self):
        v = calculate_holding_value(_holding(unit_type="gram", metal="silver", quantity=Decimal("100")), self.G, self.S)
        assert v["total_value_tl"] == Decimal("5000.00")
