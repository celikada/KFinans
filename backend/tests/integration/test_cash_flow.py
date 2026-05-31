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

from app.models.credit_card import CreditCard, CreditCardInstallment, CreditCardStatement
from app.models.expense import Expense
from app.models.income import Income
from app.models.planned_expense import PlannedExpense
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
        db.add(
            Income(
                user_id=user_id,
                amount=Decimal("5000.00"),
                date=date(2026, 3, 15),
                category="salary",
                description="test",
            )
        )
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
        db.add(
            Expense(
                user_id=user_id,
                amount=Decimal("100.00"),
                date=date(2026, 5, 5),
                category="other",
                description="market",
                is_paid=False,
            )
        )
        db.add(
            Expense(
                user_id=user_id,
                amount=Decimal("250.50"),
                date=date(2026, 5, 20),
                category="other",
                description="benzin",
                is_paid=False,
            )
        )
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
        db.add(
            Income(
                user_id=a_id,
                amount=Decimal("99999.00"),
                date=date(2026, 1, 10),
                category="salary",
                description="a",
            )
        )
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
        db.add(
            RecurringIncome(
                user_id=user_id,
                title="Maaş",
                amount=Decimal("3000.00"),
                category="salary",
                recurrence="monthly",
                day_of_month=1,
                start_date=date(today.year - 1, 1, 1),
            )
        )
        await db.commit()

    resp = await client.get(f"/api/v1/cash-flow?year={today.year}", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]

    # Gelecek aylarda en az bir ay income_forecast == 3000 olmalı
    future_with_projection = [m for m in months if not m["is_past"] and Decimal(m["income_forecast"]) >= Decimal("3000.00")]
    assert len(future_with_projection) >= 1, f"Aylık recurring gelecek aylara projecte etmedi. months={months}"


# ─── Net hesabı ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_net_equals_income_minus_expense(client: AsyncClient):
    """net = income_total - expense_total her ay için tutarlı olmalı."""
    session = await _make_user(client, "cf_net@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        db.add(
            Income(
                user_id=user_id,
                amount=Decimal("1000"),
                date=date(2026, 6, 1),
                category="other",
                description="x",
            )
        )
        db.add(
            Expense(
                user_id=user_id,
                amount=Decimal("400"),
                date=date(2026, 6, 1),
                category="other",
                description="y",
                is_paid=False,
            )
        )
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


