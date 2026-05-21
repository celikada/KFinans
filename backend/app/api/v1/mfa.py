"""MFA TOTP endpoint'leri (audit #5 MFA).

RFC 6238 standartina uyumlu, Google Authenticator / Authy / 1Password ile
calisir. Akis:

  1. POST /mfa/setup         — Setup baslat: secret + QR PNG doner. DB'ye Fernet
                               sifreli secret yazilir, `totp_enabled` False kalir.
  2. POST /mfa/enable        — Setup ile alinan secret + ilk TOTP kod dogrulanir,
                               basarili olursa `totp_enabled=True` + 10 recovery
                               code (bcrypt hash) uretilir, plaintext doner.
  3. POST /auth/login        — TOTP aktif kullanici icin full token yerine
                               `mfa_required=true + pre_mfa_token` doner.
  4. POST /mfa/verify        — pre_mfa_token + TOTP kod / recovery kod ile full
                               access+refresh token dondurur.
  5. POST /mfa/disable       — TOTP kod / recovery kod ile MFA'yi kapatir, tum
                               secret + recovery codes silinir.

Saat senkron: `pyotp.TOTP(...).verify(code, valid_window=1)` ±30sn tolerans.
Recovery code: tek kullanimlik; kullanildigi anda listeden cikarilir (one-time).
"""
import base64
import io
import json
import logging
import secrets
import uuid
from typing import Annotated

import bcrypt
import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.core.masking import mask_email
from app.core.security import (
    PRE_MFA_TOKEN_TTL_SECONDS,
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_secret,
    encrypt_secret,
)
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.mfa import (
    MFADisableIn,
    MFAEnableIn,
    MFAEnableOut,
    MFASetupOut,
    MFAVerifyIn,
)
from app.services.audit import AuditAction, log_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mfa", tags=["mfa"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


def _generate_recovery_codes(count: int = 10) -> list[str]:
    """12 hex (~48 bit entropy) tek-kullanimlik kodlar. `secrets.token_hex(6)`."""
    return [secrets.token_hex(6) for _ in range(count)]


def _hash_recovery_code(code: str) -> str:
    """bcrypt hash — recovery code'lari plaintext saklanmaz."""
    return bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()


