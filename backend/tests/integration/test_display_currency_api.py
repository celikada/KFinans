"""Görüntüleme para birimi (display) — endpoint entegrasyon testleri (Faz B).

Kapsam:
- USD kullanıcı USD görünüm → tam ``amount`` (çarpıtma yok).
- TRY görünüm → ``Σ amount_tl`` (mevcut davranış, regresyon yok).
- Çapraz (USD kayıt → EUR görünüm) → tarihsel cross.
- Forecast (recurring/budget) → güncel kur.
- cash_flow actual (tarihsel) / forecast (güncel) ayrımı.
- KK summary → güncel kur (cari/tahmin).

Tarihsel kur ``daily_rates``'e doğrudan seed edilir (TCMB'ye gidilmez). Güncel kur
``currency.fetch_rates`` monkeypatch ile sabitlenir.
"""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.daily_rate import DailyRate
from app.models.expense import Expense
from app.models.income import Income
from app.models.user import User
from tests.conftest import TestSession, make_user

# İşlem tarihi: 2026-01-15. O günkü tarihsel kur (seed): USD=30, EUR=33.
_TX_DATE = date(2026, 1, 15)
_HIST_USD = Decimal("30.000000")
_HIST_EUR = Decimal("33.000000")

# Güncel kur (forecast/cari yol): USD=40, EUR=44 (tarihselden FARKLI → ayrım ispatı).
_CUR_RATES = {"TRY": Decimal(1), "USD": Decimal("40"), "EUR": Decimal("44")}


async def _seed_historical() -> None:
    async with TestSession() as s:
        s.add(DailyRate(rate_date=_TX_DATE, currency="USD", rate_to_try=_HIST_USD))
        s.add(DailyRate(rate_date=_TX_DATE, currency="EUR", rate_to_try=_HIST_EUR))
        await s.commit()


async def _uid(s, email: str):
    return (await s.execute(select(User.id).where(User.email == email))).scalar_one()


async def _add_income(email: str, amount, currency: str, amount_tl, category="salary", on=_TX_DATE) -> None:
    """Gerçekleşmiş gelir kaydını doğrudan DB'ye yazar (write-path/amount_tl sabit)."""
    async with TestSession() as s:
        s.add(
            Income(
                user_id=await _uid(s, email),
                amount=Decimal(amount),
                currency=currency,
                amount_tl=Decimal(amount_tl),
                exchange_rate=Decimal("1"),
                category=category,
                date=on,
            )
        )
        await s.commit()


async def _add_expense(email: str, amount, currency: str, amount_tl, category="food", on=_TX_DATE) -> None:
    async with TestSession() as s:
        s.add(
            Expense(
                user_id=await _uid(s, email),
                amount=Decimal(amount),
                currency=currency,
                amount_tl=Decimal(amount_tl),
                exchange_rate=Decimal("1"),
                category=category,
                date=on,
                is_paid=False,
            )
        )
        await s.commit()


@pytest.fixture
def _patch_current_rates(monkeypatch):
    async def _fake_rates(*a, **k):
        return dict(_CUR_RATES)

    monkeypatch.setattr("app.services.currency.fetch_rates", _fake_rates)


# ── Gelir özeti ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_income_summary_try_default_unchanged(client: AsyncClient):
    """display verilmezse TRY (kullanıcı default) → total == Σ amount_tl (regresyon)."""
    email = "disp_inc_try@example.com"
    headers = await make_user(client, email)
    await _add_income(email, "100", "USD", "3000")  # amount_tl=3000
    resp = await client.get("/api/v1/income/summary?year=2026&month=1", headers=headers)
    body = resp.json()
    assert resp.status_code == 200
    assert Decimal(str(body["total"])) == Decimal("3000.00")
    assert Decimal(str(body["total_display"])) == Decimal("3000.00")  # TRY → _display == _tl
    assert body["display_currency"] == "TRY"