# ─── Çift sayım filtresi (paid kart expense haric) ──────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_paid_card_expense_excluded_from_actual(client: AsyncClient):
    """credit_card_id NOT NULL + is_paid=True Expense actual gidere DAHIL DEGIL.

    Sebep: kart borcu/ekstresiyle zaten sayilir (cift sayim kurali).
    """
    session = await _make_user(client, "cf_paid_card_excl@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        card = CreditCard(user_id=user_id, name="DC")
        db.add(card)
        await db.flush()
        # Karttan odenmis -> haric
        db.add(
            Expense(
                user_id=user_id,
                amount=Decimal("1000.00"),
                date=date(2026, 4, 10),
                category="other",
                description="paid card",
                credit_card_id=card.id,
                is_paid=True,
            )
        )
        # Karttan odenmemis -> dahil
        db.add(
            Expense(
                user_id=user_id,
                amount=Decimal("150.00"),
                date=date(2026, 4, 11),
                category="other",
                description="unpaid card",
                credit_card_id=card.id,
                is_paid=False,
            )
        )
        await db.commit()

    resp = await client.get("/api/v1/cash-flow?year=2026", headers=session["headers"])
    assert resp.status_code == 200
    nisan = resp.json()["months"][3]  # index 3 = Nisan
    # Sadece 150 (odenmemis) gorunmeli, 1000 (odenmis kart) haric
    assert Decimal(nisan["expense_actual"]) == Decimal("150.00")


# ─── Kredi kartı ekstresi (due_date hangi aya denkse) ───────────────────────


@pytest.mark.asyncio
async def test_cash_flow_statement_due_date_counted_in_actual_expense(client: AsyncClient):
    """Kredi kartı ekstresi due_date'in ayında expense_actual'a eklenir."""
    session = await _make_user(client, "cf_statement@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        card = CreditCard(user_id=user_id, name="EkstreKart")
        db.add(card)
        await db.flush()
        db.add(
            CreditCardStatement(
                card_id=card.id,
                period_year=2026,
                period_month=2,
                statement_amount=Decimal("2500.00"),
                statement_date=date(2026, 2, 10),
                due_date=date(2026, 3, 5),  # Mart'a denk gelir
            )
        )
        await db.commit()

    resp = await client.get("/api/v1/cash-flow?year=2026", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]
    # due_date Mart (index 2) -> expense_actual += 2500
    assert Decimal(months[2]["expense_actual"]) == Decimal("2500.00")
    assert Decimal(months[1]["expense_actual"]) == 0  # Subat'ta degil


# ─── Kredi kartı taksitleri (gelecek aylar forecast) ────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_installment_appears_in_future_forecast(client: AsyncClient):
    """Taksit gelecek aylarda monthly_amount kadar expense_forecast olur."""
    session = await _make_user(client, "cf_installment@example.com")
    user_id = await _get_user_id(session["email"])
    today = datetime.now().date()

    async with TestSession() as db:
        card = CreditCard(user_id=user_id, name="TaksitKart")
        db.add(card)
        await db.flush()
        # Bu yilin Ocak'indan baslayan 12 taksit -> tum yil aktif
        db.add(
            CreditCardInstallment(
                card_id=card.id,
                description="Laptop 12 taksit",
                total_amount=Decimal("12000.00"),
                monthly_amount=Decimal("1000.00"),
                installments_total=12,
                installments_remaining=12,
                first_due_date=date(today.year, 1, 1),
            )
        )
        await db.commit()

    resp = await client.get(f"/api/v1/cash-flow?year={today.year}", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]
    # Gelecek aylarda (is_past=False) en az birinde expense_forecast >= 1000
    future = [m for m in months if not m["is_past"] and Decimal(m["expense_forecast"]) >= Decimal("1000.00")]
    assert len(future) >= 1, f"Taksit gelecek aya projecte etmedi. months={months}"


# ─── Planlı gider forecast ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_planned_expense_in_future_forecast(client: AsyncClient):
    """Aylık planlı gider gelecek aylarda expense_forecast > 0 olmalı."""
    session = await _make_user(client, "cf_planned@example.com")
    user_id = await _get_user_id(session["email"])
    today = datetime.now().date()

    async with TestSession() as db:
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="Kira",
                amount=Decimal("8000.00"),
                category="rent",
                recurrence="monthly",
                day_of_month=1,
                start_date=date(today.year - 1, 1, 1),
                is_paid=False,
            )
        )
        await db.commit()

    resp = await client.get(f"/api/v1/cash-flow?year={today.year}", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]
    future = [m for m in months if not m["is_past"] and Decimal(m["expense_forecast"]) >= Decimal("8000.00")]
    assert len(future) >= 1, f"Aylık planlı gider gelecek aya projecte etmedi. months={months}"


@pytest.mark.asyncio
async def test_cash_flow_paid_planned_expense_excluded_from_forecast(client: AsyncClient):
    """credit_card_id NOT NULL + is_paid=True planlı gider forecast'a girmez."""
    session = await _make_user(client, "cf_planned_paid@example.com")
    user_id = await _get_user_id(session["email"])
    today = datetime.now().date()

    async with TestSession() as db:
        card = CreditCard(user_id=user_id, name="PlanKart")
        db.add(card)
        await db.flush()
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="Odenmis plan",
                amount=Decimal("5000.00"),
                category="other",
                recurrence="monthly",
                day_of_month=1,
                start_date=date(today.year - 1, 1, 1),
                credit_card_id=card.id,
                is_paid=True,  # haric tutulmali
            )
        )
        await db.commit()

    resp = await client.get(f"/api/v1/cash-flow?year={today.year}", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]
    # Hicbir gelecek ayda 5000 forecast olmamali (filtrelendi)
    for m in months:
        assert Decimal(m["expense_forecast"]) < Decimal("5000.00")


