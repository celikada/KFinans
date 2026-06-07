"""Tarihsel TCMB kuru servisi — DB gerektirmeyen birim testleri.

DB-backed (cache hit, upsert, bulk, cron) testleri
`tests/integration/test_historical_rates_api.py` içinde.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.aggregator import parse_tcmb_xml
from app.services.historical_rates import (
    _forward_fill_dates,
    _historical_url,
    get_historical_rate,
)

# ── TCMB XML örneği (USD + JPY 100-unit + EUR) ──────────────────────────────
_TCMB_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date>
  <Currency CurrencyCode="USD">
    <Unit>1</Unit>
    <ForexBuying>40.000000</ForexBuying>
  </Currency>
  <Currency CurrencyCode="EUR">
    <Unit>1</Unit>
    <ForexBuying>43.500000</ForexBuying>
  </Currency>
  <Currency CurrencyCode="JPY">
    <Unit>100</Unit>
    <ForexBuying>27.000000</ForexBuying>
  </Currency>
</Tarih_Date>
"""


class TestTryShortCircuit:
    @pytest.mark.asyncio
    async def test_try_returns_one_without_db(self):
        # db=None: TRY DB sorgusu yapmamali, exception atmamali
        result = await get_historical_rate(None, "TRY", date(2026, 1, 15))
        assert result == Decimal(1)

    @pytest.mark.asyncio
    async def test_try_lowercase_normalized(self):
        result = await get_historical_rate(None, "try", date(2026, 1, 15))
        assert result == Decimal(1)


class TestParseJpyUnitNormalize:
    def test_jpy_per_unit_normalized(self):
        rates = parse_tcmb_xml(_TCMB_XML)
        # 27.0 / 100 = 0.27 per 1 JPY
        assert rates["JPY"] == Decimal("0.270000")

    def test_usd_eur_unit_one(self):
        rates = parse_tcmb_xml(_TCMB_XML)
        assert rates["USD"] == Decimal("40.000000")
        assert rates["EUR"] == Decimal("43.500000")


class TestHistoricalUrl:
    def test_url_format(self):
        url = _historical_url(date(2026, 3, 7))
        assert url == "https://www.tcmb.gov.tr/kurlar/202603/07032026.xml"

    def test_url_fixed_host(self):
        # SSRF: host her zaman sabit tcmb.gov.tr
        assert _historical_url(date(2026, 12, 31)).startswith("https://www.tcmb.gov.tr/kurlar/")


class TestForwardFillHelper:
    def test_weekend_uses_previous_business_day(self):
        # Cuma 2026-01-09 yayin gunu; Cumartesi/Pazar icin Cuma kuru
        published = [(date(2026, 1, 9), Decimal("40.0"))]
        targets = {date(2026, 1, 10), date(2026, 1, 11)}  # cmt + pazar
        out = _forward_fill_dates(published, targets)
        assert out[date(2026, 1, 10)] == Decimal("40.0")
        assert out[date(2026, 1, 11)] == Decimal("40.0")

    def test_picks_latest_on_or_before(self):
        published = [
            (date(2026, 1, 5), Decimal("39.0")),
            (date(2026, 1, 9), Decimal("40.0")),
        ]
        out = _forward_fill_dates(published, {date(2026, 1, 7), date(2026, 1, 12)})
        assert out[date(2026, 1, 7)] == Decimal("39.0")  # 5'i kullanir
        assert out[date(2026, 1, 12)] == Decimal("40.0")  # 9'u kullanir

    def test_target_before_all_published_unmapped(self):
        published = [(date(2026, 1, 9), Decimal("40.0"))]
        out = _forward_fill_dates(published, {date(2026, 1, 1)})
        assert date(2026, 1, 1) not in out

    def test_empty_published_returns_empty(self):
        out = _forward_fill_dates([], {date(2026, 1, 1)})
        assert out == {}
