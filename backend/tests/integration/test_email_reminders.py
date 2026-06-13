"""Ödeme hatırlatması e-postası: cron job + profil endpoint testleri.

- `_email_due_payments_job`: opt-in + email_verified + due ekstresi olan
  kullanıcıya e-posta gönderir; opt-in OFF / unverified / due olmayan atlanır.
- `PUT /user/profile`: `payment_reminder_email` günceller; `GET /user/me` döner.

Cron job fonksiyonu doğrudan çağrılır (APScheduler trigger lifespan'da kayıtlı).
send_payment_reminder_email mock'lanır (gerçek Resend çağrısı yok).
"""

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import bcrypt
import pytest

from app.models.credit_card import CreditCard, CreditCardStatement
from app.models.user import User
from app.scheduler import _DUE_SOON_DAYS, _ISTANBUL, _email_due_payments_job
from tests.conftest import TestSession, make_user


async def _make_user_in_db(
    *,
    payment_reminder_email: bool,
    email_verified: bool = True,
    deleted_at: datetime | None = None,
) -> User:
    random_hash = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt()).decode()
    user = User(
        id=uuid4(),
        email=f"remind_{uuid4().hex[:8]}@example.com",
        password_hash=random_hash,
        risk_profile="balanced",
        email_verified=email_verified,
        payment_reminder_email=payment_reminder_email,
        deleted_at=deleted_at,
    )
    async with TestSession() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def _add_due_statement(user_id, *, due_in_days: int) -> None:
    """Kullanıcıya ödenmemiş, ödemesi `due_in_days` gün sonra olan ekstre ekle."""
    # İş (_email_due_payments_job) days_until_due'yu İstanbul tarihiyle hesaplar;
    # test de aynı tabanı kullanmalı (UTC date.today() ile gün-sınırı off-by-one
    # → CI 21:00-24:00 UTC arası flaky'di). İstanbul tabanı deterministik.
    today = datetime.now(_ISTANBUL).date()
    async with TestSession() as session:
        card = CreditCard(
            user_id=user_id,
            name="Test Kart",
            currency="TRY",
            statement_day=1,
            payment_due_day=10,
        )
        session.add(card)
        await session.flush()
        stmt = CreditCardStatement(
            card_id=card.id,
            period_year=today.year,
            period_month=today.month,
            currency="TRY",
            statement_amount=Decimal("1500.00"),
            statement_date=today - timedelta(days=5),
            due_date=today + timedelta(days=due_in_days),
            paid_at=None,
        )
        session.add(stmt)
        await session.commit()


def _patch_sender(monkeypatch) -> dict:
    """send_payment_reminder_email'i mock'la; çağrı argümanlarını yakala."""
    import app.scheduler as scheduler_module

    sent: dict = {"calls": []}

    async def _fake_send(*, to: str, items: list[dict]) -> bool:
        sent["calls"].append({"to": to, "items": items})
        return True

    monkeypatch.setattr(scheduler_module, "send_payment_reminder_email", _fake_send)
    return sent


@pytest.mark.asyncio
async def test_email_sent_to_optin_verified_with_due(monkeypatch):
    """opt-in + verified + due ekstresi olan kullanıcıya e-posta gönderilir."""
    sent = _patch_sender(monkeypatch)
    user = await _make_user_in_db(payment_reminder_email=True)
    await _add_due_statement(user.id, due_in_days=2)

    await _email_due_payments_job(session_factory=TestSession)

    tos = [c["to"] for c in sent["calls"]]
    assert user.email in tos, "Opt-in verified due kullanıcıya mail gitmeliydi"
    call = next(c for c in sent["calls"] if c["to"] == user.email)
    assert len(call["items"]) == 1
    item = call["items"][0]
    assert item["card_name"] == "Test Kart"
    assert item["currency"] == "TRY"
    assert item["days_until_due"] == 2


@pytest.mark.asyncio
async def test_email_skipped_when_optin_off(monkeypatch):
    """payment_reminder_email=False kullanıcı atlanır."""
    sent = _patch_sender(monkeypatch)
    user = await _make_user_in_db(payment_reminder_email=False)
    await _add_due_statement(user.id, due_in_days=2)

    await _email_due_payments_job(session_factory=TestSession)

    tos = [c["to"] for c in sent["calls"]]
    assert user.email not in tos, "Opt-in kapalı kullanıcıya mail gitmemeliydi"