# ─── is_past flag (geçmiş yıl tamamen past) ─────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_past_year_all_months_is_past(client: AsyncClient):
    """Geçmiş yıl (2020) tüm aylar is_past=True, forecast = 0."""
    session = await _make_user(client, "cf_past_year@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        # Gecmis yilda recurring olsa bile forecast 0 olmali (is_past)
        db.add(
            RecurringIncome(
                user_id=user_id,
                title="Maaş",
                amount=Decimal("9999.00"),
                category="salary",
                recurrence="monthly",
                day_of_month=1,
                start_date=date(2019, 1, 1),
            )
        )
        await db.commit()

    resp = await client.get("/api/v1/cash-flow?year=2020", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]
    for m in months:
        assert m["is_past"] is True
        assert Decimal(m["income_forecast"]) == 0
        assert Decimal(m["expense_forecast"]) == 0


@pytest.mark.asyncio
async def test_cash_flow_future_year_all_months_not_past(client: AsyncClient):
    """Gelecek yıl (2099) tüm aylar is_past=False."""
    session = await _make_user(client, "cf_future_year@example.com")
    resp = await client.get("/api/v1/cash-flow?year=2099", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]
    for m in months:
        assert m["is_past"] is False


# ─── Rapor indirme (Excel + PDF) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_xlsx_report_download(client: AsyncClient):
    """GET /cash-flow/report.xlsx -> Excel binary döner."""
    session = await _make_user(client, "cf_xlsx@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        db.add(
            Income(
                user_id=user_id,
                amount=Decimal("1234.00"),
                date=date(2026, 7, 1),
                category="salary",
                description="x",
            )
        )
        await db.commit()

    resp = await client.get("/api/v1/cash-flow/report.xlsx?year=2026", headers=session["headers"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "nakit-akis-2026.xlsx" in resp.headers["content-disposition"]
    # xlsx ZIP magic byte
    assert resp.content[:2] == b"PK"
    assert len(resp.content) > 100


@pytest.mark.asyncio
async def test_cash_flow_pdf_report_download(client: AsyncClient):
    """GET /cash-flow/report.pdf -> PDF binary döner."""
    session = await _make_user(client, "cf_pdf@example.com")
    resp = await client.get("/api/v1/cash-flow/report.pdf?year=2026", headers=session["headers"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "nakit-akis-2026.pdf" in resp.headers["content-disposition"]
    # PDF magic byte
    assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_cash_flow_xlsx_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/cash-flow/report.xlsx?year=2026")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cash_flow_pdf_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/cash-flow/report.pdf?year=2026")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cash_flow_report_year_validation(client: AsyncClient):
    """Rapor endpoint'leri de year range doğrular (422)."""
    session = await _make_user(client, "cf_report_badyear@example.com")
    bad_xlsx = await client.get("/api/v1/cash-flow/report.xlsx?year=1900", headers=session["headers"])
    assert bad_xlsx.status_code == 422
    bad_pdf = await client.get("/api/v1/cash-flow/report.pdf?year=3000", headers=session["headers"])
    assert bad_pdf.status_code == 422


# ─── Recurrence türleri (planned + recurring income) — forecast dalları ──────
# Bu helper'lar (_applies_planned_in_month / _applies_recurring_income_in_month)
# sadece GELECEK aylar (is_past=False) için çalışır. 2099 yılı tamamen gelecek.


@pytest.mark.asyncio
async def test_cash_flow_planned_recurrence_types_all_branches(client: AsyncClient):
    """planned_expense one_time/quarterly/biannual/yearly/custom + end_date dalları."""
    session = await _make_user(client, "cf_planned_rec@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        # one_time: sadece Mart 2099
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="OneTime",
                amount=Decimal("100"),
                category="other",
                recurrence="one_time",
                day_of_month=1,
                start_date=date(2099, 3, 1),
                is_paid=False,
            )
        )
        # quarterly: Ocak start -> Ocak, Nisan, Temmuz, Ekim
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="Quarterly",
                amount=Decimal("200"),
                category="other",
                recurrence="quarterly",
                day_of_month=1,
                start_date=date(2099, 1, 1),
                is_paid=False,
            )
        )
        # biannual: Ocak start -> Ocak, Temmuz
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="Biannual",
                amount=Decimal("300"),
                category="other",
                recurrence="biannual",
                day_of_month=1,
                start_date=date(2099, 1, 1),
                is_paid=False,
            )
        )
        # yearly: her yıl Mayıs
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="Yearly",
                amount=Decimal("400"),
                category="other",
                recurrence="yearly",
                day_of_month=1,
                start_date=date(2098, 5, 1),
                is_paid=False,
            )
        )
        # custom: Subat + Eylul
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="Custom",
                amount=Decimal("500"),
                category="other",
                recurrence="custom",
                months=[2, 9],
                day_of_month=1,
                start_date=date(2098, 1, 1),
                is_paid=False,
            )
        )
        # end_date gecmis -> hicbir ayda gorunmez (end_date < first_of_month dali)
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="Expired",
                amount=Decimal("9999"),
                category="other",
                recurrence="monthly",
                day_of_month=1,
                start_date=date(2098, 1, 1),
                end_date=date(2098, 12, 31),
                is_paid=False,
            )
        )
        await db.commit()

    resp = await client.get("/api/v1/cash-flow?year=2099", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]  # index 0=Ocak ... 11=Aralik

    # one_time Mart (idx 2)
    assert Decimal(months[2]["expense_forecast"]) >= Decimal("100")
    # quarterly Nisan (idx 3) — 200
    assert Decimal(months[3]["expense_forecast"]) >= Decimal("200")
    # biannual Temmuz (idx 6): biannual 300 + quarterly 200 (Temmuz quarterly de yakalar)
    assert Decimal(months[6]["expense_forecast"]) >= Decimal("300")
    # yearly Mayis (idx 4) — 400
    assert Decimal(months[4]["expense_forecast"]) >= Decimal("400")
    # custom Subat (idx 1) — 500, Eylul (idx 8) — 500
    assert Decimal(months[1]["expense_forecast"]) >= Decimal("500")
    assert Decimal(months[8]["expense_forecast"]) >= Decimal("500")
    # Expired hicbir ayda 9999 yok
    for m in months:
        assert Decimal(m["expense_forecast"]) < Decimal("9999")


