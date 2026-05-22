"""TEST-011 (FAZ H): TEFAS holding endpoint testleri.

PUT replace-all + distributor + avg_cost_tl validation + auth. preview ve
import-mkk endpoint'leri network/file bagimli oldugu icin kapsam disi.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


@pytest.mark.asyncio
async def test_get_holdings_empty(client: AsyncClient):
    headers = await make_user(client, "tefas_empty@example.com")
    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_holdings_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/tefas/holdings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_holdings_replace_all(client: AsyncClient):
    """PUT replace-all: eski kayitlar silinir, yeni kayitlar yazilir."""
    headers = await make_user(client, "tefas_put@example.com")

    first = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "AFA", "quantity": 100, "name": "Ak Portföy"},
            {"code": "ZJI", "quantity": 50, "name": "Ziraat Portföy"},
        ],
        headers=headers,
    )
    assert first.status_code == 200
    assert len(first.json()) == 2

    second = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "FYD", "quantity": 200, "name": "Finans Yatırım"},
        ],
        headers=headers,
    )
    assert second.status_code == 200
    assert len(second.json()) == 1
    assert second.json()[0]["code"] == "FYD"


@pytest.mark.asyncio
async def test_put_holdings_with_avg_cost(client: AsyncClient):
    headers = await make_user(client, "tefas_cost@example.com")
    resp = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "AFA", "quantity": 100, "name": "Ak Portföy", "avg_cost_tl": 1.2345},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    h = resp.json()[0]
    assert float(h["avg_cost_tl"]) == 1.2345


@pytest.mark.asyncio
async def test_put_holdings_avg_cost_zero_normalized_to_none(client: AsyncClient):
    """avg_cost_tl <= 0 -> None (cost basis bilinmiyor)."""
    headers = await make_user(client, "tefas_zerocost@example.com")
    resp = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "AFA", "quantity": 100, "name": "Ak Portföy", "avg_cost_tl": 0},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["avg_cost_tl"] is None


@pytest.mark.asyncio
async def test_put_holdings_with_distributor(client: AsyncClient):
    """ZJI fonu hem Foneria hem Ziraat'tan ayri satir."""
    headers = await make_user(client, "tefas_dist@example.com")
    resp = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "ZJI", "quantity": 50, "name": "Ziraat", "distributor": "Foneria"},
            {"code": "ZJI", "quantity": 30, "name": "Ziraat", "distributor": "Ziraat Yatırım"},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 2


@pytest.mark.asyncio
async def test_export_holdings_returns_xlsx(client: AsyncClient):
    headers = await make_user(client, "tefas_export@example.com")
    resp = await client.get("/api/v1/portfolio/tefas/export", headers=headers)
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_holdings_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/tefas/export")
    assert resp.status_code == 401