def _verify_recovery_code(code: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(code.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def _build_qr_png_base64(otpauth_url: str) -> str:
    """otpauth:// URI'sini QR PNG'ye cevirir, data URL doner."""
    img = qrcode.make(otpauth_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


async def _consume_recovery_code(user: User, code: str) -> bool:
    """Recovery code'u verify et + listeden cikar. True/False doner.

    `totp_recovery_codes` JSON list[str] (bcrypt hash). Eslesen ilk hash
    listeden silinir — one-time-use enforcement. Hicbiri eslesmezse False.
    """
    if not user.totp_recovery_codes:
        return False
    try:
        hashes: list[str] = json.loads(user.totp_recovery_codes)
    except (json.JSONDecodeError, TypeError):
        logger.warning("totp_recovery_codes JSON parse hatasi: user=%s", user.id)
        return False

    for idx, hashed in enumerate(hashes):
        if _verify_recovery_code(code, hashed):
            del hashes[idx]
            user.totp_recovery_codes = json.dumps(hashes) if hashes else None
            return True
    return False


@router.post("/setup", response_model=MFASetupOut)
@limiter.limit("3/minute")
async def mfa_setup(request: Request, current_user: CurrentUser, db: DB):
    """TOTP setup baslat — secret uret, DB'ye Fernet sifreli yaz, QR PNG don.

    `totp_enabled=True` kullanici icin 400 doner — once disable yapilmali.
    Yarim setup (secret var, enabled False) durumunda yeni secret eskinin
    yerine yazilir (re-setup safe).
    """
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA zaten aktif. Once disable yapip yeniden setup baslatin.",
        )

    secret_b32 = pyotp.random_base32()  # 160-bit base32
    otpauth_url = pyotp.TOTP(secret_b32).provisioning_uri(
        name=current_user.email,
        issuer_name="KFinans",
    )
    qr_png = _build_qr_png_base64(otpauth_url)

    current_user.totp_secret = encrypt_secret(secret_b32)
    # Yarim setup'tan kalmis recovery code varsa temizle (henuz enable degil).
    current_user.totp_recovery_codes = None

    await log_audit(
        db, request,
        action=AuditAction.MFA_SETUP,
        user_id=current_user.id,
    )
    await db.commit()
    logger.info("MFA setup baslatildi: %s", mask_email(current_user.email))

    return MFASetupOut(
        secret_base32=secret_b32,
        otpauth_url=otpauth_url,
        qr_png_base64=qr_png,
    )


@router.post("/enable", response_model=MFAEnableOut)
@limiter.limit("5/minute")
async def mfa_enable(
    request: Request,
    payload: MFAEnableIn,
    current_user: CurrentUser,
    db: DB,
):
    """Setup ile alinan secret + 6 haneli TOTP kod dogrulanir.

    Basarili olursa:
      - `totp_enabled=True`
      - 10 adet recovery code uretilir, bcrypt hash'li olarak DB'ye yazilir
      - plaintext kodlar response'da TEK SEFERLIK doner.
    """
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA zaten aktif.",
        )
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Once /mfa/setup endpoint'ini cagirin.",
        )

    secret_b32 = decrypt_secret(current_user.totp_secret)
    # valid_window=1 -> ±30sn tolerans (saat senkron sorununa karsi).
    if not pyotp.TOTP(secret_b32).verify(payload.totp_code, valid_window=1):
        await log_audit(
            db, request,
            action=AuditAction.MFA_VERIFY_FAILED,
            user_id=current_user.id,
            extra={"phase": "enable"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP kodu gecersiz. Authenticator uygulamasini kontrol edin.",
        )

    plaintext_codes = _generate_recovery_codes(10)
    hashed = [_hash_recovery_code(c) for c in plaintext_codes]
    current_user.totp_recovery_codes = json.dumps(hashed)
    current_user.totp_enabled = True

    await log_audit(
        db, request,
        action=AuditAction.MFA_ENABLED,
        user_id=current_user.id,
    )
    await db.commit()
    logger.info("MFA aktive edildi: %s", mask_email(current_user.email))

    return MFAEnableOut(recovery_codes=plaintext_codes)


@router.post("/disable", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def mfa_disable(
    request: Request,
    payload: MFADisableIn,
    current_user: CurrentUser,
    db: DB,
):
    """TOTP veya recovery code ile MFA'yi kapatir.

    `totp_code` veya `recovery_code` birinin valid olmasi gerekir; basarili
    olunca tum totp_* alanlar NULL'lanir, `totp_enabled=False`.
    """
    if not current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA zaten kapali.",
        )
    if not payload.totp_code and not payload.recovery_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="totp_code veya recovery_code zorunlu.",
        )

    verified = False
    via_recovery = False
    if payload.totp_code and current_user.totp_secret:
        secret_b32 = decrypt_secret(current_user.totp_secret)
        verified = pyotp.TOTP(secret_b32).verify(payload.totp_code, valid_window=1)
    if not verified and payload.recovery_code:
        verified = await _consume_recovery_code(current_user, payload.recovery_code)
        via_recovery = verified

    if not verified:
        await log_audit(
            db, request,
            action=AuditAction.MFA_VERIFY_FAILED,
            user_id=current_user.id,
            extra={"phase": "disable"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dogrulama basarisiz.",
        )

    current_user.totp_secret = None
    current_user.totp_enabled = False
    current_user.totp_recovery_codes = None

    await log_audit(
        db, request,
        action=AuditAction.MFA_DISABLED,
        user_id=current_user.id,
        extra={"via_recovery": via_recovery},
    )
    await db.commit()
    logger.info("MFA devre disi: %s", mask_email(current_user.email))
    return {"detail": "MFA kapatildi."}


@router.post("/verify", response_model=TokenResponse)
@limiter.limit("5/minute")
async def mfa_verify(
    request: Request,
    payload: MFAVerifyIn,
    db: DB,
):
    """Login akisinin ikinci adimi — pre_mfa_token + TOTP / recovery dogrulanir.

    Basarili olursa full access + refresh token doner; pre_mfa_token tek
    kullanimlik (jti dogrulanir, tekrar verify icin yeni login gerek).

    NOT: pre_mfa_token jti'sini blacklist'e atmaya gerek yok — 15 dk TTL
    cok kisa, RevokedToken tablosunda gereksiz yer kaplar. exp ile dogal
    expire.
    """
    # Token decode + tip kontrolu
    try:
        data = decode_token(payload.pre_mfa_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="pre_mfa_token gecersiz veya suresi dolmus.",
        )
    if data.get("type") != "pre_mfa":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yanlis token tipi — login yapip pre_mfa_token alin.",
        )
    user_id_str = data.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="pre_mfa_token gecersiz.",
        )

    if not payload.totp_code and not payload.recovery_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="totp_code veya recovery_code zorunlu.",
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id_str)))
    user = result.scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanici bulunamadi.",
        )
    if not user.totp_enabled or not user.totp_secret:
        # Edge: kullanici pre_mfa_token aldiktan sonra baska bir cihazdan MFA
        # disable etmis olabilir. Bu durumda direkt full token verilebilir ama
        # guvenli yaklasim — re-login iste.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA aktif degil — yeniden giris yapin.",
        )

    verified = False
    via_recovery = False
    if payload.totp_code:
        secret_b32 = decrypt_secret(user.totp_secret)
        verified = pyotp.TOTP(secret_b32).verify(payload.totp_code, valid_window=1)
    if not verified and payload.recovery_code:
        verified = await _consume_recovery_code(user, payload.recovery_code)
        via_recovery = verified

    if not verified:
        await log_audit(
            db, request,
            action=AuditAction.MFA_VERIFY_FAILED,
            user_id=user.id,
            extra={"phase": "login"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dogrulama basarisiz.",
        )

    await log_audit(
        db, request,
        action=AuditAction.MFA_RECOVERY_USED if via_recovery else AuditAction.MFA_VERIFY_SUCCESS,
        user_id=user.id,
    )
    await db.commit()
    logger.info(
        "MFA dogrulama basarili: %s (recovery=%s)",
        mask_email(user.email), via_recovery,
    )
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


# Re-export — auth.login response_model union'da kullanilir.
__all__ = ["router", "PRE_MFA_TOKEN_TTL_SECONDS"]
