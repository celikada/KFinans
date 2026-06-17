"""Bütçe v2 (hibrit) endpoint testleri: grid + monthly 3-kova + settings + notes."""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user

# ───────────────────────────── Izgara (grid) ─────────────────────────────


@pytest.mark.asyncio
async def test_grid_empty(client: AsyncClient):
    headers = await make_user(client, "bv2_grid_empty@example.com")
    resp = await client.get("/api/v1/budgets/grid?year=2026", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2026
    assert len(data["monthly_planned_display"]) == 12
    # Kategoriler döner ama planlanan toplam 0.
    assert float(data["planned_total_display"]) == 0.0
    assert any(r["category"] == "savings" for r in data["rows"])


@pytest.mark.asyncio
async def test_grid_upsert_cell(client: AsyncClient):
    headers = await make_user(client, "bv2_grid_cell@example.com")
    resp = await client.put("/api/v1/budgets/grid/2026/5/food", json={"amount": 3000}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["category"] == "food"

    grid = await client.get("/api/v1/budgets/grid?year=2026", headers=headers)
    food = next(r for r in grid.json()["rows"] if r["category"] == "food")
    may = next(c for c in food["cells"] if c["month"] == 5)
    assert float(may["planned"]) == 3000.0
    assert float(food["planned_total_display"]) == 3000.0
    assert float(grid.json()["monthly_planned_display"][4]) == 3000.0


@pytest.mark.asyncio
async def test_grid_invalid_category(client: AsyncClient):
    headers = await make_user(client, "bv2_grid_badcat@example.com")
    resp = await client.put("/api/v1/budgets/grid/2026/5/crypto", json={"amount": 100}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_grid_savings_category_allowed(client: AsyncClient):
    headers = await make_user(client, "bv2_grid_savings@example.com")
    resp = await client.put("/api/v1/budgets/grid/2026/5/savings", json={"amount": 5000}, headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_grid_delete_cell(client: AsyncClient):
    headers = await make_user(client, "bv2_grid_del@example.com")
    await client.put("/api/v1/budgets/grid/2026/5/food", json={"amount": 3000}, headers=headers)
    resp = await client.delete("/api/v1/budgets/grid/2026/5/food", headers=headers)
    assert resp.status_code == 204
    resp404 = await client.delete("/api/v1/budgets/grid/2026/5/food", headers=headers)
    assert resp404.status_code == 404


@pytest.mark.asyncio
async def test_grid_actual_from_expense(client: AsyncClient):
    headers = await make_user(client, "bv2_grid_actual@example.com")
    await client.post(
        "/api/v1/expenses",
        json={"amount": 1200, "category": "groceries", "date": "2026-05-10"},
        headers=headers,
    )
    grid = await client.get("/api/v1/budgets/grid?year=2026", headers=headers)
    groceries = next(r for r in grid.json()["rows"] if r["category"] == "groceries")
    may = next(c for c in groceries["cells"] if c["month"] == 5)
    assert float(may["actual_display"]) == 1200.0


@pytest.mark.asyncio
async def test_grid_idor(client: AsyncClient):
    h1 = await make_user(client, "bv2_grid_idor1@example.com")
    h2 = await make_user(client, "bv2_grid_idor2@example.com")
    await client.put("/api/v1/budgets/grid/2026/5/food", json={"amount": 3000}, headers=h1)
    grid = await client.get("/api/v1/budgets/grid?year=2026", headers=h2)
    assert float(grid.json()["planned_total_display"]) == 0.0
    resp = await client.delete("/api/v1/budgets/grid/2026/5/food", headers=h2)
    assert resp.status_code == 404


# ─────────────────────────── Aylık 3-kova ───────────────────────────


@pytest.mark.asyncio
async def test_monthly_buckets_shape(client: AsyncClient):
    headers = await make_user(client, "bv2_monthly_shape@example.com")
    resp = await client.get("/api/v1/budgets/monthly?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    buckets = {b["bucket"] for b in data["buckets"]}
    assert buckets == {"fundamental", "fun", "future"}
    # Varsayılan oranlar
    fund = next(b for b in data["buckets"] if b["bucket"] == "fundamental")
    assert fund["target_ratio"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_monthly_income_expense_net(client: AsyncClient):
    headers = await make_user(client, "bv2_monthly_net@example.com")
    await client.post("/api/v1/income", json={"amount": 50000, "category": "salary", "date": "2026-05-01"}, headers=headers)
    await client.post("/api/v1/expenses", json={"amount": 8000, "category": "groceries", "date": "2026-05-10"}, headers=headers)
    resp = await client.get("/api/v1/budgets/monthly?year=2026&month=5", headers=headers)
    data = resp.json()
    assert float(data["income_display"]) == 50000.0
    assert float(data["expense_total_display"]) == 8000.0
    assert float(data["net_display"]) == 42000.0
    fund = next(b for b in data["buckets"] if b["bucket"] == "fundamental")
    groceries = next(c for c in fund["categories"] if c["category"] == "groceries")
    assert float(groceries["actual_display"]) == 8000.0


@pytest.mark.asyncio
async def test_monthly_over_budget(client: AsyncClient):
    headers = await make_user(client, "bv2_monthly_over@example.com")
    await client.put("/api/v1/budgets/grid/2026/5/groceries", json={"amount": 5000}, headers=headers)
    await client.post("/api/v1/expenses", json={"amount": 7000, "category": "groceries", "date": "2026-05-10"}, headers=headers)
    resp = await client.get("/api/v1/budgets/monthly?year=2026&month=5", headers=headers)
    fund = next(b for b in resp.json()["buckets"] if b["bucket"] == "fundamental")
    groceries = next(c for c in fund["categories"] if c["category"] == "groceries")
    assert groceries["over_budget"] is True


@pytest.mark.asyncio
async def test_monthly_weighted_periodic(client: AsyncClient):
    """Yıllık planlı gider → aylık-eşdeğer (yıllık/12) ağırlıklı satır olarak görünür."""
    headers = await make_user(client, "bv2_monthly_weighted@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "Kasko",
            "amount": 12000,
            "category": "insurance",
            "recurrence": "yearly",
            "start_date": "2026-03-01",
            "day_of_month": 1,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/budgets/monthly?year=2026&month=5", headers=headers)
    fund = next(b for b in resp.json()["buckets"] if b["bucket"] == "fundamental")
    weighted = [c for c in fund["categories"] if c["weighted"]]
    assert any(c["category"] == "Kasko" for c in weighted)
    kasko = next(c for c in weighted if c["category"] == "Kasko")
    # 12000 yıllık → /12 = 1000 aylık-eşdeğer
    assert float(kasko["budget_display"]) == pytest.approx(1000.0)


# ─────────────────────────── Kova ayarları ───────────────────────────


@pytest.mark.asyncio
async def test_settings_default(client: AsyncClient):
    headers = await make_user(client, "bv2_settings_def@example.com")
    resp = await client.get("/api/v1/budgets/settings", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["fundamental_ratio"] == pytest.approx(0.5)
    assert data["category_buckets"]["groceries"] == "fundamental"
    assert data["category_buckets"]["food"] == "fun"
    assert data["category_buckets"]["savings"] == "future"


@pytest.mark.asyncio
async def test_settings_update(client: AsyncClient):
    headers = await make_user(client, "bv2_settings_upd@example.com")
    resp = await client.put(
        "/api/v1/budgets/settings",
        json={"fundamental_ratio": 0.6, "fun_ratio": 0.2, "future_ratio": 0.2, "category_buckets": {"food": "fundamental"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["fundamental_ratio"] == pytest.approx(0.6)
    assert resp.json()["category_buckets"]["food"] == "fundamental"


@pytest.mark.asyncio
async def test_settings_ratio_sum_invalid(client: AsyncClient):
    headers = await make_user(client, "bv2_settings_bad@example.com")
    resp = await client.put(
        "/api/v1/budgets/settings",
        json={"fundamental_ratio": 0.5, "fun_ratio": 0.5, "future_ratio": 0.5},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_settings_override_changes_bucket(client: AsyncClient):
    headers = await make_user(client, "bv2_settings_ovr@example.com")
    await client.put(
        "/api/v1/budgets/settings",
        json={"fundamental_ratio": 0.5, "fun_ratio": 0.3, "future_ratio": 0.2, "category_buckets": {"food": "fundamental"}},
        headers=headers,
    )
    await client.post("/api/v1/expenses", json={"amount": 500, "category": "food", "date": "2026-05-10"}, headers=headers)
    resp = await client.get("/api/v1/budgets/monthly?year=2026&month=5", headers=headers)
    fund = next(b for b in resp.json()["buckets"] if b["bucket"] == "fundamental")
    assert any(c["category"] == "food" for c in fund["categories"])


# ─────────────────────────── Aylık not ───────────────────────────


@pytest.mark.asyncio
async def test_note_default_empty(client: AsyncClient):
    headers = await make_user(client, "bv2_note_empty@example.com")
    resp = await client.get("/api/v1/budgets/notes/2026/5", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["analysis"] is None


@pytest.mark.asyncio
async def test_note_upsert(client: AsyncClient):
    headers = await make_user(client, "bv2_note_upsert@example.com")
    resp = await client.put(
        "/api/v1/budgets/notes/2026/5",
        json={"analysis": "İyi geçti", "action_plan": "Daha az dışarıda ye"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["analysis"] == "İyi geçti"

    get = await client.get("/api/v1/budgets/notes/2026/5", headers=headers)
    assert get.json()["action_plan"] == "Daha az dışarıda ye"


@pytest.mark.asyncio
async def test_v2_unauthenticated(client: AsyncClient):
    for url in ("/api/v1/budgets/grid?year=2026", "/api/v1/budgets/monthly?year=2026&month=5", "/api/v1/budgets/settings"):
        resp = await client.get(url)
        assert resp.status_code == 401
