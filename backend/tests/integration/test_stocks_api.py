"""TEST-011 (FAZ H): Stocks endpoint testleri.

Holding CRUD + replace-all PUT semantik + auth + validation. MKK Excel
import disardan dosya gerektirdigi icin (xlrd 1.2.0) bu test dosyasinda
kapsam disi; respx mock'siz gercek Yahoo cagrisi yapan preview endpoint'i
de network bagli oldugu icin lite tutuluyor.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


@pytest.mark.asyncio
async def test_get_holdings_empty(client: AsyncClient):
    headers = await make_user(client, "stock_empty@example.com")
    resp = await client.get("/api/v1/portfolio/stocks/holdings", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_holdings_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/stocks/holdings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_holdings_replace_all(client: AsyncClient):
    """PUT replace-all: eski kayitlar silinir, yeni kayitlar yazilir."""
    headers = await make_user(client, "stock_put@example.com")

    # Ilk kayit
    first = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "AAPL", "quantity": 10, "name": "Apple Inc."},
            {"ticker": "GOOGL", "quantity": 5, "name": "Alphabet"},
        ],
        headers=headers,
    )
    assert first.status_code == 200
    assert len(first.json()) == 2

    # Ikinci kayit AAPL'i siler, MSFT ekler
    second = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "MSFT", "quantity": 8, "name": "Microsoft"},
        ],
        headers=headers,
    )
    assert second.status_code == 200
    assert len(second.json()) == 1
    assert second.json()[0]["ticker"] == "MSFT"


@pytest.mark.asyncio
async def test_put_holdings_with_avg_cost(client: AsyncClient):
    """avg_cost_tl alani opsiyonel; pozitif deger korunur."""
    headers = await make_user(client, "stock_cost@example.com")
    resp = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "AAPL", "quantity": 10, "name": "Apple", "avg_cost_tl": 5500.50},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    h = resp.json()[0]
    assert float(h["avg_cost_tl"]) == 5500.50


@pytest.mark.asyncio
async def test_put_holdings_avg_cost_zero_normalized_to_none(client: AsyncClient):
    """Schema validator: avg_cost_tl <= 0 ise None'a normalize edilir
    (kullanici bilmiyorsa bos birakabilir)."""
    headers = await make_user(client, "stock_zerocost@example.com")
    resp = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "AAPL", "quantity": 10, "name": "Apple", "avg_cost_tl": 0},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    h = resp.json()[0]
    assert h["avg_cost_tl"] is None


@pytest.mark.asyncio
async def test_put_holdings_with_distributor(client: AsyncClient):
    """distributor (aracikurum) alani — ayni ticker farklikurumda ayri kayit."""
    headers = await make_user(client, "stock_dist@example.com")
    resp = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "AAPL", "quantity": 10, "name": "Apple", "distributor": "Is Yatirim"},
            {
                "ticker": "AAPL",
                "quantity": 5,
                "name": "Apple",
                "distributor": "Garanti BBVA Yatirim",
            },
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 2
    distributors = {h["distributor"] for h in holdings}
    assert distributors == {"Is Yatirim", "Garanti BBVA Yatirim"}


@pytest.mark.asyncio
async def test_export_holdings_empty_returns_xlsx(client: AsyncClient):
    """Export bos kayitla bile xlsx dondurmeli (header satirlari)."""
    headers = await make_user(client, "stock_export@example.com")
    resp = await client.get("/api/v1/portfolio/stocks/export", headers=headers)
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_holdings_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/stocks/export")
    assert resp.status_code == 401