@pytest.mark.asyncio
async def test_income_summary_usd_view_returns_amount_exact(client: AsyncClient):
    """USD kayıt → USD görünüm → tam amount (c==d kısayolu, çarpıtma yok)."""
    email = "disp_inc_usd@example.com"
    headers = await make_user(client, email)
    await _add_income(email, "100", "USD", "3000")
    resp = await client.get("/api/v1/income/summary?year=2026&month=1&display=USD", headers=headers)
    body = resp.json()
    assert body["display_currency"] == "USD"
    assert Decimal(str(body["total_display"])) == Decimal("100.00")  # tam amount
    assert Decimal(str(body["total"])) == Decimal("3000.00")  # TL aynen


@pytest.mark.asyncio
async def test_income_summary_cross_historical(client: AsyncClient):
    """USD kayıt → EUR görünüm → tarihsel cross: 100 × histUSD(30) / histEUR(33)."""
    email = "disp_inc_cross@example.com"
    headers = await make_user(client, email)
    await _seed_historical()
    await _add_income(email, "100", "USD", "3000")
    resp = await client.get("/api/v1/income/summary?year=2026&month=1&display=EUR", headers=headers)
    body = resp.json()
    # 100 × 30 / 33 = 90.9090... → 90.91
    assert Decimal(str(body["total_display"])) == Decimal("90.91")
    assert Decimal(str(body["by_category"][0]["total_display"])) == Decimal("90.91")


# ── Gider özeti ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expense_summary_cross_historical(client: AsyncClient):
    email = "disp_exp_cross@example.com"
    headers = await make_user(client, email)
    await _seed_historical()
    await _add_expense(email, "100", "USD", "3000")
    resp = await client.get("/api/v1/expenses/summary?year=2026&month=1&display=EUR", headers=headers)
    body = resp.json()
    assert Decimal(str(body["total_display"])) == Decimal("90.91")


@pytest.mark.asyncio
async def test_expense_summary_try_unchanged(client: AsyncClient):
    email = "disp_exp_try@example.com"
    headers = await make_user(client, email)
    await _add_expense(email, "100", "USD", "3000")
    resp = await client.get("/api/v1/expenses/summary?year=2026&month=1", headers=headers)
    body = resp.json()
    assert Decimal(str(body["total"])) == Decimal("3000.00")
    assert Decimal(str(body["total_display"])) == Decimal("3000.00")


# ── Bütçe karşılaştırma (actual tarihsel + budget güncel) ─────────────────────


@pytest.mark.asyncio
async def test_budget_comparison_display(client: AsyncClient, _patch_current_rates):
    email = "disp_budget@example.com"
    headers = await make_user(client, email)
    await _seed_historical()
    await _add_expense(email, "100", "USD", "3000", category="food")
    # Bütçe: 200 EUR (güncel kur). EUR görünümde budget == 200 (c==d), actual cross.
    await client.put("/api/v1/budgets/food", json={"amount": 200, "currency": "EUR"}, headers=headers)
    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=1&display=EUR", headers=headers)
    rows = {r["category"]: r for r in resp.json()}
    food = rows["food"]
    assert food["display_currency"] == "EUR"
    # actual: 100 USD × 30 / 33 = 90.91 (tarihsel)
    assert Decimal(str(food["actual_amount_display"])) == Decimal("90.91")
    # budget: 200 EUR güncel → EUR görünümde 200 (c==d)
    assert Decimal(str(food["budget_amount_display"])) == Decimal("200.00")
    # remaining = 200 - 90.91 = 109.09
    assert Decimal(str(food["remaining_display"])) == Decimal("109.09")


# ── Income dashboard (actual tarihsel + recurring güncel) ─────────────────────


