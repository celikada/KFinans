"""
Auth endpoint integration testleri — gerçek PostgreSQL, mock yok.
Her testte aynı DB session'ı kullanılır; rollback ile izolasyon sağlanır.
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.user import User
from tests.conftest import TestSession, verify_user_email


TEST_EMAIL = "test_auth@example.com"
TEST_PASSWORD = "guclu-sifre-123"


async def _get_user(email: str) -> User:
    async with TestSession() as session:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one()


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
    # Yeni alanlar:
    assert data["email_verified"] is False
    assert "verification_email_sent" in data


@pytest.mark.asyncio
async def test_register_with_risk_profile(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "rp_aggressive@example.com",
        "password": TEST_PASSWORD,
        "risk_profile": "aggressive",
    })
    assert resp.status_code == 201
    assert resp.json()["risk_profile"] == "aggressive"


@pytest.mark.asyncio
async def test_register_invalid_risk_profile_returns_422(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "rp_bad@example.com",
        "password": TEST_PASSWORD,
        "risk_profile": "yolo",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password_returns_422(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "shortpw@example.com",
        "password": "abc",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "pass1234"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_persists_verify_token(client: AsyncClient):
    email = "verify_token@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    user = await _get_user(email)
    assert user.verify_token is not None
    assert len(user.verify_token) >= 30
    assert user.verify_token_expires_at is not None
    assert user.verify_token_expires_at > datetime.now(timezone.utc)
    assert user.email_verified is False


@pytest.mark.asyncio
async def test_login_unverified_returns_403(client: AsyncClient):
    email = "unverified_login@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 403
    assert "doğrula" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_returns_tokens_after_verification(client: AsyncClient):
    email = "verified_login@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    await verify_user_email(email)
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient):
    email = "wrong_pw@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    await verify_user_email(email)
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "yanlis-sifre"})
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
    email = "refresh_user@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_with_access_token_returns_401(client: AsyncClient):
    email = "refresh_wrong@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    access_token = login.json()["access_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_email_succeeds_with_valid_token(client: AsyncClient):
    email = "verify_ok@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    user = await _get_user(email)
    token = user.verify_token

    resp = await client.get(f"/api/v1/auth/verify-email?token={token}")
    assert resp.status_code == 200

    user_after = await _get_user(email)
    assert user_after.email_verified is True
    assert user_after.verify_token is None
    assert user_after.verify_token_expires_at is None

    # Login artik calismali
    login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_email_invalid_token_returns_400(client: AsyncClient):
    resp = await client.get("/api/v1/auth/verify-email?token=" + "x" * 40)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_expired_token_returns_400(client: AsyncClient):
    email = "verify_expired@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    user = await _get_user(email)
    token = user.verify_token

    # Token suresini gecmise al
    async with TestSession() as session:
        await session.execute(
            update(User).where(User.email == email).values(
                verify_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        await session.commit()

    resp = await client.get(f"/api/v1/auth/verify-email?token={token}")
    assert resp.status_code == 400
    assert "süre" in resp.json()["detail"].lower() or "dolm" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_email_already_verified_is_idempotent(client: AsyncClient):
    email = "verify_idem@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    user = await _get_user(email)
    token = user.verify_token

    first = await client.get(f"/api/v1/auth/verify-email?token={token}")
    assert first.status_code == 200

    # Token sonrasinda silindi; ikinci cagri 400 olur (token yok)
    second = await client.get(f"/api/v1/auth/verify-email?token={token}")
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_for_existing_user(client: AsyncClient):
    email = "resend_ok@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    user_before = await _get_user(email)
    old_token = user_before.verify_token

    resp = await client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert resp.status_code == 202

    user_after = await _get_user(email)
    assert user_after.verify_token is not None
    assert user_after.verify_token != old_token  # token rotated
    assert user_after.email_verified is False


@pytest.mark.asyncio
async def test_resend_verification_unknown_email_returns_202_silently(client: AsyncClient):
    """Bilgi sizdirmamak icin bilinmeyen e-posta da 202 doner."""
    resp = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "hicbiryerde_yok@example.com"},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_resend_verification_already_verified_returns_202_silently(client: AsyncClient):
    email = "resend_verified@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    await verify_user_email(email)

    resp = await client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert resp.status_code == 202

    # Verify_token regenerate edilmemis olmali
    user_after = await _get_user(email)
    assert user_after.verify_token is None
    assert user_after.email_verified is True


# ─── SEC-002 (FAZ H): Account lockout ─────────────────────────────────────


@pytest.mark.asyncio
async def test_failed_login_increments_counter(client: AsyncClient):
    """Yanlis sifre denemesi failed_login_count'i artirir, basarili login sifirlar."""
    email = "lockout_inc@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    await verify_user_email(email)

    # 3 yanlis deneme
    for _ in range(3):
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "yanlis"})
        assert resp.status_code == 401

    user = await _get_user(email)
    assert user.failed_login_count == 3
    assert user.locked_until is None  # 10'a ulasmadi

    # Dogru login -> counter sifirlanir
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 200

    user_after = await _get_user(email)
    assert user_after.failed_login_count == 0


@pytest.mark.asyncio
async def test_account_locks_after_threshold(client: AsyncClient):
    """10 ust uste basarisiz login -> hesap 15 dk kilitlenir, sonraki istek 423."""
    email = "lockout_lock@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    await verify_user_email(email)

    # 10 yanlis deneme
    for _ in range(10):
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "yanlis"})
        assert resp.status_code == 401

    user = await _get_user(email)
    assert user.failed_login_count == 10
    assert user.locked_until is not None
    assert user.locked_until > datetime.now(timezone.utc)
    assert user.locked_until <= datetime.now(timezone.utc) + timedelta(minutes=15, seconds=10)

    # Kilitli iken dogru sifreyle bile login alinamaz
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 423
    body = resp.json()
    assert "kilitli" in body["detail"].lower()
    assert resp.headers.get("Retry-After")
    assert int(resp.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_lockout_expiry_unlocks_account(client: AsyncClient):
    """locked_until gecmisi ise dogru sifreyle login basarili olur ve counter sifirlanir."""
    email = "lockout_expire@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD})
    await verify_user_email(email)

    # Manuel olarak gecmis bir locked_until set et (otomatik 15 dk beklemek istemiyoruz)
    async with TestSession() as session:
        await session.execute(
            update(User).where(User.email == email).values(
                failed_login_count=10,
                locked_until=datetime.now(timezone.utc) - timedelta(minutes=1),  # gecmis
            )
        )
        await session.commit()

    # Dogru sifre -> 200 ve counter sifirlanir
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 200

    user_after = await _get_user(email)
    assert user_after.failed_login_count == 0
    assert user_after.locked_until is None
