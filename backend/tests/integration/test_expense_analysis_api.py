"""Faz 3: Harcama AI analizi endpoint testleri (POST /expenses/analysis/generate).

Test stratejisi (test_advice_credit_consumption.py + test_credits_api.py deseni):
- ExpenseAnalystService.analyze_expenses AsyncMock ile mock'lanir (gercek Anthropic yok).
- credit_balance + anthropic_consent manipulasyonu ile 403/402/basari/AI-fail/IDOR dogrulanir.
- credit_transactions ledger'inda amount=-3, reason="expense_analysis" satiri aranir.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from app.models.credit_transaction import CreditTransaction
from app.models.expense import Expense
from app.models.user import User
from tests.conftest import TestSession, make_user

_FAKE_ANALYSIS = "## Harcama Özeti\nTest analizi.\n\n⚠️ Bu içerik mali müşavirlik değildir."


async def _user(email: str) -> User:
    async with TestSession() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def _ledger(user_id):
    async with TestSession() as session:
        return (await session.execute(select(CreditTransaction).where(CreditTransaction.user_id == user_id))).scalars().all()


async def _set_credit_and_consent(email: str, balance: int, *, consent: bool = True) -> None:
    values: dict = {"credit_balance": balance}
    if consent:
        values["anthropic_consent_at"] = datetime.now(timezone.utc)
        values["anthropic_consent_version"] = "1.0"
    async with TestSession() as session:
        await session.execute(update(User).where(User.email == email).values(**values))
        await session.commit()


async def _add_expense(email: str, amount: str, category: str, d: date) -> None:
    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        session.add(Expense(user_id=user.id, amount=Decimal(amount), category=category, date=d, is_paid=False))
        await session.commit()


@pytest.fixture(autouse=True)
def _restore_anthropic_key():
    original = settings.anthropic_api_key
    settings.anthropic_api_key = "sk-ant-test"
    yield
    settings.anthropic_api_key = original


@pytest.mark.asyncio
async def test_analysis_403_without_consent(client: AsyncClient):
    """anthropic_consent yok -> 403 + Anthropic cagrilmaz."""
    email = "exp_analysis_no_consent@example.com"
    headers = await make_user(client, email)
    await _set_credit_and_consent(email, 10, consent=False)

    mock_analyze = AsyncMock()
    with patch("app.services.expense_analyst.ExpenseAnalystService.analyze_expenses", mock_analyze):
        resp = await client.post("/api/v1/expenses/analysis/generate", json={"months": 6}, headers=headers)
    assert resp.status_code == 403
    mock_analyze.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_402_when_insufficient_credit(client: AsyncClient):
    """credit_balance < 3 -> 402 + Anthropic cagrilmaz."""
    email = "exp_analysis_no_credit@example.com"
    headers = await make_user(client, email)
    await _set_credit_and_consent(email, 2)  # 3'ten az

    mock_analyze = AsyncMock()
    with patch("app.services.expense_analyst.ExpenseAnalystService.analyze_expenses", mock_analyze):
        resp = await client.post("/api/v1/expenses/analysis/generate", json={"months": 6}, headers=headers)
    assert resp.status_code == 402
    assert "kredi" in resp.json()["detail"].lower()
    mock_analyze.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_success_consumes_3_credits(client: AsyncClient):
    """Basari -> 201 + bakiye 3 dustu + ledger'da amount=-3 reason=expense_analysis 1 satir."""
    email = "exp_analysis_ok@example.com"
    headers = await make_user(client, email)
    await _set_credit_and_consent(email, 10)
    await _add_expense(email, "1500.00", "groceries", date.today())
    await _add_expense(email, "800.00", "transport", date.today())
    user = await _user(email)

    with patch(
        "app.services.expense_analyst.ExpenseAnalystService.analyze_expenses",
        AsyncMock(return_value=_FAKE_ANALYSIS),
    ):
        resp = await client.post("/api/v1/expenses/analysis/generate", json={"months": 6}, headers=headers)
    assert resp.status_code == 201

    body = resp.json()
    assert body["credits_used"] == 3
    assert body["analysis"] == _FAKE_ANALYSIS
    assert body["period"]["months"] == 6
    assert body["period"]["expense_count"] == 2

    # Bakiye 3 dustu
    user_after = await _user(email)
    assert user_after.credit_balance == 7

    # Ledger: tek satir, amount=-3, reason="expense_analysis"
    rows = await _ledger(user.id)
    assert len(rows) == 1
    assert rows[0].amount == -3
    assert rows[0].reason == "expense_analysis"


@pytest.mark.asyncio
async def test_analysis_ai_fail_no_credit_deduction(client: AsyncClient):
    """AI fail -> kredi dusmedi + ledger bos (deduct_credits cagrilmadan once exception)."""
    email = "exp_analysis_fail@example.com"
    headers = await make_user(client, email)
    await _set_credit_and_consent(email, 10)
    await _add_expense(email, "500.00", "food", date.today())
    user = await _user(email)

    with patch(
        "app.services.expense_analyst.ExpenseAnalystService.analyze_expenses",
        AsyncMock(side_effect=RuntimeError("AI patladi")),
    ):
        with pytest.raises(RuntimeError, match="AI patladi"):
            await client.post("/api/v1/expenses/analysis/generate", json={"months": 6}, headers=headers)

    user_after = await _user(email)
    assert user_after.credit_balance == 10  # dusmedi
    assert await _ledger(user.id) == []  # ledger bos


@pytest.mark.asyncio
async def test_analysis_idor(client: AsyncClient):
    """Kullanici B'nin analizi yalnizca kendi verisini kullanir + A'nin defterini etkilemez."""
    email_a = "exp_analysis_idor_a@example.com"
    email_b = "exp_analysis_idor_b@example.com"
    await make_user(client, email_a)
    headers_b = await make_user(client, email_b)
    await _set_credit_and_consent(email_a, 10)
    await _set_credit_and_consent(email_b, 10)
    # Sadece A'nin harcamasi var
    await _add_expense(email_a, "2000.00", "home", date.today())
    user_a = await _user(email_a)
    user_b = await _user(email_b)

    with patch(
        "app.services.expense_analyst.ExpenseAnalystService.analyze_expenses",
        AsyncMock(return_value=_FAKE_ANALYSIS),
    ):
        resp_b = await client.post("/api/v1/expenses/analysis/generate", json={"months": 6}, headers=headers_b)
    assert resp_b.status_code == 201
    # B'nin donemi A'nin harcamasini gormez (kendi verisi bos)
    assert resp_b.json()["period"]["expense_count"] == 0

    # A'nin bakiyesi/defteri etkilenmedi (B analiz yapti)
    assert (await _user(email_a)).credit_balance == 10
    assert await _ledger(user_a.id) == []
    # B'nin bakiyesi dustu
    assert (await _user(email_b)).credit_balance == 7
    assert len(await _ledger(user_b.id)) == 1