@pytest.mark.asyncio
async def test_income_dashboard_try_unchanged(client: AsyncClient):
    email = "disp_dash_try@example.com"
    headers = await make_user(client, email)
    await _add_income(email, "100", "USD", "3000")
    resp = await client.get("/api/v1/income/dashboard?year=2026&month=1", headers=headers)
    body = resp.json()
    assert Decimal(str(body["this_month_actual"])) == Decimal("3000.00")
    assert Decimal(str(body["this_month_actual_display"])) == Decimal("3000.00")
    assert body["display_currency"] == "TRY"


@pytest.mark.asyncio
async def test_income_dashboard_cross_actual_historical(client: AsyncClient, _patch_current_rates):
    email = "disp_dash_cross@example.com"
    headers = await make_user(client, email)
    await _seed_historical()
    await _add_income(email, "100", "USD", "3000")  # actual @ 2026-01-15
    resp = await client.get("/api/v1/income/dashboard?year=2026&month=1&display=EUR", headers=headers)
    body = resp.json()
    # actual cross tarihsel: 100 × 30/33 = 90.91
    assert Decimal(str(body["this_month_actual_display"])) == Decimal("90.91")


# ── Cash flow (actual tarihsel vs forecast güncel) ────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_try_unchanged(client: AsyncClient, _patch_current_rates):
    email = "disp_cf_try@example.com"
    headers = await make_user(client, email)
    await _add_income(email, "100", "USD", "3000", on=date(2026, 1, 15))
    resp = await client.get("/api/v1/cash-flow?year=2026", headers=headers)
    body = resp.json()
    jan = body["months"][0]
    assert Decimal(str(jan["income_total"])) == Decimal(str(jan["income_total_display"]))
    assert body["display_currency"] == "TRY"


@pytest.mark.asyncio
async def test_cash_flow_actual_cross_historical(client: AsyncClient, _patch_current_rates):
    email = "disp_cf_cross@example.com"
    headers = await make_user(client, email)
    await _seed_historical()
    await _add_income(email, "100", "USD", "3000", on=date(2026, 1, 15))
    resp = await client.get("/api/v1/cash-flow?year=2026&display=EUR", headers=headers)
    body = resp.json()
    jan = body["months"][0]
    # actual income tarihsel cross: 100 × 30/33 = 90.91
    assert Decimal(str(jan["income_total_display"])) == Decimal("90.91")


@pytest.mark.asyncio
async def test_cash_flow_detail_amount_display(client: AsyncClient, _patch_current_rates):
    email = "disp_cf_detail@example.com"
    headers = await make_user(client, email)
    await _seed_historical()
    await _add_income(email, "100", "USD", "3000", on=date(2026, 1, 15))
    resp = await client.get("/api/v1/cash-flow/2026/1/detail?display=EUR", headers=headers)
    body = resp.json()
    item = body["income_items"][0]
    # date'li (actual) kalem → tarihsel: 90.91
    assert Decimal(str(item["amount_display"])) == Decimal("90.91")
    assert body["display_currency"] == "EUR"


# ── Kredi kartı özeti (güncel kur — cari/tahmin) ──────────────────────────────


@pytest.mark.asyncio
async def test_credit_card_summary_display_current(client: AsyncClient, _patch_current_rates):
    email = "disp_cc@example.com"
    headers = await make_user(client, email)
    # USD kart, current_period_debt=100 → EUR görünümde güncel kur: 100×40/44 = 90.91
    await client.post(
        "/api/v1/credit-cards",
        json={"name": "Test", "current_period_debt": 100, "currency": "USD"},
        headers=headers,
    )
    resp = await client.get("/api/v1/credit-cards?display=EUR", headers=headers)
    body = resp.json()
    assert body["display_currency"] == "EUR"
    # period_debt = 100 USD; güncel 100×40/44 = 90.909 → 90.91
    assert Decimal(str(body["total_period_debt_display"])) == Decimal("90.91")
    card = body["cards"][0]
    assert Decimal(str(card["period_debt_display"])) == Decimal("90.91")
    # TL karşılığı: 100 × 40 = 4000
    assert Decimal(str(card["period_debt_tl"])) == Decimal("4000.00")