@pytest.mark.asyncio
async def test_cash_flow_recurring_income_recurrence_types_all_branches(client: AsyncClient):
    """recurring_income one_time/quarterly/biannual/yearly/custom + end_date dalları."""
    session = await _make_user(client, "cf_recinc_rec@example.com")
    user_id = await _get_user_id(session["email"])

    async with TestSession() as db:
        db.add(
            RecurringIncome(
                user_id=user_id, title="OneTime", amount=Decimal("100"), category="other", recurrence="one_time", day_of_month=1, start_date=date(2099, 3, 1)
            )
        )
        db.add(
            RecurringIncome(
                user_id=user_id, title="Quarterly", amount=Decimal("200"), category="other", recurrence="quarterly", day_of_month=1, start_date=date(2099, 1, 1)
            )
        )
        db.add(
            RecurringIncome(
                user_id=user_id, title="Biannual", amount=Decimal("300"), category="other", recurrence="biannual", day_of_month=1, start_date=date(2099, 1, 1)
            )
        )
        db.add(
            RecurringIncome(
                user_id=user_id, title="Yearly", amount=Decimal("400"), category="other", recurrence="yearly", day_of_month=1, start_date=date(2098, 5, 1)
            )
        )
        db.add(
            RecurringIncome(
                user_id=user_id,
                title="Custom",
                amount=Decimal("500"),
                category="other",
                recurrence="custom",
                months=[2, 9],
                day_of_month=1,
                start_date=date(2098, 1, 1),
            )
        )
        db.add(
            RecurringIncome(
                user_id=user_id,
                title="Expired",
                amount=Decimal("9999"),
                category="other",
                recurrence="monthly",
                day_of_month=1,
                start_date=date(2098, 1, 1),
                end_date=date(2098, 12, 31),
            )
        )
        await db.commit()

    resp = await client.get("/api/v1/cash-flow?year=2099", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]

    assert Decimal(months[2]["income_forecast"]) >= Decimal("100")  # one_time Mart
    assert Decimal(months[3]["income_forecast"]) >= Decimal("200")  # quarterly Nisan
    assert Decimal(months[6]["income_forecast"]) >= Decimal("300")  # biannual Temmuz
    assert Decimal(months[4]["income_forecast"]) >= Decimal("400")  # yearly Mayis
    assert Decimal(months[1]["income_forecast"]) >= Decimal("500")  # custom Subat
    assert Decimal(months[8]["income_forecast"]) >= Decimal("500")  # custom Eylul
    for m in months:
        assert Decimal(m["income_forecast"]) < Decimal("9999")  # Expired yok


