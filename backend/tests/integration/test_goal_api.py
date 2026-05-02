"""Finansal hedef GET/PUT endpoint testleri."""
import pytest
from httpx import AsyncClient

from tests.conftest import verify_user_email


async def _make_user(client: AsyncClient, email: str) -> dict:
    pwd = "guclu-sifre-123"
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_get_goal_empty(client: AsyncClient):
    headers = await _make_user(client, "goal_empty@example.com")
    resp = await client.get("/api/v1/user/goal", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["monthly_expense_goal"] is None
    assert data["freedom_target"] is None
    assert data["progress_pct"] is None


@pytest.mark.asyncio
async def test_set_goal(client: AsyncClient):
    headers = await _make_user(client, "goal_set@example.com")
    resp = await client.put(
        "/api/v1/user/goal",
        json={"monthly_expense_goal": 50000},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["monthly_expense_goal"]) == 50000.0
    assert float(data["freedom_target"]) == 15_000_000.0
    assert data["progress_pct"] is None  # snapshot yok henüz


@pytest.mark.asyncio
async def test_set_goal_invalid(client: AsyncClient):
    headers = await _make_user(client, "goal_inv@example.com")
    resp = await client.put(
        "/api/v1/user/goal",
        json={"monthly_expense_goal": -100},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_goal_after_set(client: AsyncClient):
    headers = await _make_user(client, "goal_get@example.com")
    await client.put("/api/v1/user/goal", json={"monthly_expense_goal": 30000}, headers=headers)
    resp = await client.get("/api/v1/user/goal", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["monthly_expense_goal"]) == 30000.0
    assert float(data["freedom_target"]) == 9_000_000.0


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/user/goal")
    assert resp.status_code == 401