@pytest.mark.asyncio
async def test_email_skipped_when_unverified(monkeypatch):
    """email_verified=False kullanıcı atlanır."""
    sent = _patch_sender(monkeypatch)
    user = await _make_user_in_db(payment_reminder_email=True, email_verified=False)
    await _add_due_statement(user.id, due_in_days=2)

    await _email_due_payments_job(session_factory=TestSession)

    tos = [c["to"] for c in sent["calls"]]
    assert user.email not in tos, "Doğrulanmamış kullanıcıya mail gitmemeliydi"


@pytest.mark.asyncio
async def test_email_skipped_when_soft_deleted(monkeypatch):
    """deleted_at dolu (soft-delete) kullanıcı atlanır."""
    sent = _patch_sender(monkeypatch)
    user = await _make_user_in_db(
        payment_reminder_email=True,
        deleted_at=datetime.now(timezone.utc),
    )
    await _add_due_statement(user.id, due_in_days=2)

    await _email_due_payments_job(session_factory=TestSession)

    tos = [c["to"] for c in sent["calls"]]
    assert user.email not in tos, "Soft-delete kullanıcıya mail gitmemeliydi"


@pytest.mark.asyncio
async def test_email_skipped_when_no_due_statement(monkeypatch):
    """Ödemesi yaklaşan ekstresi olmayan opt-in kullanıcı atlanır."""
    sent = _patch_sender(monkeypatch)
    user = await _make_user_in_db(payment_reminder_email=True)
    # due_date çok ileride (_DUE_SOON_DAYS + 30) → eşik dışı
    await _add_due_statement(user.id, due_in_days=_DUE_SOON_DAYS + 30)

    await _email_due_payments_job(session_factory=TestSession)

    tos = [c["to"] for c in sent["calls"]]
    assert user.email not in tos, "Yaklaşan ödemesi olmayan kullanıcıya mail gitmemeliydi"


@pytest.mark.asyncio
async def test_email_includes_overdue_statement(monkeypatch):
    """Gecikmiş (due_date < bugün) ödenmemiş ekstre de hatırlatılır."""
    sent = _patch_sender(monkeypatch)
    user = await _make_user_in_db(payment_reminder_email=True)
    await _add_due_statement(user.id, due_in_days=-3)

    await _email_due_payments_job(session_factory=TestSession)

    call = next((c for c in sent["calls"] if c["to"] == user.email), None)
    assert call is not None, "Gecikmiş ekstre için mail gitmeliydi"
    assert call["items"][0]["days_until_due"] == -3


# ─── PUT /user/profile + GET /user/me ──────────────────────────────────


@pytest.mark.asyncio
async def test_profile_update_sets_payment_reminder_email(client):
    """PUT /user/profile payment_reminder_email günceller; /user/me döner."""
    headers = await make_user(client)

    # Varsayılan kapalı
    me = await client.get("/api/v1/user/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["payment_reminder_email"] is False

    # Aç
    resp = await client.put(
        "/api/v1/user/profile",
        headers=headers,
        json={"risk_profile": "balanced", "payment_reminder_email": True},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_reminder_email"] is True

    # /user/me güncel durumu döner
    me2 = await client.get("/api/v1/user/me", headers=headers)
    assert me2.json()["payment_reminder_email"] is True


@pytest.mark.asyncio
async def test_profile_update_omitting_field_preserves_value(client):
    """payload'da payment_reminder_email verilmezse mevcut değer korunur."""
    headers = await make_user(client)

    # Önce aç
    await client.put(
        "/api/v1/user/profile",
        headers=headers,
        json={"risk_profile": "balanced", "payment_reminder_email": True},
    )
    # Sonra alan göndermeden başka bir güncelleme
    resp = await client.put(
        "/api/v1/user/profile",
        headers=headers,
        json={"risk_profile": "aggressive"},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_reminder_email"] is True, "Alan verilmeyince korunmalıydı"
