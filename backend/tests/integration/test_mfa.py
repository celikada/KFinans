"""MFA TOTP endpoint integration testleri (audit #5 MFA).

Full flow:
  register -> verify_email -> login (no MFA -> tokens)
  -> /mfa/setup -> /mfa/enable -> login (MFA required -> pre_mfa_token)
  -> /mfa/verify (TOTP) -> tokens
Recovery flow ve disable flow ayri testlerde.
"""

import json

import pyotp
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import decrypt_secret
from app.models.user import User
from tests.conftest import TestSession, make_user, verify_user_email


async def _get_user_by_email(email: str) -> User:
    async with TestSession() as session:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one()


async def _setup_and_enable_mfa(client: AsyncClient, headers: dict) -> tuple[str, list[str]]:
    """Helper: /mfa/setup + /mfa/enable yapip (secret_b32, recovery_codes) doner."""
    setup = await client.post("/api/v1/mfa/setup", headers=headers)
    assert setup.status_code == 200
    secret_b32 = setup.json()["secret_base32"]

    totp = pyotp.TOTP(secret_b32)
    enable = await client.post(
        "/api/v1/mfa/enable",
        headers=headers,
        json={"totp_code": totp.now()},
    )
    assert enable.status_code == 200, enable.text
    return secret_b32, enable.json()["recovery_codes"]


@pytest.mark.asyncio
async def test_mfa_setup_returns_secret_and_qr(client: AsyncClient):
    headers = await make_user(client, "mfa_setup@example.com")
    resp = await client.post("/api/v1/mfa/setup", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # base32 secret
    assert len(data["secret_base32"]) == 32
    # otpauth URI
    assert data["otpauth_url"].startswith("otpauth://totp/KFinans:mfa_setup@example.com")
    # QR PNG data URL
    assert data["qr_png_base64"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_mfa_setup_persists_encrypted_secret(client: AsyncClient):
    email = "mfa_setup2@example.com"
    headers = await make_user(client, email)
    setup = await client.post("/api/v1/mfa/setup", headers=headers)
    secret_b32 = setup.json()["secret_base32"]

    user = await _get_user_by_email(email)
    assert user.totp_secret is not None
    # DB'de plaintext degil — ciphertext
    assert user.totp_secret != secret_b32
    # Decrypt edince original secret donmeli
    assert decrypt_secret(user.totp_secret) == secret_b32
    # Henuz enable degil
    assert user.totp_enabled is False


@pytest.mark.asyncio
async def test_mfa_enable_with_valid_code_grants_recovery_codes(client: AsyncClient):
    headers = await make_user(client, "mfa_enable@example.com")
    _, recovery_codes = await _setup_and_enable_mfa(client, headers)

    assert len(recovery_codes) == 10
    assert len(set(recovery_codes)) == 10  # tum kodlar farkli
    for c in recovery_codes:
        assert len(c) == 12


@pytest.mark.asyncio
async def test_mfa_enable_with_invalid_code_rejected(client: AsyncClient):
    headers = await make_user(client, "mfa_invalid@example.com")
    await client.post("/api/v1/mfa/setup", headers=headers)
    resp = await client.post(
        "/api/v1/mfa/enable",
        headers=headers,
        json={"totp_code": "000000"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_mfa_enable_without_setup_rejected(client: AsyncClient):
    headers = await make_user(client, "mfa_nosetup@example.com")
    resp = await client.post(
        "/api/v1/mfa/enable",
        headers=headers,
        json={"totp_code": "123456"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_with_mfa_enabled_returns_pre_mfa_token(client: AsyncClient):
    email = "mfa_login@example.com"
    pwd = "guclu-sifre-123"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "age_confirmed": True},
    )
    await verify_user_email(email)
    login1 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    headers = {"Authorization": f"Bearer {login1.json()['access_token']}"}

    await _setup_and_enable_mfa(client, headers)

    # 2. login — MFA aktif, full token gelmemeli
    login2 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert login2.status_code == 200
    body = login2.json()
    assert body.get("mfa_required") is True
    assert "pre_mfa_token" in body
    assert body["expires_in_seconds"] == 15 * 60
    assert "access_token" not in body
    assert "refresh_token" not in body


@pytest.mark.asyncio
async def test_mfa_verify_with_valid_totp_returns_full_tokens(client: AsyncClient):
    email = "mfa_verify@example.com"
    pwd = "guclu-sifre-123"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "age_confirmed": True},
    )
    await verify_user_email(email)
    login1 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    headers = {"Authorization": f"Bearer {login1.json()['access_token']}"}

    secret_b32, _ = await _setup_and_enable_mfa(client, headers)

    # MFA aktif login
    login2 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    pre_mfa = login2.json()["pre_mfa_token"]

    # Verify TOTP
    totp = pyotp.TOTP(secret_b32)
    verify = await client.post(
        "/api/v1/mfa/verify",
        json={"pre_mfa_token": pre_mfa, "totp_code": totp.now()},
    )
    assert verify.status_code == 200, verify.text
    body = verify.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_mfa_verify_with_invalid_totp_rejected(client: AsyncClient):
    email = "mfa_verify_bad@example.com"
    pwd = "guclu-sifre-123"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "age_confirmed": True},
    )
    await verify_user_email(email)
    login1 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    headers = {"Authorization": f"Bearer {login1.json()['access_token']}"}
    await _setup_and_enable_mfa(client, headers)

    login2 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    pre_mfa = login2.json()["pre_mfa_token"]

    resp = await client.post(
        "/api/v1/mfa/verify",
        json={"pre_mfa_token": pre_mfa, "totp_code": "000000"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mfa_verify_recovery_code_consumes_it(client: AsyncClient):
    """Recovery code tek kullanimlik — ayni kod ikinci kez calismaz."""
    email = "mfa_recovery@example.com"
    pwd = "guclu-sifre-123"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "age_confirmed": True},
    )
    await verify_user_email(email)
    login1 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    headers = {"Authorization": f"Bearer {login1.json()['access_token']}"}
    _, recovery_codes = await _setup_and_enable_mfa(client, headers)
    first_code = recovery_codes[0]

    # Birinci login + recovery
    login2 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    pre_mfa1 = login2.json()["pre_mfa_token"]
    v1 = await client.post(
        "/api/v1/mfa/verify",
        json={"pre_mfa_token": pre_mfa1, "recovery_code": first_code},
    )
    assert v1.status_code == 200

    # DB'de bu hash artik yok — kalan 9 kod
    user = await _get_user_by_email(email)
    remaining = json.loads(user.totp_recovery_codes)
    assert len(remaining) == 9

    # Ikinci login + ayni recovery code -> reddedilir
    login3 = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    pre_mfa2 = login3.json()["pre_mfa_token"]
    v2 = await client.post(
        "/api/v1/mfa/verify",
        json={"pre_mfa_token": pre_mfa2, "recovery_code": first_code},
    )
    assert v2.status_code == 401


