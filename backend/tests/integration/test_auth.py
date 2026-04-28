"""
Auth endpoint integration testleri — gerçek PostgreSQL, mock yok.
Her testte aynı DB session'ı kullanılır; rollback ile izolasyon sağlanır.
"""
import pytest
from httpx import AsyncClient


TEST_EMAIL = "test_auth@example.com"
TEST_PASSWORD = "guclu-sifre-123"


@pytest.mark.asyncio
async def test_register_creates_user(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == TEST_EMAIL
    assert "id" in data
    assert "risk_profile" in data


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "pass1234"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_tokens(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": TEST_EMAIL,
        "password": "yanlis-sifre",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "yok@example.com",
        "password": "herhangi",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_with_access_token_returns_401(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    access_token = login.json()["access_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401
