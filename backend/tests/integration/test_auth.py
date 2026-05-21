"""
Auth endpoint integration testleri — gerçek PostgreSQL, mock yok.
Her testte aynı DB session'ı kullanılır; rollback ile izolasyon sağlanır.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.password_policy import _HIBP_RANGE_URL
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
        "age_confirmed": True,
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
        "age_confirmed": True,
    })
    assert resp.status_code == 201
    assert resp.json()["risk_profile"] == "aggressive"


@pytest.mark.asyncio
async def test_register_invalid_risk_profile_returns_422(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "rp_bad@example.com",
        "password": TEST_PASSWORD,
        "risk_profile": "yolo",
        "age_confirmed": True,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password_returns_422(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "shortpw@example.com",
        "password": "abc",
        "age_confirmed": True,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "pass1234", "age_confirmed": True}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


# COMP-010 (FAZ H): 18+ yas dogrulama
@pytest.mark.asyncio
async def test_register_without_age_confirmation_returns_422(client: AsyncClient):
    """age_confirmed=False -> 422 (KVKK 2018/482, TMK m.16)."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "no_age@example.com",
        "password": TEST_PASSWORD,
        # age_confirmed eksik (default False)
    })
    assert resp.status_code == 422
    assert "18 yasini" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_explicit_age_false_returns_422(client: AsyncClient):
    """age_confirmed=False acikca verilse de 422."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "age_false@example.com",
        "password": TEST_PASSWORD,
        "age_confirmed": False,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_persists_verify_token(client: AsyncClient):
    email = "verify_token@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    user = await _get_user(email)
    assert user.verify_token is not None
    assert len(user.verify_token) >= 30
    assert user.verify_token_expires_at is not None
    assert user.verify_token_expires_at > datetime.now(timezone.utc)
    assert user.email_verified is False


@pytest.mark.asyncio
async def test_login_unverified_returns_403(client: AsyncClient):
    email = "unverified_login@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    assert resp.status_code == 403
    assert "doğrula" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_returns_tokens_after_verification(client: AsyncClient):
    email = "verified_login@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient):
    email = "wrong_pw@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
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
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_with_access_token_returns_401(client: AsyncClient):
    email = "refresh_wrong@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    access_token = login.json()["access_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_email_succeeds_with_valid_token(client: AsyncClient):
    email = "verify_ok@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    user = await _get_user(email)
    token = user.verify_token

    resp = await client.get(f"/api/v1/auth/verify-email?token={token}")
    assert resp.status_code == 200

    user_after = await _get_user(email)
    assert user_after.email_verified is True
    assert user_after.verify_token is None
    assert user_after.verify_token_expires_at is None

    # Login artik calismali
    login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_email_invalid_token_returns_400(client: AsyncClient):
    resp = await client.get("/api/v1/auth/verify-email?token=" + "x" * 40)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_expired_token_returns_400(client: AsyncClient):
    email = "verify_expired@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
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
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
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
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
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
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
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
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)

    # 3 yanlis deneme
    for _ in range(3):
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "yanlis"})
        assert resp.status_code == 401

    user = await _get_user(email)
    assert user.failed_login_count == 3
    assert user.locked_until is None  # 10'a ulasmadi

    # Dogru login -> counter sifirlanir
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    assert resp.status_code == 200

    user_after = await _get_user(email)
    assert user_after.failed_login_count == 0


@pytest.mark.asyncio
async def test_account_locks_after_threshold(client: AsyncClient):
    """10 ust uste basarisiz login -> hesap 15 dk kilitlenir, sonraki istek 423."""
    email = "lockout_lock@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
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
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    assert resp.status_code == 423
    body = resp.json()
    assert "kilitli" in body["detail"].lower()
    assert resp.headers.get("Retry-After")
    assert int(resp.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_lockout_expiry_unlocks_account(client: AsyncClient):
    """locked_until gecmisi ise dogru sifreyle login basarili olur ve counter sifirlanir."""
    email = "lockout_expire@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
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
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    assert resp.status_code == 200

    user_after = await _get_user(email)
    assert user_after.failed_login_count == 0
    assert user_after.locked_until is None


# ─── SEC-001 (FAZ H): Password reset (OWASP Forgot Password Cheat Sheet) ──


@pytest.mark.asyncio
async def test_forgot_password_known_user_creates_token(client: AsyncClient):
    """Bilinen + dogrulanmis kullanici icin reset_token uretilir."""
    email = "reset_known@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)

    resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 202

    user_after = await _get_user(email)
    assert user_after.reset_token is not None
    assert len(user_after.reset_token) >= 32  # token_urlsafe(32) ~43 char
    assert user_after.reset_token_expires_at is not None
    assert user_after.reset_token_expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_202_silently(client: AsyncClient):
    """Bilinmeyen e-posta da 202 doner (kullanici enumeration onlenir)."""
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "yok_boyle_biri@example.com"},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_forgot_password_unverified_user_no_token_generated(client: AsyncClient):
    """Henuz dogrulanmamis kullanici icin token uretilmez (yine 202)."""
    email = "reset_unverified@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    # verify_user_email() cagrilmadi - email_verified = False

    resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 202

    user_after = await _get_user(email)
    assert user_after.reset_token is None


@pytest.mark.asyncio
async def test_reset_password_completes_with_valid_token(client: AsyncClient):
    """Token ile yeni sifre kaydedilir, token tuketilir, eski sifre invalid."""
    email = "reset_complete@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)
    await client.post("/api/v1/auth/forgot-password", json={"email": email})

    user = await _get_user(email)
    token = user.reset_token

    new_password = "yepyeni-sifre-456"
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )
    assert resp.status_code == 200

    # Token tuketildi
    user_after = await _get_user(email)
    assert user_after.reset_token is None
    assert user_after.reset_token_expires_at is None

    # Eski sifre artik calismaz
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True},
    )
    assert bad_login.status_code == 401

    # Yeni sifre calisir
    good_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert good_login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token_returns_400(client: AsyncClient):
    """Bilinmeyen token 400 doner."""
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "x" * 40, "new_password": "yeni-sifre-789"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_expired_token_returns_400(client: AsyncClient):
    """Suresi dolmus token reddedilir, sifre degismez."""
    email = "reset_expired@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)
    await client.post("/api/v1/auth/forgot-password", json={"email": email})

    # Manuel olarak expire et
    user = await _get_user(email)
    token = user.reset_token
    async with TestSession() as session:
        await session.execute(
            update(User).where(User.email == email).values(
                reset_token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "yeni-sifre-789"},
    )
    assert resp.status_code == 400

    # Eski sifre hala gecerli
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_token_rotation(client: AsyncClient):
    """Ikinci forgot-password yeni token uretir; eski token gecersiz olur."""
    email = "reset_rotate@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    user_first = await _get_user(email)
    token1 = user_first.reset_token

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    user_second = await _get_user(email)
    token2 = user_second.reset_token

    assert token1 != token2

    # Eski token (token1) artik DB'de yok -> reset_password 400
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token1, "new_password": "yeni-sifre-rotate"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_clears_lockout_state(client: AsyncClient):
    """Sifre sifirlama SEC-002 lockout state'i de sifirlar (failed_count + locked_until)."""
    email = "reset_lockout@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": TEST_PASSWORD, "age_confirmed": True})
    await verify_user_email(email)

    # Manuel olarak lockout simule et
    async with TestSession() as session:
        await session.execute(
            update(User).where(User.email == email).values(
                failed_login_count=10,
                locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
            )
        )
        await session.commit()

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    user = await _get_user(email)

    new_password = "lockout-aldim-sifirla-1"
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": user.reset_token, "new_password": new_password},
    )
    assert resp.status_code == 200

    # Lockout state sifirlandi
    user_after = await _get_user(email)
    assert user_after.failed_login_count == 0
    assert user_after.locked_until is None


