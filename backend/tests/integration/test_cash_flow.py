"""
Cash Flow API integration testleri.

GET /cash-flow?year=2026 — 12 aylık nakit akış projeksiyonu (gerçek + tahmini).

Schema (CashFlowMonth):
  - income_actual / income_forecast / income_total
  - expense_actual / expense_forecast / expense_total
  - net (income_total - expense_total)
  - is_past
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.expense import Expense
from app.models.income import Income
from app.models.recurring_income import RecurringIncome
from tests.conftest import TestSession, verify_user_email


async def _make_user(client: AsyncClient, email: str) -> dict:
    pwd = "guclu-sifre-123"
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd, "age_confirmed": True})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd, "age_confirmed": True})
    return {
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        "email": email,
    }


async def _get_user_id(email: str):
    from app.models.user import User
    async with TestSession() as db:
        u = (await db.execute(select(User).where(User.email == email))).scalar_one()
        return u.id


# ─── Auth + validation ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/cash-flow?year=2026")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cash_flow_year_validation(client: AsyncClient):
    """year < 2020 veya > 2100 -> 422."""
    session = await _make_user(client, "cf_year_invalid@example.com")
    bad = await client.get("/api/v1/cash-flow?year=1990", headers=session["headers"])
    assert bad.status_code == 422
    bad2 = await client.get("/api/v1/cash-flow?year=2200", headers=session["headers"])
    assert bad2.status_code == 422


# ─── Boş kullanıcı ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_empty_user_returns_zeros(client: AsyncClient):
    """Hiç income/expense olmayan user -> 12 ay 0 değeri."""
    session = await _make_user(client, "cf_empty@example.com")
    resp = await client.get("/api/v1/cash-flow?year=2026", headers=session["headers"])
    assert resp.status_code == 200
    data = resp.json()

    assert data["year"] == 2026
    assert "months" in data
    assert len(data["months"]) == 12
    assert Decimal(data["total_income"]) == 0
    assert Decimal(data["total_expense"]) == 0

    for m in data["months"]:
        assert Decimal(m["income_actual"]) == 0
        assert Decimal(m["expense_actual"]) == 0
        assert Decimal(m["income_forecast"]) == 0
        assert Decimal(m["expense_forecast"]) == 0


# ─── Gerçekleşen gelir/gider ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_actual_income_appears_in_correct_month(client: AsyncClient):
    """Mart 2026'da 5000 TL gelir → months[2].income_actual == 5000."""
    session = await _make_user(client, "cf_income_mar@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        db.add(Income(
            user_id=user_id,
            amount=Decimal("5000.00"),
            date=date(2026, 3, 15),
            category="salary",
            description="test",
        ))
        await db.commit()

    resp = await client.get("/api/v1/cash-flow?year=2026", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]

    # months[0] = Ocak, months[2] = Mart
    assert Decimal(months[2]["income_actual"]) == Decimal("5000.00")
    for i, m in enumerate(months):
        if i != 2:
            assert Decimal(m["income_actual"]) == 0


@pytest.mark.asyncio
async def test_cash_flow_simple_expense_appears(client: AsyncClient):
    """Mayıs 2026'da 2 expense → toplamı doğru ay'da."""
    session = await _make_user(client, "cf_simple_expense@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        # Her iki expense de credit_card_id=None ve is_paid=False → çift sayım
        # filtresi DAHİL (credit_card_id IS NULL OR is_paid=False)
        db.add(Expense(
            user_id=user_id, amount=Decimal("100.00"),
            date=date(2026, 5, 5), category="other", description="market",
            is_paid=False,
        ))
        db.add(Expense(
            user_id=user_id, amount=Decimal("250.50"),
            date=date(2026, 5, 20), category="other", description="benzin",
            is_paid=False,
        ))
        await db.commit()

    resp = await client.get("/api/v1/cash-flow?year=2026", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]

    # months[4] = Mayıs
    assert Decimal(months[4]["expense_actual"]) == Decimal("350.50")


# ─── IDOR korunumu ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_idor_user_isolation(client: AsyncClient):
    """User A'nın income'u User B'nin cash-flow'unda görünmemeli."""
    session_a = await _make_user(client, "cf_idor_a@example.com")
    session_b = await _make_user(client, "cf_idor_b@example.com")
    a_id = await _get_user_id(session_a["email"])

    async with TestSession() as db:
        db.add(Income(
            user_id=a_id, amount=Decimal("99999.00"),
            date=date(2026, 1, 10), category="salary", description="a",
        ))
        await db.commit()

    # B'nin cash-flow'u sıfır olmalı
    resp = await client.get("/api/v1/cash-flow?year=2026", headers=session_b["headers"])
    assert resp.status_code == 200
    for m in resp.json()["months"]:
        assert Decimal(m["income_actual"]) == 0


# ─── Recurring income projection ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_recurring_income_projects_into_future_months(client: AsyncClient):
    """Aylık recurring income gelecek aylarda income_forecast > 0 olmalı."""
    session = await _make_user(client, "cf_recurring@example.com")
    user_id = await _get_user_id(session["email"])
    today = datetime.now().date()

    async with TestSession() as db:
        db.add(RecurringIncome(
            user_id=user_id,
            title="Maaş",
            amount=Decimal("3000.00"),
            category="salary",
            recurrence="monthly",
            day_of_month=1,
            start_date=date(today.year - 1, 1, 1),
        ))
        await db.commit()

    resp = await client.get(
        f"/api/v1/cash-flow?year={today.year}", headers=session["headers"]
    )
    assert resp.status_code == 200
    months = resp.json()["months"]

    # Gelecek aylarda en az bir ay income_forecast == 3000 olmalı
    future_with_projection = [
        m for m in months
        if not m["is_past"] and Decimal(m["income_forecast"]) >= Decimal("3000.00")
    ]
    assert len(future_with_projection) >= 1, (
        f"Aylık recurring gelecek aylara projecte etmedi. months={months}"
    )


# ─── Net hesabı ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_net_equals_income_minus_expense(client: AsyncClient):
    """net = income_total - expense_total her ay için tutarlı olmalı."""
    session = await _make_user(client, "cf_net@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        db.add(Income(
            user_id=user_id, amount=Decimal("1000"),
            date=date(2026, 6, 1), category="other", description="x",
        ))
        db.add(Expense(
            user_id=user_id, amount=Decimal("400"),
            date=date(2026, 6, 1), category="other", description="y",
            is_paid=False,
        ))
        await db.commit()

    resp = await client.get("/api/v1/cash-flow?year=2026", headers=session["headers"])
    assert resp.status_code == 200
    haziran = resp.json()["months"][5]  # index 5 = Haziran

    income_total = Decimal(haziran["income_total"])
    expense_total = Decimal(haziran["expense_total"])
    net = Decimal(haziran["net"])

    assert net == income_total - expense_total
    assert income_total == Decimal("1000")
    assert expense_total == Decimal("400")
    assert net == Decimal("600")
