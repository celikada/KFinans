"""AI-007 (FAZ H): Kredi tuketim mantigi — credits_used kolonu kullaniliyor.

Test stratejisi:
- Anthropic SDK mock'lanir (advisor.AdvisorService.generate AsyncMock).
- Snapshot fixture ile DB'de portfoy_snapshot olusturulur.
- credit_balance manipulasyonlari ile 402, basarili, atomik dusum dogrulanir.
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from app.models.advice import InvestmentAdvice
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from tests.conftest import TestSession, make_user


def _fake_advice(user_id, snapshot_id):
    """advisor.generate() doneni: gercek InvestmentAdvice (DB'ye eklenebilir)."""
    return InvestmentAdvice(
        user_id=user_id,
        snapshot_id=snapshot_id,
        horizon="medium",
        content="Test tavsiye",
        prompt_tokens=120,
        completion_tokens=80,
    )


async def _create_snapshot_for(email: str) -> uuid.UUID:
    """Test user'a iliskin snapshot olustur. Returns snapshot_id."""
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


async def _set_credit_balance(email: str, balance: int) -> None:
    """credit_balance + Anthropic consent set (AI-005 gate gecsin)."""
    from datetime import datetime, timezone

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


async def _get_user(email: str) -> User:
    async with TestSession() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()


@pytest.fixture(autouse=True)
def _restore_anthropic_key():
    original = settings.anthropic_api_key
    settings.anthropic_api_key = "sk-ant-test"
    yield
    settings.anthropic_api_key = original


@pytest.mark.asyncio
async def test_generate_advice_402_when_insufficient_credit(client: AsyncClient):
    """credit_balance=0 ise 402 Payment Required + Anthropic cagrilmaz."""
    email = "advice_no_credit@example.com"
    headers = await make_user(client, email)
    await _create_snapshot_for(email)
    await _set_credit_balance(email, 0)

    mock_generate = AsyncMock()  # cagriliarsa fail eder, beklenmiyor
    with patch("app.services.advisor.AdvisorService.generate", mock_generate):
        resp = await client.post(
            "/api/v1/advice/generate",
            json={"horizon": "medium"},
            headers=headers,
        )
    assert resp.status_code == 402
    assert "kredi" in resp.json()["detail"].lower()
    mock_generate.assert_not_called()


@pytest.mark.asyncio
async def test_generate_advice_consumes_credit(client: AsyncClient):
    """Basarili uretim credit_balance'i 1 dusurur, advice.credits_used=1."""
    email = "advice_with_credit@example.com"
    headers = await make_user(client, email)
    snap_id = await _create_snapshot_for(email)
    await _set_credit_balance(email, 5)

    user_before = await _get_user(email)
    fake = _fake_advice(user_before.id, snap_id)

    with patch("app.services.advisor.AdvisorService.generate", AsyncMock(return_value=fake)):
        resp = await client.post(
            "/api/v1/advice/generate",
            json={"horizon": "medium"},
            headers=headers,
        )
    assert resp.status_code == 201

    # Credit dusuruldu
    user_after = await _get_user(email)
    assert user_after.credit_balance == 4

    # advice.credits_used yazildi
    async with TestSession() as session:
        advice_db = (await session.execute(select(InvestmentAdvice).where(InvestmentAdvice.user_id == user_before.id))).scalar_one()
        assert advice_db.credits_used == 1


@pytest.mark.asyncio
async def test_generate_advice_404_when_no_snapshot(client: AsyncClient):
    """Snapshot yokken 404 — kredi dusumu yapilmaz."""
    email = "advice_no_snap@example.com"
    headers = await make_user(client, email)
    await _set_credit_balance(email, 5)
    # Snapshot olusturmuyoruz

    mock_generate = AsyncMock()
    with patch("app.services.advisor.AdvisorService.generate", mock_generate):
        resp = await client.post(
            "/api/v1/advice/generate",
            json={"horizon": "medium"},
            headers=headers,
        )
    assert resp.status_code == 404
    mock_generate.assert_not_called()

    # Credit balance degismedi (snapshot kontrolu credit kontrolu sonrasi yapilir
    # ama LLM cagirilmadi -> dusum sadece basarili uretim sonrasi)
    user_after = await _get_user(email)
    assert user_after.credit_balance == 5
