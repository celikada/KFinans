"""Expenses CRUD + summary endpoint testleri."""
import pytest
from httpx import AsyncClient

from tests.conftest import make_user, verify_user_email



def _exp(amount: float, category: str, date: str, description: str | None = None) -> dict:
    return {"amount": amount, "category": category, "date": date, "description": description}


# ─── CRUD ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_list(client: AsyncClient):
    headers = await make_user(client, "exp_empty@example.com")
    resp = await client.get("/api/v1/expenses", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_expense(client: AsyncClient):
    headers = await make_user(client, "exp_create@example.com")
    resp = await client.post(
        "/api/v1/expenses",
        json=_exp(150.50, "groceries", "2026-05-02", "Migros haftalik"),
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert float(data["amount"]) == 150.50
    assert data["category"] == "groceries"
    assert data["date"] == "2026-05-02"
    assert data["description"] == "Migros haftalik"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_invalid_category_returns_422(client: AsyncClient):
    headers = await make_user(client, "exp_bad_cat@example.com")
    resp = await client.post(
        "/api/v1/expenses",
        json=_exp(50, "yolo", "2026-05-02"),
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_negative_amount_returns_422(client: AsyncClient):
    headers = await make_user(client, "exp_neg@example.com")
    resp = await client.post(
        "/api/v1/expenses",
        json=_exp(-10, "food", "2026-05-02"),
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_zero_amount_returns_422(client: AsyncClient):
    """gt=0 — tam sifir kabul edilmez."""
    headers = await make_user(client, "exp_zero@example.com")
    resp = await client.post(
        "/api/v1/expenses",
        json=_exp(0, "food", "2026-05-02"),
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_expense(client: AsyncClient):
    headers = await make_user(client, "exp_update@example.com")
    create = await client.post(
        "/api/v1/expenses",
        json=_exp(50, "food", "2026-05-02", "ilk"),
        headers=headers,
    )
    expense_id = create.json()["id"]

    update = await client.put(
        f"/api/v1/expenses/{expense_id}",
        json={"amount": 75.50, "description": "guncellendi"},
        headers=headers,
    )
    assert update.status_code == 200
    assert float(update.json()["amount"]) == 75.50
    assert update.json()["description"] == "guncellendi"
    assert update.json()["category"] == "food"  # degismedi


@pytest.mark.asyncio
async def test_update_nonexistent_returns_404(client: AsyncClient):
    headers = await make_user(client, "exp_404@example.com")
    resp = await client.put(
        "/api/v1/expenses/99999",
        json={"amount": 100},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_expense(client: AsyncClient):
    headers = await make_user(client, "exp_delete@example.com")
    create = await client.post(
        "/api/v1/expenses",
        json=_exp(50, "food", "2026-05-02"),
        headers=headers,
    )
    expense_id = create.json()["id"]

    delete = await client.delete(f"/api/v1/expenses/{expense_id}", headers=headers)
    assert delete.status_code == 204

    get_after = await client.get("/api/v1/expenses", headers=headers)
    assert get_after.json() == []


@pytest.mark.asyncio
async def test_list_filters_by_year_month(client: AsyncClient):
    headers = await make_user(client, "exp_filter@example.com")
    await client.post("/api/v1/expenses", json=_exp(100, "food", "2026-04-15"), headers=headers)
    await client.post("/api/v1/expenses", json=_exp(200, "food", "2026-05-10"), headers=headers)
    await client.post("/api/v1/expenses", json=_exp(300, "food", "2026-05-20"), headers=headers)

    resp = await client.get("/api/v1/expenses?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2  # sadece Mayis kayitlari
    amounts = sorted(float(e["amount"]) for e in data)
    assert amounts == [200.0, 300.0]


@pytest.mark.asyncio
async def test_list_filters_by_category(client: AsyncClient):
    headers = await make_user(client, "exp_cat_filter@example.com")
    await client.post("/api/v1/expenses", json=_exp(50, "food", "2026-05-01"), headers=headers)
    await client.post("/api/v1/expenses", json=_exp(100, "transport", "2026-05-02"), headers=headers)
    await client.post("/api/v1/expenses", json=_exp(75, "food", "2026-05-03"), headers=headers)

    resp = await client.get("/api/v1/expenses?category=food", headers=headers)
    data = resp.json()
    assert len(data) == 2
    assert all(e["category"] == "food" for e in data)


@pytest.mark.asyncio
async def test_list_invalid_category_returns_422(client: AsyncClient):
    headers = await make_user(client, "exp_bad_filter@example.com")
    resp = await client.get("/api/v1/expenses?category=invalid", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_sorted_desc_by_date(client: AsyncClient):
    headers = await make_user(client, "exp_sort@example.com")
    await client.post("/api/v1/expenses", json=_exp(10, "food", "2026-05-01"), headers=headers)
    await client.post("/api/v1/expenses", json=_exp(20, "food", "2026-05-15"), headers=headers)
    await client.post("/api/v1/expenses", json=_exp(30, "food", "2026-05-10"), headers=headers)

    resp = await client.get("/api/v1/expenses", headers=headers)
    dates = [e["date"] for e in resp.json()]
    assert dates == ["2026-05-15", "2026-05-10", "2026-05-01"]


# ─── Summary ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summary_empty_month(client: AsyncClient):
    headers = await make_user(client, "sum_empty@example.com")
    resp = await client.get("/api/v1/expenses/summary?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2026
    assert data["month"] == 5
    assert float(data["total"]) == 0
    assert data["count"] == 0
    assert data["by_category"] == []


@pytest.mark.asyncio
async def test_summary_with_data(client: AsyncClient):
    headers = await make_user(client, "sum_data@example.com")
    await client.post("/api/v1/expenses", json=_exp(100, "food", "2026-05-05"), headers=headers)
    await client.post("/api/v1/expenses", json=_exp(50, "food", "2026-05-10"), headers=headers)
    await client.post("/api/v1/expenses", json=_exp(200, "transport", "2026-05-12"), headers=headers)
    # Farkli ay — summary'ye dahil olmamali
    await client.post("/api/v1/expenses", json=_exp(999, "food", "2026-04-15"), headers=headers)

    resp = await client.get("/api/v1/expenses/summary?year=2026&month=5", headers=headers)
    data = resp.json()
    assert float(data["total"]) == 350.0
    assert data["count"] == 3

    by_cat = {b["category"]: b for b in data["by_category"]}
    assert float(by_cat["food"]["total"]) == 150.0
    assert by_cat["food"]["count"] == 2
    assert float(by_cat["transport"]["total"]) == 200.0
    assert by_cat["transport"]["count"] == 1


# ─── IDOR ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_expenses(client: AsyncClient):
    a = await make_user(client, "exp_idor_a@example.com")
    b = await make_user(client, "exp_idor_b@example.com")
    await client.post("/api/v1/expenses", json=_exp(100, "food", "2026-05-02"), headers=b)

    resp_a = await client.get("/api/v1/expenses", headers=a)
    assert resp_a.json() == []


@pytest.mark.asyncio
async def test_user_a_cannot_update_user_b_expense(client: AsyncClient):
    a = await make_user(client, "exp_idor_upd_a@example.com")
    b = await make_user(client, "exp_idor_upd_b@example.com")
    create = await client.post("/api/v1/expenses", json=_exp(100, "food", "2026-05-02"), headers=b)
    b_expense_id = create.json()["id"]

    resp = await client.put(
        f"/api/v1/expenses/{b_expense_id}",
        json={"amount": 1},
        headers=a,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_delete_user_b_expense(client: AsyncClient):
    a = await make_user(client, "exp_idor_del_a@example.com")
    b = await make_user(client, "exp_idor_del_b@example.com")
    create = await client.post("/api/v1/expenses", json=_exp(100, "food", "2026-05-02"), headers=b)
    b_expense_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/expenses/{b_expense_id}", headers=a)
    assert resp.status_code == 404


# ─── Auth ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unauth_returns_401(client: AsyncClient):
    for method, path in [
        ("GET", "/api/v1/expenses"),
        ("POST", "/api/v1/expenses"),
        ("GET", "/api/v1/expenses/summary?year=2026&month=5"),
    ]:
        resp = await client.request(method, path)
        assert resp.status_code == 401, f"{method} {path}"