# ─── SEC (audit #5): Password policy (zxcvbn + HIBP) ─────────────────────────


def _hibp_body_for(password: str, count: int) -> str:
    """HIBP response uret — sifrenin suffix'i `count` ile birlikte."""
    sha1_hex = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    suffix = sha1_hex[5:]
    return (
        "0018A45C4D1DEF81644B54AB7F969B88D65:5\r\n"
        f"{suffix}:{count}\r\n"
    )


def _hibp_clean_body() -> str:
    """Suffix eslesmeyen response — pwned olmayan sifreler icin."""
    return (
        "0018A45C4D1DEF81644B54AB7F969B88D65:5\r\n"
        "00D4F6E8FA6EECAD2A3AA415EEC418D38EC:2\r\n"
    )


@pytest.mark.password_policy_enabled
@pytest.mark.asyncio
async def test_register_weak_password_returns_422(client: AsyncClient):
    """Zayif sifre (zxcvbn score < 3) -> 422 + Turkce mesaj."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "weak_pw@example.com",
        "password": "12345678",  # zxcvbn score 0/1
        "age_confirmed": True,
    })
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "zayif" in detail.lower() or "skor" in detail.lower()
    # Sifrenin kendisi mesajda olmamali
    assert "12345678" not in detail


@pytest.mark.password_policy_enabled
@pytest.mark.asyncio
async def test_register_password_containing_email_rejected(client: AsyncClient):
    """Email/local-part iceren sifre -> 422 (zxcvbn user_inputs)."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "celikada@example.com",
        "password": "Celikada123!",
        "age_confirmed": True,
    })
    assert resp.status_code == 422