@pytest.mark.asyncio
async def test_cash_flow_planned_starts_after_year_not_shown(client: AsyncClient):
    """start_date sorgulanan yıldan sonra ise hiçbir ayda görünmez (start_date > last_of_month)."""
    session = await _make_user(client, "cf_planned_future_start@example.com")
    user_id = await _get_user_id(session["email"])
    async with TestSession() as db:
        db.add(
            PlannedExpense(
                user_id=user_id,
                title="Gelecek",
                amount=Decimal("777"),
                category="other",
                recurrence="monthly",
                day_of_month=1,
                start_date=date(2100, 1, 1),
                is_paid=False,
            )
        )
        await db.commit()
    resp = await client.get("/api/v1/cash-flow?year=2099", headers=session["headers"])
    assert resp.status_code == 200
    for m in resp.json()["months"]:
        assert Decimal(m["expense_forecast"]) < Decimal("777")


@pytest.mark.asyncio
async def test_cash_flow_installment_wraps_year_boundary(client: AsyncClient):
    """first_due Kasım 2098 + 6 taksit -> 2099 Ocak-Nisan'a sarkar (year wrap dalı)."""
    session = await _make_user(client, "cf_inst_wrap@example.com")
    user_id = await _get_user_id(session["email"])
    async with TestSession() as db:
        card = CreditCard(user_id=user_id, name="WrapKart")
        db.add(card)
        await db.flush()
        # Kasim 2098 (11) + 6 taksit: 11,12 (2098), 1,2,3,4 (2099) -> Nisan 2099'a kadar
        db.add(
            CreditCardInstallment(
                card_id=card.id,
                description="Wrap",
                total_amount=Decimal("600"),
                monthly_amount=Decimal("100"),
                installments_total=6,
                installments_remaining=6,
                first_due_date=date(2098, 11, 1),
            )
        )
        await db.commit()
    resp = await client.get("/api/v1/cash-flow?year=2099", headers=session["headers"])
    assert resp.status_code == 200
    months = resp.json()["months"]
    # 2099 Ocak-Nisan (idx 0-3) taksit 100 var, Mayis (idx 4) yok
    assert Decimal(months[0]["expense_forecast"]) >= Decimal("100")  # Ocak
    assert Decimal(months[3]["expense_forecast"]) >= Decimal("100")  # Nisan
    assert Decimal(months[4]["expense_forecast"]) < Decimal("100")  # Mayis: taksit bitti
