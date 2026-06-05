"""Sürüm bildirimleri (release notes) entegrasyon testleri.

Kapsam:
- register opt-in alanı kaydedilir (varsayılan False, açıkça True gönderilebilir).
- unsubscribe token akışı (geçerli token kapatır, geçersiz → 404).
- opt-in toggle (auth'lu PUT/GET).
- admin send: opt-in + verified kullanıcılara mail (email gönderimi mock).
- is_admin yetki: non-admin → 403.
- changelog parse (unit) ayrı dosyada (test_changelog.py).
"""

import uuid

import pytest
from sqlalchemy import select, update

from app.models.user import User
from tests.conftest import TestSession, make_user, verify_user_email

pytestmark = pytest.mark.asyncio


async def _make_admin(client, email: str | None = None) -> dict:
    """make_user + DB'de is_admin=True set eder, header döner."""
    if email is None:
        email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    headers = await make_user(client, email)
    async with TestSession() as session:
        await session.execute(update(User).where(User.email == email).values(is_admin=True))
        await session.commit()
    return headers


async def _register(client, email: str, *, opt_in: bool | None = None) -> None:
    body = {"email": email, "password": "guclu-sifre-123", "age_confirmed": True}
    if opt_in is not None:
        body["release_notes_opt_in"] = opt_in
    await client.post("/api/v1/auth/register", json=body)


async def _get_user(email: str) -> User:
    async with TestSession() as session:
        res = await session.execute(select(User).where(User.email == email))
        return res.scalar_one()


# ─── Register opt-in ────────────────────────────────────────────────


async def test_register_opt_in_default_false(client):
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, email)  # opt_in gönderilmedi
    user = await _get_user(email)
    assert user.release_notes_opt_in is False
    # unsubscribe_token her kullanıcıya üretilir
    assert user.unsubscribe_token
    assert user.is_admin is False


async def test_register_opt_in_true(client):
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, email, opt_in=True)
    user = await _get_user(email)
    assert user.release_notes_opt_in is True


# ─── Opt-in toggle (auth) ───────────────────────────────────────────


async def test_opt_in_toggle(client):
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    headers = await make_user(client, email)

    # Başlangıçta kapalı
    r = await client.get("/api/v1/release-notes/opt-in", headers=headers)
    assert r.status_code == 200
    assert r.json()["release_notes_opt_in"] is False

    # Aç
    r = await client.put("/api/v1/release-notes/opt-in", headers=headers, json={"opt_in": True})
    assert r.status_code == 200
    assert r.json()["release_notes_opt_in"] is True

    user = await _get_user(email)
    assert user.release_notes_opt_in is True

    # Kapat
    r = await client.put("/api/v1/release-notes/opt-in", headers=headers, json={"opt_in": False})
    assert r.status_code == 200
    assert r.json()["release_notes_opt_in"] is False


async def test_opt_in_requires_auth(client):
    r = await client.put("/api/v1/release-notes/opt-in", json={"opt_in": True})
    assert r.status_code == 401


# ─── Unsubscribe (auth'suz, token) ──────────────────────────────────


async def test_unsubscribe_valid_token(client):
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, email, opt_in=True)
    user = await _get_user(email)
    token = user.unsubscribe_token

    r = await client.get(f"/api/v1/release-notes/unsubscribe?token={token}")
    assert r.status_code == 200
    assert "iptal" in r.text.lower()

    refreshed = await _get_user(email)
    assert refreshed.release_notes_opt_in is False


async def test_unsubscribe_invalid_token(client):
    r = await client.get("/api/v1/release-notes/unsubscribe?token=gecersiz-token-xyz")
    assert r.status_code == 404


# ─── Admin send ─────────────────────────────────────────────────────


async def test_send_requires_admin(client):
    headers = await make_user(client)  # normal kullanıcı
    r = await client.post("/api/v1/release-notes/send", headers=headers, json={"version": "0.2.0"})
    assert r.status_code == 403


async def test_send_unknown_version_404(client):
    headers = await _make_admin(client)
    r = await client.post("/api/v1/release-notes/send", headers=headers, json={"version": "99.99.99"})
    assert r.status_code == 404