@pytest.mark.asyncio
async def test_mfa_verify_invalid_pre_mfa_token(client: AsyncClient):
    resp = await client.post(
        "/api/v1/mfa/verify",
        json={"pre_mfa_token": "not-a-valid-jwt", "totp_code": "123456"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mfa_verify_wrong_token_type(client: AsyncClient):
    """Access token pre_mfa_token olarak kullanilamaz."""
    headers = await make_user(client, "mfa_wrongtype@example.com")
    access = headers["Authorization"].split(" ", 1)[1]
    resp = await client.post(
        "/api/v1/mfa/verify",
        json={"pre_mfa_token": access, "totp_code": "123456"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mfa_disable_with_totp_clears_secret(client: AsyncClient):
    email = "mfa_disable@example.com"
    headers = await make_user(client, email)
    secret_b32, _ = await _setup_and_enable_mfa(client, headers)

    totp = pyotp.TOTP(secret_b32)
    resp = await client.post(
        "/api/v1/mfa/disable",
        headers=headers,
        json={"totp_code": totp.now()},
    )
    assert resp.status_code == 200

    user = await _get_user_by_email(email)
    assert user.totp_secret is None
    assert user.totp_enabled is False
    assert user.totp_recovery_codes is None


@pytest.mark.asyncio
async def test_mfa_disable_with_recovery_code(client: AsyncClient):
    email = "mfa_disable_recovery@example.com"
    headers = await make_user(client, email)
    _, recovery_codes = await _setup_and_enable_mfa(client, headers)

    resp = await client.post(
        "/api/v1/mfa/disable",
        headers=headers,
        json={"recovery_code": recovery_codes[0]},
    )
    assert resp.status_code == 200

    user = await _get_user_by_email(email)
    assert user.totp_enabled is False


@pytest.mark.asyncio
async def test_mfa_disable_without_code_422(client: AsyncClient):
    headers = await make_user(client, "mfa_disable_noargs@example.com")
    await _setup_and_enable_mfa(client, headers)
    resp = await client.post("/api/v1/mfa/disable", headers=headers, json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_mfa_setup_when_already_enabled_rejected(client: AsyncClient):
    headers = await make_user(client, "mfa_double_setup@example.com")
    await _setup_and_enable_mfa(client, headers)
    resp = await client.post("/api/v1/mfa/setup", headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_without_mfa_returns_tokens_unchanged(client: AsyncClient):
    """MFA aktif olmayan kullanici icin login davranisi degismedi."""
    headers = await make_user(client, "no_mfa@example.com")
    # Headers zaten basarili login'den geldi — mfa_required olmamali.
    assert headers["Authorization"].startswith("Bearer ")
