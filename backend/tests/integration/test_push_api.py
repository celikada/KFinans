"""Web Push endpoint'leri (/api/v1/push) + DB'ye dokunan servis + cron testleri.

Kontrat:
- GET  /push/vapid-public-key → {public_key}
- POST /push/subscribe        → 201, (user, endpoint) UPSERT idempotent
- POST /push/unsubscribe      → 204, sadece kendi aboneliği (IDOR-safe)
- POST /push/test             → tüm aboneliklere gönderir, {sent}
"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from pywebpush import WebPushException
from sqlalchemy import select

from app.models.credit_card import CreditCard, CreditCardStatement
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.services import push as push_service
from tests.conftest import TestSession, make_user

_SUB = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
    "keys": {"p256dh": "BNcRoyANB...", "auth": "tBHIt...="},
    "user_agent": "Mozilla/5.0 Test",
}


def _settings(public="pub", private="priv"):
    return SimpleNamespace(vapid_public_key=public, vapid_private_key=private, vapid_subject="mailto:t@e.com")


# ─── vapid-public-key ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vapid_public_key_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/push/vapid-public-key")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_vapid_public_key_returns_key(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.api.v1.push.settings", _settings(public="PUBKEY"))
    headers = await make_user(client, "vapid@example.com")
    resp = await client.get("/api/v1/push/vapid-public-key", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"public_key": "PUBKEY"}


# ─── subscribe ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_creates(client: AsyncClient):
    headers = await make_user(client, "sub_create@example.com")
    resp = await client.post("/api/v1/push/subscribe", json=_SUB, headers=headers)
    assert resp.status_code == 201, resp.text

    async with TestSession() as s:
        rows = (await s.execute(select(PushSubscription))).scalars().all()
        assert len(rows) == 1
        assert rows[0].endpoint == _SUB["endpoint"]
        assert rows[0].p256dh == _SUB["keys"]["p256dh"]
        assert rows[0].user_agent == "Mozilla/5.0 Test"


@pytest.mark.asyncio
async def test_subscribe_idempotent_upsert(client: AsyncClient):
    headers = await make_user(client, "sub_upsert@example.com")
    await client.post("/api/v1/push/subscribe", json=_SUB, headers=headers)
    # Aynı endpoint, farklı keys → güncelle (yeni satır oluşturma)
    updated = {**_SUB, "keys": {"p256dh": "NEWp256", "auth": "NEWauth"}, "user_agent": "Chrome"}
    resp = await client.post("/api/v1/push/subscribe", json=updated, headers=headers)
    assert resp.status_code == 201

    async with TestSession() as s:
        rows = (await s.execute(select(PushSubscription))).scalars().all()
        assert len(rows) == 1  # tek kayıt
        assert rows[0].p256dh == "NEWp256"
        assert rows[0].user_agent == "Chrome"


@pytest.mark.asyncio
async def test_subscribe_invalid_endpoint_422(client: AsyncClient):
    headers = await make_user(client, "sub_bad@example.com")
    bad = {**_SUB, "endpoint": "not-a-url"}
    resp = await client.post("/api/v1/push/subscribe", json=bad, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_subscribe_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/push/subscribe", json=_SUB)
    assert resp.status_code == 401


# ─── unsubscribe ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unsubscribe_deletes_own(client: AsyncClient):
    headers = await make_user(client, "unsub@example.com")
    await client.post("/api/v1/push/subscribe", json=_SUB, headers=headers)
    resp = await client.post("/api/v1/push/unsubscribe", json={"endpoint": _SUB["endpoint"]}, headers=headers)
    assert resp.status_code == 204

    async with TestSession() as s:
        rows = (await s.execute(select(PushSubscription))).scalars().all()
        assert rows == []


@pytest.mark.asyncio
async def test_unsubscribe_idor_cannot_delete_other(client: AsyncClient):
    owner = await make_user(client, "unsub_owner@example.com")
    await client.post("/api/v1/push/subscribe", json=_SUB, headers=owner)

    attacker = await make_user(client, "unsub_attacker@example.com")
    resp = await client.post("/api/v1/push/unsubscribe", json={"endpoint": _SUB["endpoint"]}, headers=attacker)
    # IDOR-safe: attacker'ın eşleşen aboneliği yok → 204 (no-op) ama owner'ınki silinmez
    assert resp.status_code == 204
    async with TestSession() as s:
        rows = (await s.execute(select(PushSubscription))).scalars().all()
        assert len(rows) == 1  # owner'ınki duruyor


# ─── test endpoint ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_test_endpoint_sends_to_all(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.api.v1.push.settings", _settings())
    monkeypatch.setattr("app.services.push.settings", _settings())
    calls = []
    monkeypatch.setattr(push_service, "webpush", lambda **kw: calls.append(kw))

    headers = await make_user(client, "test_ep@example.com")
    await client.post("/api/v1/push/subscribe", json=_SUB, headers=headers)
    sub2 = {**_SUB, "endpoint": "https://fcm.googleapis.com/fcm/send/second"}
    await client.post("/api/v1/push/subscribe", json=sub2, headers=headers)

    resp = await client.post("/api/v1/push/test", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"sent": 2}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_test_endpoint_noop_without_vapid(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.services.push.settings", _settings(public="", private=""))
    headers = await make_user(client, "test_noop@example.com")
    await client.post("/api/v1/push/subscribe", json=_SUB, headers=headers)
    resp = await client.post("/api/v1/push/test", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"sent": 0}


# ─── send_to_user (DB'ye dokunan servis) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_send_to_user_counts_and_deletes_expired(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "s2u@example.com")
    await client.post("/api/v1/push/subscribe", json=_SUB, headers=headers)
    gone = {**_SUB, "endpoint": "https://fcm.googleapis.com/fcm/send/gone"}
    await client.post("/api/v1/push/subscribe", json=gone, headers=headers)

    def _fake_webpush(**kw):
        if kw["subscription_info"]["endpoint"].endswith("/gone"):
            exc = WebPushException("gone")
            exc.response = SimpleNamespace(status_code=410)
            raise exc

    monkeypatch.setattr(push_service, "webpush", _fake_webpush)

    async with TestSession() as s:
        user = (await s.execute(select(User).where(User.email == "s2u@example.com"))).scalar_one()
        sent = await push_service.send_to_user(s, user.id, title="T", body="B", url="/x", app_settings=_settings())
        assert sent == 1
        rows = (await s.execute(select(PushSubscription))).scalars().all()
        assert {r.endpoint for r in rows} == {_SUB["endpoint"]}  # gone silindi


# ─── cron job ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_push_due_payments_job_sends(client: AsyncClient, monkeypatch):
    """Aboneliği + yaklaşan ödenmemiş ekstresi olan kullanıcıya bildirim gider."""
    from app import scheduler

    headers = await make_user(client, "cron_due@example.com")
    await client.post("/api/v1/push/subscribe", json=_SUB, headers=headers)

    today = date.today()
    async with TestSession() as s:
        user = (await s.execute(select(User).where(User.email == "cron_due@example.com"))).scalar_one()
        card = CreditCard(user_id=user.id, name="Kart", statement_day=1, payment_due_day=10)
        s.add(card)
        await s.flush()
        # Yaklaşan (3 gün sonra) ödenmemiş ekstre
        s.add(
            CreditCardStatement(
                card_id=card.id,
                period_year=today.year,
                period_month=today.month,
                statement_amount="1000.00",
                statement_date=today - timedelta(days=2),
                due_date=today + timedelta(days=3),
                paid_at=None,
            )
        )
        await s.commit()

    sent_calls = []

    async def _fake_send_to_user(db, user_id, title, body, url, tag=None, app_settings=None):
        sent_calls.append({"user_id": user_id, "title": title, "body": body, "url": url})
        return 1

    monkeypatch.setattr(scheduler, "send_to_user", _fake_send_to_user)

    await scheduler._push_due_payments_job(session_factory=TestSession)

    assert len(sent_calls) == 1
    assert sent_calls[0]["title"] == "Yaklaşan kart ödemesi"
    assert sent_calls[0]["url"] == "/dashboard/credit-cards"
    assert "1" in sent_calls[0]["body"]


@pytest.mark.asyncio
async def test_push_due_payments_job_skips_paid(client: AsyncClient, monkeypatch):
    """Ödenmiş (paid_at dolu) ekstre için bildirim gönderilmez."""
    from app import scheduler

    headers = await make_user(client, "cron_paid@example.com")
    await client.post("/api/v1/push/subscribe", json=_SUB, headers=headers)

    today = date.today()
    async with TestSession() as s:
        user = (await s.execute(select(User).where(User.email == "cron_paid@example.com"))).scalar_one()
        card = CreditCard(user_id=user.id, name="Kart", statement_day=1, payment_due_day=10)
        s.add(card)
        await s.flush()
        s.add(
            CreditCardStatement(
                card_id=card.id,
                period_year=today.year,
                period_month=today.month,
                statement_amount="1000.00",
                statement_date=today - timedelta(days=2),
                due_date=today + timedelta(days=3),
                paid_at=datetime.now(timezone.utc),  # ödenmiş
            )
        )
        await s.commit()

    sent_calls = []

    async def _fake_send_to_user(*a, **k):
        sent_calls.append(1)
        return 1

    monkeypatch.setattr(scheduler, "send_to_user", _fake_send_to_user)
    await scheduler._push_due_payments_job(session_factory=TestSession)
    assert sent_calls == []  # bildirim yok
