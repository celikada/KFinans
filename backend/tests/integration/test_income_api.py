"""Income CRUD + summary endpoint testleri."""
import pytest
from httpx import AsyncClient

from tests.conftest import make_user, verify_user_email



def _inc(amount: float, category: str, date: str, description: str | None = None) -> dict:
    return {"amount": amount, "category": category, "date": date, "description": description}


@pytest.mark.asyncio
async def test_empty_list(client: AsyncClient):
    headers = await make_user(client, "inc_empty@example.com")
    resp = await client.get("/api/v1/income", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_income(client: AsyncClient):
    headers = await make_user(client, "inc_create@example.com")
    resp = await client.post(
        "/api/v1/income",
        json=_inc(50000, "salary", "2026-05-01", "Mayıs maaşı"),
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert float(data["amount"]) == 50000.0
    assert data["category"] == "salary"
    assert data["date"] == "2026-05-01"
    assert data["description"] == "Mayıs maaşı"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_invalid_category(client: AsyncClient):
    headers = await make_user(client, "inc_badcat@example.com")
    resp = await client.post("/api/v1/income", json=_inc(1000, "crypto", "2026-05-01"), headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_negative_amount(client: AsyncClient):
    headers = await make_user(client, "inc_neg@example.com")
    resp = await client.post("/api/v1/income", json=_inc(-500, "salary", "2026-05-01"), headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_filter_by_month(client: AsyncClient):
    headers = await make_user(client, "inc_filter@example.com")
    await client.post("/api/v1/income", json=_inc(50000, "salary", "2026-05-01"), headers=headers)
    await client.post("/api/v1/income", json=_inc(10000, "bonus", "2026-04-15"), headers=headers)

    resp = await client.get("/api/v1/income?year=2026&month=5", headers=headers)
    data = resp.json()
    assert len(data) == 1
    assert data[0]["category"] == "salary"


@pytest.mark.asyncio
async def test_update_income(client: AsyncClient):
    headers = await make_user(client, "inc_update@example.com")
    create = await client.post("/api/v1/income", json=_inc(50000, "salary", "2026-05-01"), headers=headers)
    inc_id = create.json()["id"]

    resp = await client.put(f"/api/v1/income/{inc_id}", json={"amount": 55000.0}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 55000.0


@pytest.mark.asyncio
async def test_delete_income(client: AsyncClient):
    headers = await make_user(client, "inc_delete@example.com")
    create = await client.post("/api/v1/income", json=_inc(50000, "salary", "2026-05-01"), headers=headers)
    inc_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/income/{inc_id}", headers=headers)
    assert resp.status_code == 204

    list_resp = await client.get("/api/v1/income", headers=headers)
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_idor_update(client: AsyncClient):
    h1 = await make_user(client, "inc_idor1@example.com")
    h2 = await make_user(client, "inc_idor2@example.com")
    create = await client.post("/api/v1/income", json=_inc(50000, "salary", "2026-05-01"), headers=h1)
    inc_id = create.json()["id"]

    resp = await client.put(f"/api/v1/income/{inc_id}", json={"amount": 1.0}, headers=h2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_idor_delete(client: AsyncClient):
    h1 = await make_user(client, "inc_idor3@example.com")
    h2 = await make_user(client, "inc_idor4@example.com")
    create = await client.post("/api/v1/income", json=_inc(50000, "salary", "2026-05-01"), headers=h1)
    inc_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/income/{inc_id}", headers=h2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/income")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_summary_empty(client: AsyncClient):
    headers = await make_user(client, "inc_sum_empty@example.com")
    resp = await client.get("/api/v1/income/summary?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total"]) == 0.0
    assert data["count"] == 0
    assert data["by_category"] == []


@pytest.mark.asyncio
async def test_summary_with_data(client: AsyncClient):
    headers = await make_user(client, "inc_sum_data@example.com")
    await client.post("/api/v1/income", json=_inc(50000, "salary",   "2026-05-01"), headers=headers)
    await client.post("/api/v1/income", json=_inc(10000, "freelance", "2026-05-15"), headers=headers)
    await client.post("/api/v1/income", json=_inc(5000,  "dividend",  "2026-05-20"), headers=headers)
    # Farklı ay — summary'e dahil olmamalı
    await client.post("/api/v1/income", json=_inc(20000, "bonus", "2026-04-01"), headers=headers)

    resp = await client.get("/api/v1/income/summary?year=2026&month=5", headers=headers)
    data = resp.json()
    assert float(data["total"]) == 65000.0
    assert data["count"] == 3
    categories = [b["category"] for b in data["by_category"]]
    assert "salary" in categories
    assert "freelance" in categories


@pytest.mark.asyncio
async def test_net_balance_calculation(client: AsyncClient):
    """Gelir ve gider endpoint'leri birlikte çalışıyor mu — net bakiye kontrolü."""
    headers = await make_user(client, "inc_net@example.com")
    await client.post("/api/v1/income",   json=_inc(50000, "salary", "2026-05-01"),     headers=headers)
    await client.post("/api/v1/expenses", json={"amount": 20000, "category": "bills", "date": "2026-05-10"}, headers=headers)

    income_sum  = await client.get("/api/v1/income/summary?year=2026&month=5",   headers=headers)
    expense_sum = await client.get("/api/v1/expenses/summary?year=2026&month=5", headers=headers)

    net = float(income_sum.json()["total"]) - float(expense_sum.json()["total"])
    assert net == 30000.0
