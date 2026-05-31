"""Finansal hedef GET/PUT endpoint testleri."""

from datetime import date
from decimal import Decimal

import pytest
import respx
from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from tests.conftest import TestSession, make_user


def _mock_tcmb_usd_only(usd_to_tl: float = 40.0):
    """TCMB XML — sadece USD (EUR/GBP eksik -> _rate_to_tl 503 dalı)."""
    xml = f"""<?xml version="1.0" encoding="ISO-8859-9"?>
<Tarih_Date Tarih="07.05.2026">
  <Currency CrossOrder="0" Kod="USD" CurrencyCode="USD">
    <Unit>1</Unit><Isim>ABD DOLARI</Isim><CurrencyName>US DOLLAR</CurrencyName>
    <ForexBuying>{usd_to_tl}</ForexBuying><ForexSelling>{usd_to_tl + 0.01}</ForexSelling>
  </Currency>
</Tarih_Date>"""
    respx.get("https://www.tcmb.gov.tr/kurlar/today.xml").mock(return_value=Response(200, content=xml, headers={"Content-Type": "application/xml"}))


async def _get_user_id(email: str):
    async with TestSession() as db:
        u = (await db.execute(select(User).where(User.email == email))).scalar_one()
        return u.id


async def _add_snapshot(user_id, total_tl: str, snap_date: date = date(2026, 5, 1)):
    async with TestSession() as db:
        db.add(
            PortfolioSnapshot(
                user_id=user_id,
                snapshot_date=snap_date,
                total_value_tl=Decimal(total_tl),
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_get_goal_empty(client: AsyncClient):
    headers = await make_user(client, "goal_empty@example.com")
    resp = await client.get("/api/v1/user/goal", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal_amount"] is None
    assert data["freedom_target_tl"] is None
    assert data["progress_pct"] is None
    assert data["goal_currency"] == "TRY"


@pytest.mark.asyncio
async def test_set_goal_try(client: AsyncClient):
    headers = await make_user(client, "goal_try@example.com")
    resp = await client.put(
        "/api/v1/user/goal",
        json={"amount": 50000, "currency": "TRY"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["goal_amount"]) == 50000.0
    assert data["goal_currency"] == "TRY"
    assert float(data["rate_to_tl"]) == 1.0
    assert float(data["monthly_tl"]) == 50000.0
    assert float(data["freedom_target_tl"]) == 15_000_000.0
    assert data["progress_pct"] is None  # snapshot yok


@pytest.mark.asyncio
async def test_set_goal_usd(client: AsyncClient):
    headers = await make_user(client, "goal_usd@example.com")
    resp = await client.put(
        "/api/v1/user/goal",
        json={"amount": 3000, "currency": "USD"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["goal_amount"]) == 3000.0
    assert data["goal_currency"] == "USD"
    # Kur TRY ise 1, USD ise TCMB'den gelir (test ortamında gerçek API çağrısı)
    assert float(data["rate_to_tl"]) > 1.0
    assert float(data["monthly_tl"]) > 50000.0  # USD > 1 TL
    assert float(data["freedom_target_tl"]) == float(data["monthly_tl"]) * 300


@pytest.mark.asyncio
async def test_set_goal_eur(client: AsyncClient):
    headers = await make_user(client, "goal_eur@example.com")
    resp = await client.put(
        "/api/v1/user/goal",
        json={"amount": 2000, "currency": "EUR"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal_currency"] == "EUR"
    assert float(data["rate_to_tl"]) > 1.0


@pytest.mark.asyncio
async def test_set_goal_invalid_currency(client: AsyncClient):
    headers = await make_user(client, "goal_badcur@example.com")
    resp = await client.put(
        "/api/v1/user/goal",
        json={"amount": 1000, "currency": "JPY"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_set_goal_invalid_amount(client: AsyncClient):
    headers = await make_user(client, "goal_badamt@example.com")
    resp = await client.put(
        "/api/v1/user/goal",
        json={"amount": -100, "currency": "USD"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_goal_after_set(client: AsyncClient):
    headers = await make_user(client, "goal_get@example.com")
    await client.put("/api/v1/user/goal", json={"amount": 3000, "currency": "USD"}, headers=headers)
    resp = await client.get("/api/v1/user/goal", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["goal_amount"]) == 3000.0
    assert data["goal_currency"] == "USD"
    assert data["freedom_target_tl"] is not None


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/user/goal")
    assert resp.status_code == 401


# ─── Snapshot var + hedef yok (passive income hesabı — satır 61-69) ─────────


@pytest.mark.asyncio
async def test_get_goal_with_snapshot_no_goal_returns_passive_income(client: AsyncClient):
    """goal_amount yok ama snapshot var -> portfolio_value + passive_income_tl dolu.

    passive_income_tl = portfolio / 300; diger hedef alanlari None.
    """
    email = "goal_snap_nogoal@example.com"
    headers = await make_user(client, email)
    user_id = await _get_user_id(email)
    await _add_snapshot(user_id, "3000000.00")

    resp = await client.get("/api/v1/user/goal", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal_amount"] is None
    assert Decimal(data["portfolio_value"]) == Decimal("3000000.00")
    # passive = 3.000.000 / 300 = 10.000
    assert Decimal(data["passive_income_tl"]) == Decimal("10000")
    assert data["freedom_target_tl"] is None
    assert data["progress_pct"] is None


@pytest.mark.asyncio
async def test_get_goal_uses_latest_snapshot(client: AsyncClient):
    """Birden fazla snapshot varsa en yeni (snapshot_date) kullanılır."""
    email = "goal_latest_snap@example.com"
    headers = await make_user(client, email)
    user_id = await _get_user_id(email)
    await _add_snapshot(user_id, "1000000.00", date(2026, 1, 1))
    await _add_snapshot(user_id, "6000000.00", date(2026, 6, 1))  # en yeni

    resp = await client.get("/api/v1/user/goal", headers=headers)
    data = resp.json()
    assert Decimal(data["portfolio_value"]) == Decimal("6000000.00")
    assert Decimal(data["passive_income_tl"]) == Decimal("20000")  # 6.000.000 / 300


# ─── Hedef + snapshot (progress_pct, months_covered, passive_foreign) ───────


@pytest.mark.asyncio
async def test_get_goal_with_goal_and_snapshot_full_metrics(client: AsyncClient):
    """TRY hedef + snapshot -> progress_pct + months_covered + passive hesabı dolu."""
    email = "goal_full@example.com"
    headers = await make_user(client, email)
    user_id = await _get_user_id(email)

    # 10.000 TL/ay hedef -> freedom_target = 3.000.000
    await client.put("/api/v1/user/goal", json={"amount": 10000, "currency": "TRY"}, headers=headers)
    await _add_snapshot(user_id, "1500000.00")

    resp = await client.get("/api/v1/user/goal", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["monthly_tl"]) == Decimal("10000.00")
    assert Decimal(data["freedom_target_tl"]) == Decimal("3000000.00")
    assert Decimal(data["portfolio_value"]) == Decimal("1500000.00")
    # progress = 1.500.000 / 3.000.000 × 100 = 50
    assert data["progress_pct"] == 50.0
    # months_covered = 1.500.000 / 10.000 = 150
    assert data["months_covered"] == 150.0
    # passive_tl = 1.500.000 / 300 = 5000; passive_foreign (TRY, rate 1) = 5000
    assert Decimal(data["passive_income_tl"]) == Decimal("5000.00")
    assert Decimal(data["passive_income_foreign"]) == Decimal("5000.00")


# ─── _rate_to_tl 503 dalı (satır 28) ────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_set_goal_rate_unavailable_returns_503(client: AsyncClient):
    """TCMB yanıtında EUR kuru yoksa -> 503 (rate alınamadı)."""
    _mock_tcmb_usd_only(usd_to_tl=40.0)
    headers = await make_user(client, "goal_503@example.com")
    # PUT EUR -> set_goal commit eder sonra get_goal -> _rate_to_tl(EUR) -> 503
    resp = await client.put(
        "/api/v1/user/goal",
        json={"amount": 2000, "currency": "EUR"},
        headers=headers,
    )
    assert resp.status_code == 503
    assert "EUR" in resp.json()["detail"]


@pytest.mark.asyncio
@respx.mock
async def test_get_goal_rate_unavailable_returns_503(client: AsyncClient):
    """Hedef EUR olarak kayıtlı ama TCMB EUR vermiyor -> GET 503."""
    email = "goal_get_503@example.com"
    headers = await make_user(client, email)
    user_id = await _get_user_id(email)
    # Hedefi DB'de dogrudan EUR yap (set_goal mock'suz gercek kur cekemez)
    async with TestSession() as db:
        u = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        u.goal_amount = Decimal("2000")
        u.goal_currency = "EUR"
        await db.commit()

    _mock_tcmb_usd_only(usd_to_tl=40.0)
    resp = await client.get("/api/v1/user/goal", headers=headers)
    assert resp.status_code == 503
