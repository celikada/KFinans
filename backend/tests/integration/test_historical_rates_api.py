"""Tarihsel TCMB kuru servisi — DB + TCMB-mock entegrasyon testleri.

DB cache hit, forward-fill (DB), 7-gün tatil sınırı, upsert idempotency,
bulk distinct-date eşleme, cron job upsert (mock).
"""

from datetime import date
from decimal import Decimal

import pytest
import respx
from httpx import Response
from sqlalchemy import select

from app.models.daily_rate import DailyRate
from app.services.historical_rates import (
    backfill_dates,
    ensure_date_cached,
    get_historical_rate,
    get_historical_rates_bulk,
)
from tests.conftest import TestSession


def _tcmb_xml(usd: str = "40.000000", jpy: str = "27.000000") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date>
  <Currency CurrencyCode="USD"><Unit>1</Unit><ForexBuying>{usd}</ForexBuying></Currency>
  <Currency CurrencyCode="EUR"><Unit>1</Unit><ForexBuying>43.500000</ForexBuying></Currency>
  <Currency CurrencyCode="JPY"><Unit>100</Unit><ForexBuying>{jpy}</ForexBuying></Currency>
</Tarih_Date>""".encode()


def _hist_url(d: date) -> str:
    return f"https://www.tcmb.gov.tr/kurlar/{d:%Y%m}/{d:%d%m%Y}.xml"


async def _seed(d: date, currency: str, rate: str) -> None:
    async with TestSession() as s:
        s.add(DailyRate(rate_date=d, currency=currency, rate_to_try=Decimal(rate)))
        await s.commit()


# ── DB cache hit ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_db_cache_hit_no_http():
    await _seed(date(2026, 1, 9), "USD", "41.123456")
    async with TestSession() as s:
        # respx hicbir route mock'lamadi; HTTP yapilirsa patlar → cache hit ispati
        with respx.mock(assert_all_called=False):
            rate = await get_historical_rate(s, "USD", date(2026, 1, 9))
    assert rate == Decimal("41.123456")


@pytest.mark.asyncio
async def test_forward_fill_db_weekend():
    # Cuma kuru DB'de; Cumartesi sorulunca Cuma kuru (DB forward-fill)
    await _seed(date(2026, 1, 9), "USD", "40.500000")
    async with TestSession() as s:
        with respx.mock(assert_all_called=False):
            rate = await get_historical_rate(s, "USD", date(2026, 1, 10))  # cmt
    assert rate == Decimal("40.500000")


# ── TCMB fetch + upsert (DB miss) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_db_miss_fetches_and_upserts():
    target = date(2026, 2, 5)
    async with TestSession() as s, respx.mock(assert_all_called=False) as mock:
        mock.get(_hist_url(target)).mock(return_value=Response(200, content=_tcmb_xml()))
        rate = await get_historical_rate(s, "USD", target)
    assert rate == Decimal("40.000000")

    # upsert kontrol — TRY saklanmaz, JPY normalize edilir
    async with TestSession() as s:
        rows = (await s.execute(select(DailyRate).where(DailyRate.rate_date == target))).scalars().all()
        codes = {r.currency: r.rate_to_try for r in rows}
    assert "TRY" not in codes
    assert codes["USD"] == Decimal("40.000000")
    assert codes["JPY"] == Decimal("0.270000")  # 27/100


@pytest.mark.asyncio
async def test_holiday_lookback_finds_previous_business_day():
    # Hedef gun 404 (tatil); -1 gun de 404; -2 gun yayin gunu
    target = date(2026, 4, 23)  # 23 Nisan resmi tatil
    async with TestSession() as s, respx.mock(assert_all_called=False) as mock:
        mock.get(_hist_url(date(2026, 4, 23))).mock(return_value=Response(404))
        mock.get(_hist_url(date(2026, 4, 22))).mock(return_value=Response(404))
        mock.get(_hist_url(date(2026, 4, 21))).mock(return_value=Response(200, content=_tcmb_xml(usd="39.900000")))
        rate = await get_historical_rate(s, "USD", target)
    assert rate == Decimal("39.900000")


@pytest.mark.asyncio
async def test_seven_day_limit_returns_none():
    target = date(2026, 5, 20)
    async with TestSession() as s, respx.mock(assert_all_called=False) as mock:
        # ≤7 gun geriye hepsi 404
        mock.get(url__regex=r"https://www\.tcmb\.gov\.tr/kurlar/.*\.xml").mock(return_value=Response(404))
        rate = await get_historical_rate(s, "USD", target)
    assert rate is None


@pytest.mark.asyncio
async def test_upsert_idempotent_updates_rate():
    target = date(2026, 6, 1)
    async with TestSession() as s, respx.mock(assert_all_called=False) as mock:
        mock.get(_hist_url(target)).mock(return_value=Response(200, content=_tcmb_xml(usd="40.000000")))
        await ensure_date_cached(s, target)
    # ensure_date_cached ikinci kez DB'de varsa HTTP yapmaz (idempotent)
    async with TestSession() as s, respx.mock(assert_all_called=False):
        await ensure_date_cached(s, target)
    async with TestSession() as s:
        rows = (await s.execute(select(DailyRate).where(DailyRate.rate_date == target, DailyRate.currency == "USD"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].rate_to_try == Decimal("40.000000")


# ── Bulk ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_try_returns_one_each():
    dates = {date(2026, 1, 1), date(2026, 1, 2)}
    async with TestSession() as s:
        out = await get_historical_rates_bulk(s, "TRY", dates)
    assert out == {d: Decimal(1) for d in dates}


@pytest.mark.asyncio
async def test_bulk_distinct_date_mapping_with_forward_fill():
    # Yayin gunu: 2026-03-06 (Cuma); hedefler Cuma + Cumartesi + Pazar
    await _seed(date(2026, 3, 6), "USD", "42.000000")
    dates = {date(2026, 3, 6), date(2026, 3, 7), date(2026, 3, 8)}
    async with TestSession() as s, respx.mock(assert_all_called=False) as mock:
        # hafta sonu hedefleri 404 (yayin yok) → forward-fill Cuma kuru
        mock.get(url__regex=r"https://www\.tcmb\.gov\.tr/kurlar/.*\.xml").mock(return_value=Response(404))
        out = await get_historical_rates_bulk(s, "USD", dates)
    assert out[date(2026, 3, 6)] == Decimal("42.000000")
    assert out[date(2026, 3, 7)] == Decimal("42.000000")
    assert out[date(2026, 3, 8)] == Decimal("42.000000")


@pytest.mark.asyncio
async def test_bulk_empty_dates():
    async with TestSession() as s:
        assert await get_historical_rates_bulk(s, "USD", set()) == {}


# ── backfill ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backfill_caches_business_days():
    d1, d2 = date(2026, 7, 6), date(2026, 7, 7)
    async with TestSession() as s, respx.mock(assert_all_called=False) as mock:
        mock.get(_hist_url(d1)).mock(return_value=Response(200, content=_tcmb_xml()))
        mock.get(_hist_url(d2)).mock(return_value=Response(404))  # tatil
        count = await backfill_dates(s, {d1, d2})
    assert count == 1  # yalniz d1 cekildi
    async with TestSession() as s:
        rows = (await s.execute(select(DailyRate).where(DailyRate.rate_date == d1))).scalars().all()
    assert any(r.currency == "USD" for r in rows)


# ── Cron job ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cron_job_upserts_today(monkeypatch):
    from app import scheduler

    fixed = date(2026, 8, 3)

    class _FakeDT:
        @staticmethod
        def now(tz=None):
            import datetime as _d

            return _d.datetime(2026, 8, 3, 16, 0, tzinfo=tz)

    monkeypatch.setattr(scheduler, "datetime", _FakeDT)

    async with respx.mock(assert_all_called=False) as mock:
        mock.get(_hist_url(fixed)).mock(return_value=Response(200, content=_tcmb_xml(usd="45.000000")))
        await scheduler._fetch_daily_rate_job(session_factory=TestSession)

    async with TestSession() as s:
        rows = (await s.execute(select(DailyRate).where(DailyRate.rate_date == fixed, DailyRate.currency == "USD"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].rate_to_try == Decimal("45.000000")