@pytest.mark.password_policy_enabled
@pytest.mark.asyncio
async def test_register_pwned_password_returns_422(client: AsyncClient):
    """HIBP'de bulunan sifre -> 422 'veri sizintilarinda bulundu' mesaji."""
    strong_but_pwned = "very-strong-passphrase-but-leaked-9z"
    prefix = hashlib.sha1(strong_but_pwned.encode()).hexdigest().upper()[:5]

    with respx.mock(assert_all_called=False):
        respx.get(_HIBP_RANGE_URL.format(prefix=prefix)).mock(
            return_value=httpx.Response(200, text=_hibp_body_for(strong_but_pwned, 42)),
        )
        # Tum diger HIBP cagrilari (varsa) clean response
        respx.get(url__regex=r"https://api\.pwnedpasswords\.com/range/.*").mock(
            return_value=httpx.Response(200, text=_hibp_clean_body()),
        )
        resp = await client.post("/api/v1/auth/register", json={
            "email": "pwned_pw@example.com",
            "password": strong_but_pwned,
            "age_confirmed": True,
        })

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "sizinti" in detail.lower() or "sızıntı" in detail.lower()
    # Sifre mesajda olmamali
    assert strong_but_pwned not in detail


@pytest.mark.password_policy_enabled
@pytest.mark.asyncio
async def test_register_strong_non_pwned_password_succeeds(client: AsyncClient):
    """Guclu + HIBP'de olmayan sifre -> 201 basari."""
    strong = "yagmur-kahve-bulut-meridyen-9421-Q!"

    with respx.mock(assert_all_called=False):
        # Tum HIBP cagrilari clean (suffix eslesmiyor)
        respx.get(url__regex=r"https://api\.pwnedpasswords\.com/range/.*").mock(
            return_value=httpx.Response(200, text=_hibp_clean_body()),
        )
        resp = await client.post("/api/v1/auth/register", json={
            "email": "strong_pw@example.com",
            "password": strong,
            "age_confirmed": True,
        })

    assert resp.status_code == 201


@pytest.mark.password_policy_enabled
@pytest.mark.asyncio
async def test_register_hibp_timeout_fails_open(client: AsyncClient):
    """HIBP timeout -> registration block edilmez (fail-open)."""
    strong = "yagmur-kahve-bulut-meridyen-3185-K!"

    with respx.mock(assert_all_called=False):
        respx.get(url__regex=r"https://api\.pwnedpasswords\.com/range/.*").mock(
            side_effect=httpx.TimeoutException("network timeout"),
        )
        resp = await client.post("/api/v1/auth/register", json={
            "email": "hibp_timeout@example.com",
            "password": strong,
            "age_confirmed": True,
        })

    # zxcvbn gecti, HIBP timeout -> kayit yine de basarili
    assert resp.status_code == 201