async def test_send_to_opt_in_verified_users(client, monkeypatch):
    sent_to: list[str] = []

    async def _fake_send(*, to, version, body_html, unsubscribe_url):
        sent_to.append(to)
        assert "unsubscribe" in unsubscribe_url
        assert body_html  # markdown→html dönüşmüş
        return True

    # release router'ın import ettiği sembolü patch et
    monkeypatch.setattr("app.api.v1.release.send_release_notes_email", _fake_send)

    # 1) opt-in + verified alıcı
    recipient = f"r-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, recipient, opt_in=True)
    await verify_user_email(recipient)

    # 2) opt-in ama doğrulanmamış → gönderilmez
    not_verified = f"nv-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, not_verified, opt_in=True)

    # 3) verified ama opt-out → gönderilmez
    opted_out = f"oo-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, opted_out, opt_in=False)
    await verify_user_email(opted_out)

    headers = await _make_admin(client)
    r = await client.post("/api/v1/release-notes/send", headers=headers, json={"version": "0.2.0"})
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "0.2.0"
    assert data["sent"] == data["recipients"]
    # Sadece opt-in + verified alıcıya gitti
    assert recipient in sent_to
    assert not_verified not in sent_to
    assert opted_out not in sent_to


async def test_preview_requires_admin(client):
    headers = await make_user(client)
    r = await client.get("/api/v1/release-notes/preview?version=0.2.0", headers=headers)
    assert r.status_code == 403


async def test_preview_returns_markdown(client):
    headers = await _make_admin(client)
    r = await client.get("/api/v1/release-notes/preview?version=0.2.0", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "0.2.0"
    assert "[0.2.0]" in data["body_markdown"]


# ─── X-Release-Token (CI/CD otomasyon yolu) ─────────────────────────


async def test_send_via_release_token(client, monkeypatch):
    """X-Release-Token geçerli → admin JWT olmadan gönderim (CI yolu)."""
    sent_to: list[str] = []

    async def _fake_send(*, to, version, body_html, unsubscribe_url):
        sent_to.append(to)
        return True

    monkeypatch.setattr("app.api.v1.release.send_release_notes_email", _fake_send)
    monkeypatch.setattr("app.api.v1.release.settings.release_notes_token", "ci-secret-token")

    recipient = f"rt-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, recipient, opt_in=True)
    await verify_user_email(recipient)

    r = await client.post(
        "/api/v1/release-notes/send",
        headers={"X-Release-Token": "ci-secret-token"},
        json={"version": "0.2.0"},
    )
    assert r.status_code == 200
    assert recipient in sent_to


async def test_send_wrong_release_token_401(client, monkeypatch):
    """Yanlış token + admin JWT yok → 401."""
    monkeypatch.setattr("app.api.v1.release.settings.release_notes_token", "ci-secret-token")
    r = await client.post(
        "/api/v1/release-notes/send",
        headers={"X-Release-Token": "yanlis"},
        json={"version": "0.2.0"},
    )
    assert r.status_code == 401


async def test_send_no_auth_401(client):
    """Token da JWT de yok → 401."""
    r = await client.post("/api/v1/release-notes/send", json={"version": "0.2.0"})
    assert r.status_code == 401


# ─── ADMIN_EMAILS bootstrap (girişte otomatik admin) ────────────────


async def test_admin_emails_bootstrap_on_login(client, monkeypatch):
    """ADMIN_EMAILS'teki kullanıcı girişte otomatik is_admin olur."""
    email = f"boot-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, email)
    await verify_user_email(email)

    # Önce admin değil
    assert (await _get_user(email)).is_admin is False

    monkeypatch.setattr("app.api.v1.auth.settings.admin_emails", f"{email}, other@x.com")
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "guclu-sifre-123", "age_confirmed": True},
    )
    assert r.status_code == 200
    # Giriş sonrası admin oldu
    assert (await _get_user(email)).is_admin is True


async def test_admin_emails_empty_no_grant(client, monkeypatch):
    """ADMIN_EMAILS boş → kimse otomatik admin olmaz."""
    email = f"noboot-{uuid.uuid4().hex[:10]}@example.com"
    await _register(client, email)
    await verify_user_email(email)
    monkeypatch.setattr("app.api.v1.auth.settings.admin_emails", "")
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "guclu-sifre-123", "age_confirmed": True},
    )
    assert r.status_code == 200
    assert (await _get_user(email)).is_admin is False
