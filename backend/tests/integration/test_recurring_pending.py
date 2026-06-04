"""Periyodik gerçekleşme: gider realize + skip + pending (popup) testleri.

Gelir realize zaten test_income_api.py'de; burada yeni eklenenler: planned_expense
→ expense realize, dönem-bazlı skip, /recurring/pending hesabı.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user

# start_date birkaç ay öncesi (bugüne göre dönemler ödeme günü geçmiş olur).
_START = "2026-01-01"


async def _make_planned(client: AsyncClient, headers, title="Kira", amount="5000"):
    resp = await client.post(
        "/api/v1/planned-expenses",
        json={
            "title": title,
            "amount": amount,
            "category": "rent",
            "recurrence": "monthly",
            "day_of_month": 1,
            "start_date": _START,
            "is_estimated": False,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _make_recurring_income(client: AsyncClient, headers, title="Maaş", amount="40000"):
    resp = await client.post(
        "/api/v1/income/recurring",
        json={
            "title": title,
            "amount": amount,
            "category": "salary",
            "recurrence": "monthly",
            "day_of_month": 1,
            "start_date": _START,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ─── Gider realize ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_realize_planned_creates_expense(client: AsyncClient):
    headers = await make_user(client, "rp_realize@example.com")
    pe_id = await _make_planned(client, headers)

    resp = await client.post(
        f"/api/v1/planned-expenses/{pe_id}/realize",
        json={"year": 2026, "month": 1},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["realized"] == 1

    # expenses listesinde 2026-01-01 kaydı oluştu
    exps = (await client.get("/api/v1/expenses?year=2026&month=1", headers=headers)).json()
    assert any(e["planned_expense_id"] == pe_id and e["date"] == "2026-01-01" for e in exps)


@pytest.mark.asyncio
async def test_realize_planned_idempotent(client: AsyncClient):
    headers = await make_user(client, "rp_idem@example.com")
    pe_id = await _make_planned(client, headers)
    body = {"year": 2026, "month": 1}
    first = await client.post(f"/api/v1/planned-expenses/{pe_id}/realize", json=body, headers=headers)
    second = await client.post(f"/api/v1/planned-expenses/{pe_id}/realize", json=body, headers=headers)
    assert first.json()["realized"] == 1
    assert second.json()["realized"] == 0 and second.json()["skipped"] == 1


@pytest.mark.asyncio
async def test_realize_planned_future_month_rejected(client: AsyncClient):
    headers = await make_user(client, "rp_future@example.com")
    pe_id = await _make_planned(client, headers)
    resp = await client.post(
        f"/api/v1/planned-expenses/{pe_id}/realize",
        json={"year": 2099, "month": 1},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_realize_planned_past_creates_many(client: AsyncClient):
    headers = await make_user(client, "rp_past@example.com")
    pe_id = await _make_planned(client, headers)
    resp = await client.post(f"/api/v1/planned-expenses/{pe_id}/realize-past", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["realized"] >= 1  # start'tan bugüne en az 1 dönem


# ─── Pending ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pending_lists_income_and_expense(client: AsyncClient):
    headers = await make_user(client, "rp_pending@example.com")
    pe_id = await _make_planned(client, headers)
    ri_id = await _make_recurring_income(client, headers)

    data = (await client.get("/api/v1/recurring/pending", headers=headers)).json()
    kinds = {(it["kind"], it["ref_id"]) for it in data["items"]}
    assert ("expense", pe_id) in kinds
    assert ("income", ri_id) in kinds
    # 2026-01 her ikisi için de pending
    assert any(it["kind"] == "expense" and it["period_year"] == 2026 and it["period_month"] == 1 for it in data["items"])


@pytest.mark.asyncio
async def test_realize_removes_from_pending(client: AsyncClient):
    headers = await make_user(client, "rp_pend_realize@example.com")
    pe_id = await _make_planned(client, headers)
    await client.post(f"/api/v1/planned-expenses/{pe_id}/realize", json={"year": 2026, "month": 1}, headers=headers)
    data = (await client.get("/api/v1/recurring/pending", headers=headers)).json()
    assert not any(it["kind"] == "expense" and it["ref_id"] == pe_id and it["period_month"] == 1 for it in data["items"])


@pytest.mark.asyncio
async def test_skip_removes_from_pending(client: AsyncClient):
    headers = await make_user(client, "rp_skip@example.com")
    ri_id = await _make_recurring_income(client, headers)
    skip = await client.post(
        "/api/v1/recurring/skips",
        json={"kind": "income", "ref_id": ri_id, "year": 2026, "month": 1},
        headers=headers,
    )
    assert skip.status_code == 201
    data = (await client.get("/api/v1/recurring/pending", headers=headers)).json()
    assert not any(it["kind"] == "income" and it["ref_id"] == ri_id and it["period_month"] == 1 for it in data["items"])


@pytest.mark.asyncio
async def test_skip_idempotent(client: AsyncClient):
    headers = await make_user(client, "rp_skip_idem@example.com")
    pe_id = await _make_planned(client, headers)
    body = {"kind": "expense", "ref_id": pe_id, "year": 2026, "month": 2}
    first = await client.post("/api/v1/recurring/skips", json=body, headers=headers)
    second = await client.post("/api/v1/recurring/skips", json=body, headers=headers)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]  # aynı kayıt döner


@pytest.mark.asyncio
async def test_skip_idor_other_users_ref(client: AsyncClient):
    owner = await make_user(client, "rp_owner@example.com")
    pe_id = await _make_planned(client, owner)
    attacker = await make_user(client, "rp_attacker@example.com")
    resp = await client.post(
        "/api/v1/recurring/skips",
        json={"kind": "expense", "ref_id": pe_id, "year": 2026, "month": 1},
        headers=attacker,
    )
    assert resp.status_code == 404
