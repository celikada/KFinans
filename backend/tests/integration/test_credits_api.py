"""Faz 3 kredi sistemi — GET /credits endpoint + advice ledger entegrasyonu.

- GET /credits: bakiye + sayfalanan defter, IDOR korumasi.
- advice refactor regresyonu: basarili tavsiye -> ledger'da amount=-1 satir;
  AI fail -> kredi dusmedi + ledger bos.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from app.models.advice import InvestmentAdvice
from app.models.credit_transaction import CreditTransaction
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from tests.conftest import TestSession, make_user


async def _user(email: str) -> User:
    async with TestSession() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def _ledger(user_id):
    async with TestSession() as session:
        return (await session.execute(select(CreditTransaction).where(CreditTransaction.user_id == user_id))).scalars().all()


async def _set_credit_and_consent(email: str, balance: int) -> None:
    async with TestSession() as session:
        await session.execute(
            update(User)
            .where(User.email == email)
            .values(
                credit_balance=balance,
                anthropic_consent_at=datetime.now(timezone.utc),
                anthropic_consent_version="1.0",
            )
        )
        await session.commit()


async def _create_snapshot_for(email: str) -> uuid.UUID:
    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        snap = PortfolioSnapshot(user_id=user.id, snapshot_date=date.today(), total_value_tl=Decimal("10000.00"))
        session.add(snap)
        await session.commit()
        return snap.id


def _fake_advice(user_id, snapshot_id):
    return InvestmentAdvice(
        user_id=user_id,
        snapshot_id=snapshot_id,
        horizon="medium",
        content="Test tavsiye",
        prompt_tokens=120,
        completion_tokens=80,
    )


@pytest.fixture(autouse=True)
def _restore_anthropic_key():
    original = settings.anthropic_api_key
    settings.anthropic_api_key = "sk-ant-test"
    yield
    settings.anthropic_api_key = original


@pytest.mark.asyncio
async def test_get_credits_empty(client: AsyncClient):
    """Yeni kullanici: balance=0, bos defter."""
    email = "credits_empty@example.com"
    headers = await make_user(client, email)

    resp = await client.get("/api/v1/credits", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] == 0
    assert body["transactions"]["items"] == []
    assert body["transactions"]["total_count"] == 0
    assert body["transactions"]["has_next"] is False


@pytest.mark.asyncio
async def test_get_credits_reflects_advice_consumption(client: AsyncClient):
    """Tavsiye uretildikten sonra GET /credits defterde -1 satir gosterir."""
    email = "credits_after_advice@example.com"
    headers = await make_user(client, email)
    snap_id = await _create_snapshot_for(email)
    await _set_credit_and_consent(email, 5)
    user = await _user(email)

    with patch(
        "app.services.advisor.AdvisorService.generate",
        AsyncMock(return_value=_fake_advice(user.id, snap_id)),
    ):
        resp = await client.post("/api/v1/advice/generate", json={"horizon": "medium"}, headers=headers)
    assert resp.status_code == 201

    # Ledger'da -1 satir + reference_id = advice.id
    rows = await _ledger(user.id)
    assert len(rows) == 1
    assert rows[0].amount == -1
    assert rows[0].reason == "ai_advice_medium"
    assert rows[0].reference_id is not None

    # GET /credits
    resp = await client.get("/api/v1/credits", headers=headers)
    body = resp.json()
    assert body["balance"] == 4
    assert body["transactions"]["total_count"] == 1
    assert body["transactions"]["items"][0]["amount"] == -1


@pytest.mark.asyncio
async def test_advice_fail_no_credit_deduction_no_ledger(client: AsyncClient):
    """AI fail -> kredi dusmedi + ledger bos (kritik regresyon garantisi)."""
    email = "credits_advice_fail@example.com"
    headers = await make_user(client, email)
    await _create_snapshot_for(email)
    await _set_credit_and_consent(email, 5)
    user = await _user(email)

    # advisor.generate exception'i deduct_credits'ten ONCE firlar; get_db rollback
    # eder. Test transport'u (raise_app_exceptions=True) exception'i yukseltir —
    # production'da generic Exception handler 500 doner. Kritik garanti: kredi
    # dusmedi + ledger'a satir yazilmadi.
    with patch(
        "app.services.advisor.AdvisorService.generate",
        AsyncMock(side_effect=RuntimeError("AI patladi")),
    ):
        with pytest.raises(RuntimeError, match="AI patladi"):
            await client.post("/api/v1/advice/generate", json={"horizon": "medium"}, headers=headers)

    user_after = await _user(email)
    assert user_after.credit_balance == 5  # dusmedi
    assert await _ledger(user.id) == []  # ledger bos


@pytest.mark.asyncio
async def test_get_credits_idor(client: AsyncClient):
    """Kullanici yalnizca kendi defterini gorur."""
    email_a = "credits_idor_a@example.com"
    email_b = "credits_idor_b@example.com"
    headers_a = await make_user(client, email_a)
    headers_b = await make_user(client, email_b)
    snap_id = await _create_snapshot_for(email_a)
    await _set_credit_and_consent(email_a, 5)
    user_a = await _user(email_a)

    with patch(
        "app.services.advisor.AdvisorService.generate",
        AsyncMock(return_value=_fake_advice(user_a.id, snap_id)),
    ):
        await client.post("/api/v1/advice/generate", json={"horizon": "medium"}, headers=headers_a)

    # B kullanicisi A'nin defterini gormez
    resp_b = await client.get("/api/v1/credits", headers=headers_b)
    assert resp_b.json()["transactions"]["total_count"] == 0
    # A kendi defterini gorur
    resp_a = await client.get("/api/v1/credits", headers=headers_a)
    assert resp_a.json()["transactions"]["total_count"] == 1
