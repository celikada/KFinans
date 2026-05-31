"""PlannedExpense CRUD + forecast endpoint testleri."""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


def _loan(
    title: str = "Ziraat Kredisi",
    amount: float = 5000.0,
    recurrence: str = "monthly",
    start_date: str = "2026-01-15",
    remaining_count: int | None = 12,
    category: str = "loan",
    is_estimated: bool = False,
) -> dict:
    payload: dict = {
        "title": title,
        "amount": amount,
        "category": category,
        "recurrence": recurrence,
        "start_date": start_date,
        "is_estimated": is_estimated,
        "day_of_month": 15,
    }
    if remaining_count is not None:
        payload["remaining_count"] = remaining_count
    return payload


# ─── CRUD ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_list(client: AsyncClient):
    headers = await make_user(client, "pe_empty@example.com")
    resp = await client.get("/api/v1/planned-expenses", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_monthly_loan(client: AsyncClient):
    headers = await make_user(client, "pe_create@example.com")
    resp = await client.post("/api/v1/planned-expenses", json=_loan(), headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Ziraat Kredisi"
    assert float(data["amount"]) == 5000.0
    assert data["recurrence"] == "monthly"
    assert data["remaining_count"] == 12
    # end_date = start_date + 11 ay = 2026-12-15
    assert data["end_date"] == "2026-12-15"


@pytest.mark.asyncio
async def test_create_yearly_tax(client: AsyncClient):
    headers = await make_user(client, "pe_yearly@example.com")
    payload = {
        "title": "Gelir Vergisi",
        "amount": 8000.0,
        "category": "tax",
        "recurrence": "yearly",
        "start_date": "2026-03-01",
        "day_of_month": 1,
        "is_estimated": True,
    }
    resp = await client.post("/api/v1/planned-expenses", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["category"] == "tax"
    assert data["is_estimated"] is True
    assert data["end_date"] is None


@pytest.mark.asyncio
async def test_create_custom_recurrence(client: AsyncClient):
    headers = await make_user(client, "pe_custom@example.com")
    payload = {
        "title": "Sigorta Primi",
        "amount": 3000.0,
        "category": "insurance",
        "recurrence": "custom",
        "months": [3, 9],
        "start_date": "2026-01-01",
        "day_of_month": 1,
    }
    resp = await client.post("/api/v1/planned-expenses", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["months"] == [3, 9]


@pytest.mark.asyncio
async def test_create_invalid_category_returns_422(client: AsyncClient):
    headers = await make_user(client, "pe_badcat@example.com")
    payload = _loan(category="yolo")
    resp = await client.post("/api/v1/planned-expenses", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_invalid_recurrence_returns_422(client: AsyncClient):
    headers = await make_user(client, "pe_badrec@example.com")
    payload = _loan(recurrence="weekly")
    resp = await client.post("/api/v1/planned-expenses", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_planned_expense(client: AsyncClient):
    headers = await make_user(client, "pe_update@example.com")
    create = await client.post("/api/v1/planned-expenses", json=_loan(), headers=headers)
    pe_id = create.json()["id"]

    resp = await client.put(
        f"/api/v1/planned-expenses/{pe_id}",
        json={"amount": 5500.0, "notes": "Güncellendi"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["amount"]) == 5500.0
    assert data["notes"] == "Güncellendi"


@pytest.mark.asyncio
async def test_delete_planned_expense(client: AsyncClient):
    headers = await make_user(client, "pe_delete@example.com")
    create = await client.post("/api/v1/planned-expenses", json=_loan(), headers=headers)
    pe_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/planned-expenses/{pe_id}", headers=headers)
    assert resp.status_code == 204

    list_resp = await client.get("/api/v1/planned-expenses", headers=headers)
    assert list_resp.json() == []


# ─── IDOR ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_idor_update_returns_404(client: AsyncClient):
    h1 = await make_user(client, "pe_idor1@example.com")
    h2 = await make_user(client, "pe_idor2@example.com")
    create = await client.post("/api/v1/planned-expenses", json=_loan(), headers=h1)
    pe_id = create.json()["id"]

    resp = await client.put(
        f"/api/v1/planned-expenses/{pe_id}",
        json={"amount": 1.0},
        headers=h2,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_idor_delete_returns_404(client: AsyncClient):
    h1 = await make_user(client, "pe_idor3@example.com")
    h2 = await make_user(client, "pe_idor4@example.com")
    create = await client.post("/api/v1/planned-expenses", json=_loan(), headers=h1)
    pe_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/planned-expenses/{pe_id}", headers=h2)
    assert resp.status_code == 404


# ─── AUTH ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/planned-expenses")
    assert resp.status_code == 401


# ─── FORECAST ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forecast_empty(client: AsyncClient):
    headers = await make_user(client, "pe_fc_empty@example.com")
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2026
    assert len(data["months"]) == 12
    assert float(data["year_total"]) == 0.0
    assert all(float(m["total"]) == 0.0 for m in data["months"])


@pytest.mark.asyncio
async def test_forecast_monthly_loan(client: AsyncClient):
    """Aylik kredi 12 ay boyunca her ayda gorünmeli."""
    headers = await make_user(client, "pe_fc_loan@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json=_loan(start_date="2026-01-15", remaining_count=12),
        headers=headers,
    )

    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    data = resp.json()
    active_months = [m for m in data["months"] if float(m["total"]) > 0]
    assert len(active_months) == 12
    assert float(data["year_total"]) == 5000.0 * 12


@pytest.mark.asyncio
async def test_forecast_yearly_tax(client: AsyncClient):
    """Yillik vergi sadece Mart'ta gorünmeli."""
    headers = await make_user(client, "pe_fc_tax@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "Gelir Vergisi",
            "amount": 8000.0,
            "category": "tax",
            "recurrence": "yearly",
            "start_date": "2026-03-01",
            "day_of_month": 1,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    data = resp.json()
    march = next(m for m in data["months"] if m["month"] == 3)
    assert float(march["total"]) == 8000.0
    assert float(data["year_total"]) == 8000.0
    non_march = [m for m in data["months"] if m["month"] != 3]
    assert all(float(m["total"]) == 0.0 for m in non_march)


@pytest.mark.asyncio
async def test_forecast_custom_recurrence(client: AsyncClient):
    """Ozel tekrar: [3, 9] → sadece Mart ve Eylul'de gorünmeli."""
    headers = await make_user(client, "pe_fc_custom@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "Sigorta",
            "amount": 3000.0,
            "category": "insurance",
            "recurrence": "custom",
            "months": [3, 9],
            "start_date": "2026-01-01",
            "day_of_month": 1,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    data = resp.json()
    active = [m for m in data["months"] if float(m["total"]) > 0]
    assert len(active) == 2
    assert {m["month"] for m in active} == {3, 9}
    assert float(data["year_total"]) == 6000.0


@pytest.mark.asyncio
async def test_forecast_is_estimated_flag(client: AsyncClient):
    headers = await make_user(client, "pe_fc_est@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "Elektrik",
            "amount": 800.0,
            "category": "utility",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "day_of_month": 1,
            "is_estimated": True,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    jan = resp.json()["months"][0]
    assert jan["items"][0]["is_estimated"] is True


# ─── UPDATE edge cases + 404 ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_nonexistent_returns_404(client: AsyncClient):
    headers = await make_user(client, "pe_upd_404@example.com")
    resp = await client.put("/api/v1/planned-expenses/99999", json={"amount": 1.0}, headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(client: AsyncClient):
    headers = await make_user(client, "pe_del_404@example.com")
    resp = await client.delete("/api/v1/planned-expenses/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_many_fields(client: AsyncClient):
    headers = await make_user(client, "pe_upd_many@example.com")
    create = await client.post("/api/v1/planned-expenses", json=_loan(), headers=headers)
    pe_id = create.json()["id"]
    resp = await client.put(
        f"/api/v1/planned-expenses/{pe_id}",
        json={
            "title": "Yeni Kredi",
            "category": "rent",
            "recurrence": "quarterly",
            "is_estimated": True,
            "start_date": "2026-02-01",
            "day_of_month": 5,
            "is_paid": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Yeni Kredi"
    assert data["category"] == "rent"
    assert data["recurrence"] == "quarterly"
    assert data["is_estimated"] is True
    assert data["day_of_month"] == 5
    assert data["is_paid"] is True


@pytest.mark.asyncio
async def test_update_credit_card_unlink(client: AsyncClient):
    headers = await make_user(client, "pe_cc_unlink@example.com")
    payload = _loan()
    payload["credit_card_id"] = None
    payload["is_paid"] = True
    create = await client.post("/api/v1/planned-expenses", json=payload, headers=headers)
    pe_id = create.json()["id"]
    resp = await client.put(
        f"/api/v1/planned-expenses/{pe_id}",
        json={"credit_card_id": None},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["credit_card_id"] is None


@pytest.mark.asyncio
async def test_create_with_remaining_count_no_end_date_non_monthly(client: AsyncClient):
    """remaining_count var ama recurrence monthly degil → end_date hesaplanmaz."""
    headers = await make_user(client, "pe_rc_quarterly@example.com")
    payload = _loan(recurrence="quarterly", remaining_count=4)
    resp = await client.post("/api/v1/planned-expenses", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["end_date"] is None


@pytest.mark.asyncio
async def test_create_quarterly_recurrence(client: AsyncClient):
    """quarterly _applies_in_month dali — Oca,Nis,Tem,Eki."""
    headers = await make_user(client, "pe_quarterly@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "3 Aylik Aidat",
            "amount": 1000.0,
            "category": "subscription",
            "recurrence": "quarterly",
            "start_date": "2026-01-01",
            "day_of_month": 1,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    active = {m["month"] for m in resp.json()["months"] if float(m["total"]) > 0}
    assert active == {1, 4, 7, 10}


@pytest.mark.asyncio
async def test_create_biannual_recurrence(client: AsyncClient):
    headers = await make_user(client, "pe_biannual@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "6 Aylik",
            "amount": 2000.0,
            "category": "insurance",
            "recurrence": "biannual",
            "start_date": "2026-02-01",
            "day_of_month": 1,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    active = {m["month"] for m in resp.json()["months"] if float(m["total"]) > 0}
    assert active == {2, 8}


@pytest.mark.asyncio
async def test_create_one_time_recurrence(client: AsyncClient):
    headers = await make_user(client, "pe_onetime@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "Tek Seferlik",
            "amount": 9999.0,
            "category": "other",
            "recurrence": "one_time",
            "start_date": "2026-06-15",
            "day_of_month": 15,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    active = {m["month"] for m in resp.json()["months"] if float(m["total"]) > 0}
    assert active == {6}


@pytest.mark.asyncio
async def test_create_with_end_date_limits_forecast(client: AsyncClient):
    """end_date'ten sonraki aylar forecast'ta gorunmemeli."""
    headers = await make_user(client, "pe_enddate@example.com")
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "Kisa Kredi",
            "amount": 1000.0,
            "category": "loan",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "day_of_month": 1,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    active = {m["month"] for m in resp.json()["months"] if float(m["total"]) > 0}
    assert active == {1, 2, 3}


# ─── Çift sayım kuralı (forecast) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forecast_excludes_paid_credit_card(client: AsyncClient):
    """credit_card_id + is_paid=true → forecast'a dahil edilmez."""
    headers = await make_user(client, "pe_fc_double@example.com")
    # Gerçek kart oluştur (credit_card_id FK; olmayan id FK ihlali → plan oluşmaz)
    card = await client.post("/api/v1/credit-cards", json={"name": "Test Kart"}, headers=headers)
    cid = card.json()["id"]
    # Kart + odendi → HARIC
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "Odenmis Kart Plani",
            "amount": 5000.0,
            "category": "loan",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "day_of_month": 1,
            "credit_card_id": cid,
            "is_paid": True,
        },
        headers=headers,
    )
    # Kart ama odenmemis → DAHIL
    await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": "Odenmemis Kart Plani",
            "amount": 1000.0,
            "category": "loan",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "day_of_month": 1,
            "credit_card_id": cid,
            "is_paid": False,
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026", headers=headers)
    data = resp.json()
    # Sadece odenmemis (1000 * 12)
    assert float(data["year_total"]) == 12000.0


@pytest.mark.asyncio
async def test_forecast_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/planned-expenses/forecast?year=2026")
    assert resp.status_code == 401
