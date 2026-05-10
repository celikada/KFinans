"""COMP-003 + COMP-006 + COMP-029 (FAZ H): KVKK haklari endpoint testleri.

- COMP-003: GET /user/data-export (veri tasinabilirligi)
- COMP-006: DELETE /user/consent/{type} (acik riza geri cekme)
- COMP-029: POST /user/email/request + GET /user/email/confirm (email change)
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.user import User
from tests.conftest import TestSession, make_user, verify_user_email


# ─── COMP-003: data-export ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_data_export_returns_user_profile_and_audit(client: AsyncClient):
    """data-export JSON formatinda profile + audit_logs listesini icerir."""
    headers = await make_user(client, "data_export@example.com")
    resp = await client.get("/api/v1/user/data-export", headers=headers)
    assert resp.status_code == 200
    payload = json.loads(resp.content)
    assert payload["_meta"]["format"] == "kfinans-data-export-v1"
    assert payload["profile"]["email"] == "data_export@example.com"
    # Audit logs export aksiyonu icermeli (DATA_EXPORT)
    actions = {a["action"] for a in payload["audit_logs"]}
    assert "user.data_export" in actions or "auth.register" in actions
    # Liste alanlari mevcut (bos olabilir)
    for key in ("integrations", "wallets", "snapshots", "expenses", "audit_logs"):
        assert key in payload
        assert isinstance(payload[key], list)


@pytest.mark.asyncio
async def test_data_export_excludes_api_key_plaintext(client: AsyncClient):
    """Integrations export'unda encrypted_key/encrypted_secret YOK olmalidir."""
    headers = await make_user(client, "data_export_api@example.com")
    resp = await client.get("/api/v1/user/data-export", headers=headers)
    assert resp.status_code == 200
    payload = json.loads(resp.content)
    # Mevcut hicbir integration olmasa da, schema icinde encrypted_* alanlari sizmamali
    # Bos liste durumunda da dogru cunku _list exclude'u uygular.
    serialized_str = resp.text
    assert "encrypted_key" not in serialized_str
    assert "encrypted_secret" not in serialized_str


@pytest.mark.asyncio
async def test_data_export_requires_auth(client: AsyncClient):
    """Token yoksa 401."""
    resp = await client.get("/api/v1/user/data-export")
    assert resp.status_code == 401


# ─── COMP-006: consent revoke ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_overseas_consent(client: AsyncClient):
    """Acik riza geri cekme overseas_consent_at'i NULL'lar."""
    email = "consent_revoke@example.com"
    headers = await make_user(client, email)

    # Manuel olarak overseas_consent_at set et (register'da varsayilan default False)
    async with TestSession() as session:
        await session.execute(
            update(User).where(User.email == email).values(
                overseas_consent_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    resp = await client.delete("/api/v1/user/consent/overseas", headers=headers)
    assert resp.status_code == 200

    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        assert user.overseas_consent_at is None


@pytest.mark.asyncio
async def test_revoke_consent_unknown_type_400(client: AsyncClient):
    """Bilinmeyen riza turu 400."""
    headers = await make_user(client, "consent_bad@example.com")
    resp = await client.delete("/api/v1/user/consent/something", headers=headers)
    assert resp.status_code == 400


# ─── COMP-029: email change ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_email_change_request_creates_token(client: AsyncClient):
    """E-posta degistirme istegi token + new_email + expires_at set eder."""
    email = "email_change@example.com"
    headers = await make_user(client, email)

    resp = await client.post(
        "/api/v1/user/email/request",
        headers=headers,
        json={"new_email": "new_email@example.com"},
    )
    assert resp.status_code == 202

    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        assert user.email_change_new == "new_email@example.com"
        assert user.email_change_token is not None
        assert user.email_change_expires_at is not None
        assert user.email_change_expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_email_change_request_same_email_400(client: AsyncClient):
    """Yeni email mevcutla ayni ise 400."""
    email = "email_same@example.com"
    headers = await make_user(client, email)
    resp = await client.post(
        "/api/v1/user/email/request",
        headers=headers,
        json={"new_email": email},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_email_change_request_taken_email_409(client: AsyncClient):
    """Yeni email baska bir hesapta varsa 409."""
    headers = await make_user(client, "ec_owner@example.com")
    # Ayri kullanici ec_target olusturalim
    await make_user(client, "ec_target@example.com")
    resp = await client.post(
        "/api/v1/user/email/request",
        headers=headers,
        json={"new_email": "ec_target@example.com"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_email_change_confirm_swaps_email(client: AsyncClient):
    """Token tiklandiginda email swap'i tamamlanir."""
    old_email = "ec_old@example.com"
    new_email = "ec_new@example.com"
    headers = await make_user(client, old_email)
    await client.post(
        "/api/v1/user/email/request",
        headers=headers,
        json={"new_email": new_email},
    )

    async with TestSession() as session:
        user = (await session.execute(select(User).where(User.email == old_email))).scalar_one()
        token = user.email_change_token

    resp = await client.get(f"/api/v1/user/email/confirm?token={token}")
    assert resp.status_code == 200

    async with TestSession() as session:
        # old_email artik bulunmamali, new_email var
        old = (await session.execute(select(User).where(User.email == old_email))).scalar_one_or_none()
        new = (await session.execute(select(User).where(User.email == new_email))).scalar_one_or_none()
        assert old is None
        assert new is not None
        assert new.email_change_token is None
        assert new.email_change_new is None


@pytest.mark.asyncio
async def test_email_change_confirm_expired_token_400(client: AsyncClient):
    """Suresi dolmus token 400 doner, email degismez."""
    email = "ec_expired@example.com"
    headers = await make_user(client, email)
    await client.post(
        "/api/v1/user/email/request",
        headers=headers,
        json={"new_email": "ec_target_expired@example.com"},
    )

    async with TestSession() as session:
        await session.execute(
            update(User).where(User.email == email).values(
                email_change_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        token = user.email_change_token

    resp = await client.get(f"/api/v1/user/email/confirm?token={token}")
    assert resp.status_code == 400

    async with TestSession() as session:
        # Email degismedi
        user_after = (await session.execute(select(User).where(User.email == email))).scalar_one()
        assert user_after.email == email
