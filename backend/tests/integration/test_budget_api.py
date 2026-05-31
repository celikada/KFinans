"""Budget CRUD + comparison endpoint testleri."""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


@pytest.mark.asyncio
async def test_empty_list(client: AsyncClient):
    headers = await make_user(client, "bgt_empty@example.com")
    resp = await client.get("/api/v1/budgets", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_upsert_create(client: AsyncClient):
    headers = await make_user(client, "bgt_create@example.com")
    resp = await client.put("/api/v1/budgets/food", json={"amount": 3000}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "food"
    assert float(data["amount"]) == 3000.0
    assert "id" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_upsert_update(client: AsyncClient):
    headers = await make_user(client, "bgt_update@example.com")
    await client.put("/api/v1/budgets/food", json={"amount": 3000}, headers=headers)
    resp = await client.put("/api/v1/budgets/food", json={"amount": 4500}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 4500.0

    list_resp = await client.get("/api/v1/budgets", headers=headers)
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_upsert_invalid_category(client: AsyncClient):
    headers = await make_user(client, "bgt_badcat@example.com")
    resp = await client.put("/api/v1/budgets/crypto", json={"amount": 1000}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upsert_negative_amount(client: AsyncClient):
    headers = await make_user(client, "bgt_neg@example.com")
    resp = await client.put("/api/v1/budgets/food", json={"amount": -500}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_budget(client: AsyncClient):
    headers = await make_user(client, "bgt_delete@example.com")
    await client.put("/api/v1/budgets/food", json={"amount": 3000}, headers=headers)
    resp = await client.delete("/api/v1/budgets/food", headers=headers)
    assert resp.status_code == 204

    list_resp = await client.get("/api/v1/budgets", headers=headers)
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_delete_nonexistent(client: AsyncClient):
    headers = await make_user(client, "bgt_del404@example.com")
    resp = await client.delete("/api/v1/budgets/food", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/budgets")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_comparison_no_data(client: AsyncClient):
    headers = await make_user(client, "bgt_cmp_empty@example.com")
    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_comparison_under_budget(client: AsyncClient):
    headers = await make_user(client, "bgt_cmp_under@example.com")
    await client.put("/api/v1/budgets/food", json={"amount": 5000}, headers=headers)
    await client.post(
        "/api/v1/expenses",
        json={"amount": 2000, "category": "food", "date": "2026-05-10"},
        headers=headers,
    )
    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    food = next(r for r in data if r["category"] == "food")
    assert float(food["budget_amount"]) == 5000.0
    assert float(food["actual_amount"]) == 2000.0
    assert float(food["remaining"]) == 3000.0
    assert food["over_budget"] is False
    assert food["pct_used"] == pytest.approx(40.0)


@pytest.mark.asyncio
async def test_comparison_over_budget(client: AsyncClient):
    headers = await make_user(client, "bgt_cmp_over@example.com")
    await client.put("/api/v1/budgets/transport", json={"amount": 1000}, headers=headers)
    await client.post(
        "/api/v1/expenses",
        json={"amount": 1500, "category": "transport", "date": "2026-05-05"},
        headers=headers,
    )
    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5", headers=headers)
    row = next(r for r in resp.json() if r["category"] == "transport")
    assert row["over_budget"] is True
    assert float(row["remaining"]) == pytest.approx(-500.0)
    assert row["pct_used"] == pytest.approx(150.0)


@pytest.mark.asyncio
async def test_comparison_expense_without_budget(client: AsyncClient):
    headers = await make_user(client, "bgt_cmp_nobgt@example.com")
    await client.post(
        "/api/v1/expenses",
        json={"amount": 800, "category": "health", "date": "2026-05-12"},
        headers=headers,
    )
    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5", headers=headers)
    row = next(r for r in resp.json() if r["category"] == "health")
    assert row["budget_amount"] is None
    assert row["remaining"] is None
    assert row["pct_used"] is None
    assert row["over_budget"] is False


@pytest.mark.asyncio
async def test_comparison_multiple_categories(client: AsyncClient):
    headers = await make_user(client, "bgt_cmp_multi@example.com")
    await client.put("/api/v1/budgets/food", json={"amount": 3000}, headers=headers)
    await client.put("/api/v1/budgets/transport", json={"amount": 1000}, headers=headers)
    await client.put("/api/v1/budgets/bills", json={"amount": 2000}, headers=headers)
    await client.post(
        "/api/v1/expenses",
        json={"amount": 2800, "category": "food", "date": "2026-05-01"},
        headers=headers,
    )
    await client.post(
        "/api/v1/expenses",
        json={"amount": 1200, "category": "transport", "date": "2026-05-02"},
        headers=headers,
    )

    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5", headers=headers)
    data = {r["category"]: r for r in resp.json()}
    assert data["food"]["over_budget"] is False
    assert data["transport"]["over_budget"] is True
    assert float(data["bills"]["actual_amount"]) == 0.0


@pytest.mark.asyncio
async def test_idor_budgets(client: AsyncClient):
    h1 = await make_user(client, "bgt_idor1@example.com")
    h2 = await make_user(client, "bgt_idor2@example.com")
    await client.put("/api/v1/budgets/food", json={"amount": 3000}, headers=h1)

    resp = await client.get("/api/v1/budgets", headers=h2)
    assert resp.json() == []

    resp2 = await client.delete("/api/v1/budgets/food", headers=h2)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_comparison_no_budget_pct_none(client: AsyncClient):
    """Bütçesi olmayan kategori → budget_amount/pct_used None (sıfıra bölme korumalı).

    Not: amount=0 bütçe API'den kurulamaz (şema gt=0 → 422); pct_used=None dalı
    yalnızca bütçesi set edilmemiş (budget_amount None) kategoriler için tetiklenir.
    """
    headers = await make_user(client, "bgt_zero@example.com")
    await client.post(
        "/api/v1/expenses",
        json={"amount": 100, "category": "food", "date": "2026-05-10"},
        headers=headers,
    )
    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5", headers=headers)
    food = next(r for r in resp.json() if r["category"] == "food")
    assert food["budget_amount"] is None
    assert food["pct_used"] is None
    assert food["over_budget"] is False
    assert float(food["actual_amount"]) == 100.0


@pytest.mark.asyncio
async def test_comparison_excludes_paid_credit_card(client: AsyncClient):
    """Cift sayim: kart + odendi olan harcama comparison actual'a girmez."""
    headers = await make_user(client, "bgt_cmp_double@example.com")
    # Gerçek kart oluştur (credit_card_id FK; olmayan id FK ihlali → harcama oluşmaz,
    # hariç tutma testi sahte-pozitif olur)
    card = await client.post("/api/v1/credit-cards", json={"name": "Test Kart"}, headers=headers)
    cid = card.json()["id"]
    await client.put("/api/v1/budgets/food", json={"amount": 5000}, headers=headers)
    # nakit — dahil
    await client.post(
        "/api/v1/expenses",
        json={"amount": 1000, "category": "food", "date": "2026-05-01"},
        headers=headers,
    )
    # kart + odendi — haric
    await client.post(
        "/api/v1/expenses",
        json={"amount": 3000, "category": "food", "date": "2026-05-02", "credit_card_id": cid, "is_paid": True},
        headers=headers,
    )
    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5", headers=headers)
    food = next(r for r in resp.json() if r["category"] == "food")
    assert float(food["actual_amount"]) == 1000.0
    assert float(food["remaining"]) == 4000.0


@pytest.mark.asyncio
async def test_comparison_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upsert_unauthenticated(client: AsyncClient):
    resp = await client.put("/api/v1/budgets/food", json={"amount": 1000})
    assert resp.status_code == 401
