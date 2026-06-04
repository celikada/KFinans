"""Faz 3 kredi sistemi — core/credits.py helper birim/entegrasyon testleri.

deduct_credits / add_credits gercek Postgres'te (SELECT FOR UPDATE) test edilir.
Helper'lar commit ETMEZ; test caller commit eder.
"""

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from app.core.credits import add_credits, deduct_credits
from app.models.credit_transaction import CreditTransaction
from app.models.user import User
from tests.conftest import TestSession, make_user


async def _user_id(email: str):
    async with TestSession() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one().id


async def _set_balance(email: str, balance: int) -> None:
    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        user.credit_balance = balance
        await session.commit()


async def _ledger_rows(user_id):
    async with TestSession() as session:
        return (await session.execute(select(CreditTransaction).where(CreditTransaction.user_id == user_id))).scalars().all()


@pytest.mark.asyncio
async def test_deduct_credits_happy_path(client: AsyncClient):
    """Bakiye 10, dus 3 -> bakiye 7, ledger'da amount=-3 tek satir."""
    email = "credit_deduct_ok@example.com"
    await make_user(client, email)
    await _set_balance(email, 10)
    uid = await _user_id(email)

    async with TestSession() as session:
        new_balance = await deduct_credits(session, user_id=uid, amount=3, reason="ai_advice_medium", reference_id="advice-1")
        assert new_balance == 7
        await session.commit()

    rows = await _ledger_rows(uid)
    assert len(rows) == 1
    assert rows[0].amount == -3
    assert rows[0].reason == "ai_advice_medium"
    assert rows[0].reference_id == "advice-1"


@pytest.mark.asyncio
async def test_deduct_credits_insufficient_balance(client: AsyncClient):
    """Bakiye 0 -> 402, ledger'a satir YOK, bakiye degismedi."""
    email = "credit_deduct_402@example.com"
    await make_user(client, email)
    await _set_balance(email, 0)
    uid = await _user_id(email)

    async with TestSession() as session:
        with pytest.raises(HTTPException) as exc:
            await deduct_credits(session, user_id=uid, amount=5, reason="ai_advice_medium")
        assert exc.value.status_code == 402
        await session.rollback()

    assert await _ledger_rows(uid) == []
    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one()
        assert (user.credit_balance or 0) == 0


@pytest.mark.asyncio
async def test_deduct_credits_rejects_non_positive(client: AsyncClient):
    """amount <= 0 -> ValueError (defansif)."""
    email = "credit_deduct_neg@example.com"
    await make_user(client, email)
    uid = await _user_id(email)
    async with TestSession() as session:
        with pytest.raises(ValueError):
            await deduct_credits(session, user_id=uid, amount=0, reason="x")


@pytest.mark.asyncio
async def test_add_credits_happy_path(client: AsyncClient):
    """+150 -> bakiye artar, ledger amount=+150."""
    email = "credit_add_ok@example.com"
    await make_user(client, email)
    await _set_balance(email, 0)
    uid = await _user_id(email)

    async with TestSession() as session:
        new_balance = await add_credits(session, user_id=uid, amount=150, reason="purchase", reference_id="iyz-1")
        assert new_balance == 150
        await session.commit()

    rows = await _ledger_rows(uid)
    assert len(rows) == 1
    assert rows[0].amount == 150
    assert rows[0].reason == "purchase"


@pytest.mark.asyncio
async def test_add_credits_idempotency(client: AsyncClient):
    """Ayni idempotency_key ile 2 kez -> ikinci no-op, bakiye 1 kez arttn, 1 satir."""
    email = "credit_add_idem@example.com"
    await make_user(client, email)
    await _set_balance(email, 0)
    uid = await _user_id(email)
    key = "conv-abc-123"

    async with TestSession() as session:
        b1 = await add_credits(session, user_id=uid, amount=50, reason="purchase", idempotency_key=key)
        await session.commit()
    assert b1 == 50

    async with TestSession() as session:
        b2 = await add_credits(session, user_id=uid, amount=50, reason="purchase", idempotency_key=key)
        await session.commit()
    # Ikinci cagri no-op: bakiye hala 50
    assert b2 == 50

    rows = await _ledger_rows(uid)
    assert len(rows) == 1
    assert rows[0].amount == 50
