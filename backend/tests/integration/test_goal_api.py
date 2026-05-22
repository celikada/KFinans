"""Finansal hedef GET/PUT endpoint testleri."""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


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
