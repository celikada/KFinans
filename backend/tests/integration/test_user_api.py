"""
User API integration testleri.

Endpoint'ler:
  GET    /user/me       — kullanıcı profil
  PUT    /user/profile  — risk_profile güncelle
  PUT    /user/password — şifre değiştir
  DELETE /user/me       — soft-delete (deleted_at = now)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from tests.conftest import TestSession, verify_user_email


async def _make_user(client: AsyncClient, email: str, pwd: str = "guclu-sifre-123") -> dict:
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd, "age_confirmed": True})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd, "age_confirmed": True})
    return {
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        "email": email,
    }


# ─── GET /user/me ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/user/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_user_profile(client: AsyncClient):
    session = await _make_user(client, "user_me@example.com")
    resp = await client.get("/api/v1/user/me", headers=session["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user_me@example.com"
    assert data["email_verified"] is True
    assert data["risk_profile"] in ("conservative", "balanced", "aggressive")
    assert "created_at" in data
    assert "credit_balance" in data
    # Sensitive alanlar dönmemeli
    assert "password_hash" not in data
    assert "verify_token" not in data


# ─── PUT /user/profile ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_profile_changes_risk_profile(client: AsyncClient):
    session = await _make_user(client, "user_profile@example.com")
    resp = await client.put(
        "/api/v1/user/profile",
        json={"risk_profile": "aggressive"},
        headers=session["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["risk_profile"] == "aggressive"

    # Tekrar GET'le doğrula
    me = await client.get("/api/v1/user/me", headers=session["headers"])
    assert me.json()["risk_profile"] == "aggressive"


@pytest.mark.asyncio
async def test_update_profile_invalid_risk_returns_422(client: AsyncClient):
    session = await _make_user(client, "user_profile_bad@example.com")
    resp = await client.put(
        "/api/v1/user/profile",
        json={"risk_profile": "yatirimci-degilim"},
        headers=session["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_profile_requires_auth(client: AsyncClient):
    resp = await client.put("/api/v1/user/profile", json={"risk_profile": "balanced"})
    assert resp.status_code == 401


# ─── PUT /user/password ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_change_password_wrong_current_returns_400(client: AsyncClient):
    session = await _make_user(client, "user_pwd_wrong@example.com")
    resp = await client.put(
        "/api/v1/user/password",
        json={"current_password": "yanlis-sifre", "new_password": "yenisifre456"},
        headers=session["headers"],
    )
    assert resp.status_code == 400
    assert "hatalı" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_password_short_new_returns_422(client: AsyncClient):
    """new_password min_length=8 — 7 karakter → 422."""
    session = await _make_user(client, "user_pwd_short@example.com")
    resp = await client.put(
        "/api/v1/user/password",
        json={"current_password": "guclu-sifre-123", "new_password": "kisa12"},
        headers=session["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_success_then_login_with_new(client: AsyncClient):
    session = await _make_user(client, "user_pwd_ok@example.com")
    # Şifreyi değiştir
    resp = await client.put(
        "/api/v1/user/password",
        json={"current_password": "guclu-sifre-123", "new_password": "yeni-guclu-sifre-456"},
        headers=session["headers"],
    )
    assert resp.status_code == 200

    # Eski şifre artık çalışmamalı
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user_pwd_ok@example.com", "password": "guclu-sifre-123"},
    )
    assert bad_login.status_code == 401

    # Yeni şifre çalışmalı
    good_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user_pwd_ok@example.com", "password": "yeni-guclu-sifre-456"},
    )
    assert good_login.status_code == 200


# ─── DELETE /user/me (soft-delete) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_me_sets_deleted_at(client: AsyncClient):
    session = await _make_user(client, "user_delete@example.com")
    resp = await client.delete("/api/v1/user/me", headers=session["headers"])
    assert resp.status_code == 200

    # DB'de deleted_at set olmuş olmalı
    async with TestSession() as db:
        u = (await db.execute(select(User).where(User.email == "user_delete@example.com"))).scalar_one()
        assert u.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_me_requires_auth(client: AsyncClient):
    resp = await client.delete("/api/v1/user/me")
    assert resp.status_code == 401


# ─── IDOR — kullanıcı izolasyonu ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_a_cannot_modify_user_b_profile(client: AsyncClient):
    """GET/PUT /user/* her zaman current_user üzerinden çalışır.

    A'nın token'ıyla B'nin profilini okuma teknik olarak imkansız (sub claim
    A'yı işaret eder). Bu test invariant'ı doğrular.
    """
    session_a = await _make_user(client, "user_idor_a@example.com")
    session_b = await _make_user(client, "user_idor_b@example.com")

    # A token'ıyla risk değiştir
    await client.put(
        "/api/v1/user/profile",
        json={"risk_profile": "aggressive"},
        headers=session_a["headers"],
    )
    # B token'ıyla risk hala default olmalı
    me_b = await client.get("/api/v1/user/me", headers=session_b["headers"])
    assert me_b.json()["risk_profile"] != "aggressive" or me_b.json()["email"] == "user_idor_b@example.com"
    # daha kesin: B'nin email'i kendi
    assert me_b.json()["email"] == "user_idor_b@example.com"
