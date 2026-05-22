"""
Doviz kuru fetch fonksiyonlari — TCMB primary, exchangerate-api fallback.

respx ile dis HTTP cagrilari mock'lanir; gercek aga gidilmez.
Cache'in testler arasi sizmasini onlemek icin her test once cache'i temizler.
"""

from decimal import Decimal

import pytest
import respx
from httpx import Response

from app.services import aggregator
from app.services.aggregator import (
    EXCHANGERATE_API_GBP,
    EXCHANGERATE_API_USD,
    TCMB_URL,
    fetch_gbp_to_usd,
    fetch_usd_to_tl,
)

_TCMB_XML_FULL = """<?xml version="1.0" encoding="utf-8"?>
<Tarih_Date Tarih="01.05.2026" Date="05/01/2026">
  <Currency CrossOrder="0" Kod="USD" CurrencyCode="USD">
    <Unit>1</Unit>
    <ForexBuying>30.5012</ForexBuying>
    <ForexSelling>30.5623</ForexSelling>
  </Currency>
  <Currency CrossOrder="6" Kod="GBP" CurrencyCode="GBP">
    <Unit>1</Unit>
    <ForexBuying>38.2105</ForexBuying>
    <ForexSelling>38.2987</ForexSelling>
  </Currency>
  <Currency CrossOrder="9" Kod="JPY" CurrencyCode="JPY">
    <Unit>100</Unit>
    <ForexBuying>20.4500</ForexBuying>
    <ForexSelling>20.5000</ForexSelling>
  </Currency>
</Tarih_Date>"""


_TCMB_XML_NO_USD = """<?xml version="1.0" encoding="utf-8"?>
<Tarih_Date Tarih="01.05.2026" Date="05/01/2026">
  <Currency CrossOrder="3" Kod="EUR" CurrencyCode="EUR">
    <Unit>1</Unit>
    <ForexBuying>32.0000</ForexBuying>
  </Currency>
</Tarih_Date>"""


@pytest.fixture(autouse=True)
def _clear_tcmb_cache():
    """Her testten once TCMB in-memory cache'ini temizle."""
    aggregator._tcmb_cache = None
    yield
    aggregator._tcmb_cache = None


# ─── fetch_usd_to_tl ──────────────────────────────────────────────────────────


class TestFetchUsdToTl:
    @pytest.mark.asyncio
    async def test_uses_tcmb_when_available(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_XML_FULL))
            rate = await fetch_usd_to_tl()
        assert rate == Decimal("30.5012")

    @pytest.mark.asyncio
    async def test_falls_back_to_exchangerate_api_when_tcmb_fails(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(503))
            rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(200, json={"rates": {"TRY": "31.25"}}))
            rate = await fetch_usd_to_tl()
        assert rate == Decimal("31.25")

    @pytest.mark.asyncio
    async def test_falls_back_when_tcmb_xml_missing_usd(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_XML_NO_USD))
            rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(200, json={"rates": {"TRY": "32.10"}}))
            rate = await fetch_usd_to_tl()
        assert rate == Decimal("32.10")

    @pytest.mark.asyncio
    async def test_raises_when_both_sources_fail(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(503))
            rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(500))
            with pytest.raises(RuntimeError, match="USD/TRY"):
                await fetch_usd_to_tl()


# ─── fetch_gbp_to_usd ─────────────────────────────────────────────────────────


class TestFetchGbpToUsd:
    @pytest.mark.asyncio
    async def test_derives_from_tcmb_gbp_and_usd(self):
        # 38.2105 / 30.5012 = 1.252754... → quantize 6 hane
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_XML_FULL))
            rate = await fetch_gbp_to_usd()
        assert rate == (Decimal("38.2105") / Decimal("30.5012")).quantize(Decimal("0.000001"))

    @pytest.mark.asyncio
    async def test_falls_back_when_tcmb_lacks_gbp(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_XML_NO_USD))
            rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(200, json={"rates": {"USD": "1.27"}}))
            rate = await fetch_gbp_to_usd()
        assert rate == Decimal("1.27")

    @pytest.mark.asyncio
    async def test_raises_when_both_sources_fail(self):
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(503))
            rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(500))
            with pytest.raises(RuntimeError, match="GBP/USD"):
                await fetch_gbp_to_usd()


# ─── TCMB cache ───────────────────────────────────────────────────────────────


class TestTcmbCache:
    @pytest.mark.asyncio
    async def test_cache_avoids_second_http_call(self):
        with respx.mock(assert_all_called=False) as rsx:
            route = rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_XML_FULL))
            await fetch_usd_to_tl()
            await fetch_gbp_to_usd()
        # Iki kuru pespese cektik; TCMB sadece bir kez cagirilmali
        assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_clears_when_tcmb_returns_unparseable(self):
        # Bozuk XML — parse hatasi; cache'e yazilmamali
        with respx.mock(assert_all_called=False) as rsx:
            rsx.get(TCMB_URL).mock(return_value=Response(200, content=b"<not><valid"))
            rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(200, json={"rates": {"TRY": "33.00"}}))
            rate = await fetch_usd_to_tl()
        assert rate == Decimal("33.00")
        assert aggregator._tcmb_cache is None