@pytest.mark.password_policy_enabled
@pytest.mark.asyncio
async def test_change_password_weak_returns_422(client: AsyncClient):
    """PUT /user/password zayif yeni sifreyi reddeder."""
    # Once strong sifre ile kayit + login (policy bypass yapilmadan)
    strong = "ilk-guclu-sifre-meridyen-Q9!-bulut"
    with respx.mock(assert_all_called=False):
        respx.get(url__regex=r"https://api\.pwnedpasswords\.com/range/.*").mock(
            return_value=httpx.Response(200, text=_hibp_clean_body()),
        )
        await client.post("/api/v1/auth/register", json={
            "email": "change_weak@example.com",
            "password": strong,
            "age_confirmed": True,
        })
        await verify_user_email("change_weak@example.com")
        login = await client.post("/api/v1/auth/login", json={
            "email": "change_weak@example.com",
            "password": strong,
        })
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Yeni sifre zayif -> 422
        resp = await client.put(
            "/api/v1/user/password",
            json={"current_password": strong, "new_password": "password123"},
            headers=headers,
        )
    assert resp.status_code == 422


@pytest.mark.password_policy_enabled
@pytest.mark.asyncio
async def test_change_password_pwned_returns_422(client: AsyncClient):
    """PUT /user/password HIBP'de olan sifreyi reddeder."""
    strong = "ilk-guclu-sifre-yagmur-K9!-meridyen"
    new_pwned = "yepyeni-sifre-yagmur-Q9!-pwned-x42"

    new_pwned_prefix = hashlib.sha1(new_pwned.encode()).hexdigest().upper()[:5]

    with respx.mock(assert_all_called=False):
        # Default: clean response
        respx.get(url__regex=r"https://api\.pwnedpasswords\.com/range/.*").mock(
            return_value=httpx.Response(200, text=_hibp_clean_body()),
        )
        # Specific: yeni sifre HIBP'de
        respx.get(_HIBP_RANGE_URL.format(prefix=new_pwned_prefix)).mock(
            return_value=httpx.Response(200, text=_hibp_body_for(new_pwned, 1337)),
        )

        await client.post("/api/v1/auth/register", json={
            "email": "change_pwned@example.com",
            "password": strong,
            "age_confirmed": True,
        })
        await verify_user_email("change_pwned@example.com")
        login = await client.post("/api/v1/auth/login", json={
            "email": "change_pwned@example.com",
            "password": strong,
        })
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = await client.put(
            "/api/v1/user/password",
            json={"current_password": strong, "new_password": new_pwned},
            headers=headers,
        )
    assert resp.status_code == 422
    assert "sizinti" in resp.json()["detail"].lower()


@pytest.mark.password_policy_enabled
@pytest.mark.asyncio
async def test_change_password_strong_succeeds(client: AsyncClient):
    """PUT /user/password guclu + non-pwned yeni sifreyi kabul eder (200)."""
    old_strong = "eski-guclu-sifre-yagmur-K9!-meridyen"
    new_strong = "yepyeni-guclu-sifre-bulut-Q9!-meridyen-7"

    with respx.mock(assert_all_called=False):
        respx.get(url__regex=r"https://api\.pwnedpasswords\.com/range/.*").mock(
            return_value=httpx.Response(200, text=_hibp_clean_body()),
        )
        await client.post("/api/v1/auth/register", json={
            "email": "change_ok@example.com",
            "password": old_strong,
            "age_confirmed": True,
        })
        await verify_user_email("change_ok@example.com")
        login = await client.post("/api/v1/auth/login", json={
            "email": "change_ok@example.com",
            "password": old_strong,
        })
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = await client.put(
            "/api/v1/user/password",
            json={"current_password": old_strong, "new_password": new_strong},
            headers=headers,
        )
    assert resp.status_code == 200
