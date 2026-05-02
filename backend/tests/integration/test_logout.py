"""POST /auth/logout endpoint'i ve JWT blacklist davranisi.

Logout sonrasi:
- Access token ile auth gerektiren her endpoint 401 doner
- Refresh token (body'de gonderildiyse) /auth/refresh'te 401 doner
- Logout idempotent — ayni token tekrar logout edilirse hata yok
"""
import pytest
from httpx import AsyncClient

from tests.conftest import verify_user_email


async def _register_and_login(client: AsyncClient, email: str) -> dict:
    """User olustur, dogrula, login yap; tum tokenlari ve auth header'i don."""
    pwd = "guclu-sifre-123"
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    data = login.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


@pytest.mark.asyncio
async def test_logout_returns_200(client: AsyncClient):
    session = await _register_and_login(client, "logout_basic@example.com")
    resp = await client.post("/api/v1/auth/logout", json={}, headers=session["headers"])
    assert resp.status_code == 200
    assert "Çıkış" in resp.json()["detail"] or "yapıldı" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_logout_blacklists_access_token(client: AsyncClient):
    """Logout sonrasi ayni access token ile auth endpoint'e erisilmemeli."""
    session = await _register_and_login(client, "logout_access@example.com")

    # Logout once
    await client.post("/api/v1/auth/logout", json={}, headers=session["headers"])

    # Ayni access token ile auth gerektiren endpoint
    resp = await client.get("/api/v1/integrations", headers=session["headers"])
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_blacklists_refresh_token_when_provided(client: AsyncClient):
    """Body'de refresh_token verilirse /auth/refresh'te 401 olmali."""
    session = await _register_and_login(client, "logout_refresh@example.com")

    await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": session["refresh_token"]},
        headers=session["headers"],
    )

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": session["refresh_token"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_works_when_only_access_logged_out(client: AsyncClient):
    """Sadece access logout edilirse refresh hala calismali (yeni access uretir)."""
    session = await _register_and_login(client, "logout_partial@example.com")

    # Sadece access blacklist (refresh_token body'ye dahil edilmez)
    await client.post("/api/v1/auth/logout", json={}, headers=session["headers"])

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": session["refresh_token"]},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_logout_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.post("/api/v1/auth/logout", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_idempotent(client: AsyncClient):
    """Ayni access token tekrar logout edilirse 401 (token zaten blacklist'te)."""
    session = await _register_and_login(client, "logout_idem@example.com")

    first = await client.post("/api/v1/auth/logout", json={}, headers=session["headers"])
    assert first.status_code == 200

    # Ikinci cagrida access zaten blacklist'te → get_current_user 401
    second = await client.post("/api/v1/auth/logout", json={}, headers=session["headers"])
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_invalid_refresh_token_silently_succeeds(client: AsyncClient):
    """Bozuk refresh token body'de olsa bile access blacklist edilir, logout basarili."""
    session = await _register_and_login(client, "logout_bad_refresh@example.com")

    resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "garbage.invalid.token"},
        headers=session["headers"],
    )
    assert resp.status_code == 200

    # Access blacklist edilmis olmali
    auth = await client.get("/api/v1/integrations", headers=session["headers"])
    assert auth.status_code == 401


@pytest.mark.asyncio
async def test_logout_does_not_affect_other_users(client: AsyncClient):
    """User A logout, User B'nin token'i etkilenmemeli."""
    session_a = await _register_and_login(client, "logout_a@example.com")
    session_b = await _register_and_login(client, "logout_b@example.com")

    await client.post("/api/v1/auth/logout", json={}, headers=session_a["headers"])

    # B'nin tokenlari hala calisiyor olmali
    resp = await client.get("/api/v1/integrations", headers=session_b["headers"])
    assert resp.status_code == 200
