"""AI-005 (FAZ H): Anthropic ozel acik riza testleri (KVKK m.9).

POST/DELETE /user/anthropic-consent + /advice/generate gate.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from app.models.advice import InvestmentAdvice
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from tests.conftest import TestSession, make_user


@pytest.fixture(autouse=True)
def _restore_anthropic_key():
    original = settings.anthropic_api_key
    settings.anthropic_api_key = "sk-ant-test"
    yield
    settings.anthropic_api_key = original


async def _set_credit(email: str, balance: int) -> None:
    async with TestSession() as session:
        await session.execute(
            update(User).where(User.email == email).values(credit_balance=balance)
        )
        await session.commit()


async def _create_snapshot(email: str) -> uuid.UUID:
    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        snap = PortfolioSnapshot(
            user_id=user.id,
            snapshot_date=date.today(),
            total_value_tl=Decimal("10000.00"),
        )
        session.add(snap)
        await session.commit()
        return snap.id


# ─── /user/anthropic-consent endpoint'leri ─────────────────────────────


@pytest.mark.asyncio
async def test_grant_anthropic_consent_sets_timestamp(client: AsyncClient):
    email = "ant_grant@example.com"
    headers = await make_user(client, email)

    resp = await client.post("/api/v1/user/anthropic-consent", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "1.0"
    assert "consent_at" in body

    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        assert user.anthropic_consent_at is not None
        assert user.anthropic_consent_version == "1.0"


@pytest.mark.asyncio
async def test_revoke_anthropic_consent_clears_timestamp(client: AsyncClient):
    email = "ant_revoke@example.com"
    headers = await make_user(client, email)

    # Once grant et
    await client.post("/api/v1/user/anthropic-consent", headers=headers)
    # Sonra revoke
    resp = await client.delete("/api/v1/user/anthropic-consent", headers=headers)
    assert resp.status_code == 200

    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        assert user.anthropic_consent_at is None
        assert user.anthropic_consent_version is None


@pytest.mark.asyncio
async def test_revoke_consent_when_not_present_returns_200(client: AsyncClient):
    """Riza yokken revoke -> 200 (idempotent), 'zaten mevcut degil' mesaj."""
    headers = await make_user(client, "ant_no_revoke@example.com")
    resp = await client.delete("/api/v1/user/anthropic-consent", headers=headers)
    assert resp.status_code == 200
    assert "mevcut degil" in resp.json()["detail"].lower()


# ─── /advice/generate gate ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_advice_generate_403_without_anthropic_consent(client: AsyncClient):
    """Anthropic rizasi yokken /advice/generate -> 403 (KVKK m.9 ihlali engeli)."""
    email = "ant_gate@example.com"
    headers = await make_user(client, email)
    await _create_snapshot(email)
    await _set_credit(email, 10)
    # Rıza VERMEDIK

    mock_generate = AsyncMock()
    with patch("app.services.advisor.AdvisorService.generate", mock_generate):
        resp = await client.post(
            "/api/v1/advice/generate",
            json={"horizon": "medium"},
            headers=headers,
        )
    assert resp.status_code == 403
    detail = resp.json()["detail"].lower()
    assert "anthropic" in detail or "riza" in detail
    mock_generate.assert_not_called()


@pytest.mark.asyncio
async def test_advice_generate_works_with_consent(client: AsyncClient):
    """Rıza verildikten sonra /advice/generate (mevcut credit varsa) basarili."""
    email = "ant_works@example.com"
    headers = await make_user(client, email)
    snap_id = await _create_snapshot(email)
    await _set_credit(email, 10)

    # Rıza ver
    grant = await client.post("/api/v1/user/anthropic-consent", headers=headers)
    assert grant.status_code == 200

    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
    fake = InvestmentAdvice(
        user_id=user.id,
        snapshot_id=snap_id,
        horizon="medium",
        content="Test",
        prompt_tokens=10, completion_tokens=10,
    )

    with patch("app.services.advisor.AdvisorService.generate", AsyncMock(return_value=fake)):
        resp = await client.post(
            "/api/v1/advice/generate",
            json={"horizon": "medium"},
            headers=headers,
        )
    assert resp.status_code == 201
