import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_db
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
)
from app.services.email import send_verification_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _new_verify_token() -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.verify_token_expire_hours)
    return token, expires_at


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        logger.warning("Başarısız giriş denemesi: %s", payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya şifre hatalı")
    if not user.email_verified:
        logger.info("Doğrulanmamış kullanıcı giriş denedi: %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-posta adresiniz henüz doğrulanmadı. Lütfen gelen kutunuzu kontrol edin.",
        )
    logger.info("Kullanıcı giriş yaptı: %s", payload.email)
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(request: Request, payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token türü")
        user_id = data.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten kayıtlı")

    token, expires_at = _new_verify_token()
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        risk_profile=payload.risk_profile,
        verify_token=token,
        verify_token_expires_at=expires_at,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Yeni kullanıcı kaydı: %s", payload.email)

    sent = await send_verification_email(to=user.email, token=token)
    return RegisterResponse(
        id=user.id,
        email=user.email,
        risk_profile=user.risk_profile,
        email_verified=user.email_verified,
        verification_email_sent=sent,
    )


@router.get("/verify-email")
@limiter.limit("20/minute")
async def verify_email(
    request: Request,
    token: str = Query(..., min_length=10, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.verify_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doğrulama bağlantısı geçersiz",
        )
    if user.email_verified:
        return {"detail": "E-posta zaten doğrulanmış"}
    if not user.verify_token_expires_at or user.verify_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doğrulama bağlantısının süresi dolmuş. Lütfen yeniden gönderin.",
        )

    user.email_verified = True
    user.verify_token = None
    user.verify_token_expires_at = None
    await db.commit()
    logger.info("E-posta doğrulandı: %s", user.email)
    return {"detail": "E-posta başarıyla doğrulandı"}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Doğrulama e-postasını yeniden gönderir. Bilgi sızdırmayı önlemek için
    kullanıcı bulunmasa veya zaten doğrulanmış olsa bile aynı yanıtı döner."""
    generic_response = {"detail": "Doğrulama e-postası gönderilecek"}

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or user.email_verified:
        return generic_response

    token, expires_at = _new_verify_token()
    user.verify_token = token
    user.verify_token_expires_at = expires_at
    await db.commit()

    await send_verification_email(to=user.email, token=token)
    return generic_response
