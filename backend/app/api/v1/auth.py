import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.core.masking import mask_email
from app.core.password_policy import check_hibp_pwned, check_password_strength
from app.core.security import (
    PRE_MFA_TOKEN_TTL_SECONDS,
    create_access_token,
    create_pre_mfa_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.mfa import MFALoginRequiredOut
from app.services.audit import AuditAction, log_audit
from app.services.email import send_password_reset_email, send_verification_email

_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# SEC-002 (FAZ H): Account lockout esikleri.
# 10 ust uste basarisiz login = 15 dakika kilit (OWASP ASVS V2.2.1).
_FAILED_LOGIN_THRESHOLD = 10
_LOCK_DURATION = timedelta(minutes=15)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _new_verify_token() -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.verify_token_expire_hours)
    return token, expires_at


def _new_reset_token() -> tuple[str, datetime]:
    """SEC-001 (FAZ H): secrets.token_urlsafe(32) — 256 bit random; URL-safe.
    Default 1 saat TTL (OWASP onerisi)."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.password_reset_expire_hours)
    return token, expires_at


async def _raise_if_locked(db: AsyncSession, request: Request, user: User | None, email: str) -> None:
    """SEC-002 (FAZ H): Account lockout — locked_until > now ise direkt 423.

    Bu kontrol parola dogrulamasindan ONCE; saldirgan kilit suresi icinde
    yeni denemeler yaparak counter'i kabartamaz.
    """
    if not (user and user.locked_until and user.locked_until > datetime.now(timezone.utc)):
        return
    retry_seconds = int((user.locked_until - datetime.now(timezone.utc)).total_seconds())
    logger.warning(
        "Kilitli hesap login denedi: %s (kalan=%ssn)",
        mask_email(email),
        retry_seconds,
    )
    await log_audit(
        db,
        request,
        action=AuditAction.LOGIN_FAILED,
        user_id=user.id,
        extra={"email": mask_email(email), "reason": "locked"},
    )
    await db.commit()
    raise HTTPException(
        status_code=status.HTTP_423_LOCKED,
        detail=f"Hesap guvenlik nedeniyle gecici kilitli. Lutfen {retry_seconds // 60 + 1} dk sonra deneyin.",
        headers={"Retry-After": str(retry_seconds)},
    )


async def _handle_failed_login(db: AsyncSession, request: Request, user: User | None, email: str) -> None:
    """SEC-002 (FAZ H): Basarisiz login — counter artir, threshold'da kilitle,
    audit'le ve 401 firlat."""
    logger.warning("Başarısız giriş denemesi: %s", mask_email(email))
    # User varsa counter'i artir; threshold'u asarsa kilitle.
    if user:
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= _FAILED_LOGIN_THRESHOLD:
            user.locked_until = datetime.now(timezone.utc) + _LOCK_DURATION
            logger.warning(
                "Account lockout: %s (%s deneme)",
                mask_email(email),
                user.failed_login_count,
            )
    # Failed login audit (user_id=None — anonim, hesap olabilir/olmayabilir)
    await log_audit(
        db,
        request,
        action=AuditAction.LOGIN_FAILED,
        user_id=user.id if user else None,
        extra={
            "email": mask_email(email),
            "failed_count": user.failed_login_count if user else None,
            "locked": bool(user and user.locked_until),
        },
    )
    await db.commit()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya şifre hatalı")


@router.post("/login", response_model=TokenResponse | MFALoginRequiredOut)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, db: DB):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    await _raise_if_locked(db, request, user, payload.email)

    if not user or not verify_password(payload.password, user.password_hash):
        await _handle_failed_login(db, request, user, payload.email)
    if not user.email_verified:
        logger.info("Doğrulanmamış kullanıcı giriş denedi: %s", mask_email(payload.email))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-posta adresiniz henüz doğrulanmadı. Lütfen gelen kutunuzu kontrol edin.",
        )

    # SEC-002: Basarili login -> counter sifirla (kilit suresi gecmis ve dogru parola).
    if user.failed_login_count or user.locked_until:
        user.failed_login_count = 0
        user.locked_until = None

    # MFA — TOTP aktif kullanici icin full token yerine pre_mfa_token doner.
    # Frontend /mfa/verify endpoint'ine yonlendirir. (audit #5 MFA)
    if user.totp_enabled:
        logger.info("MFA gerekli — login adim 1: %s", mask_email(payload.email))
        await log_audit(
            db,
            request,
            action=AuditAction.LOGIN_MFA_REQUIRED,
            user_id=user.id,
        )
        await db.commit()
        return MFALoginRequiredOut(
            mfa_required=True,
            pre_mfa_token=create_pre_mfa_token(str(user.id)),
            expires_in_seconds=PRE_MFA_TOKEN_TTL_SECONDS,
        )

    logger.info("Kullanıcı giriş yaptı: %s", mask_email(payload.email))
    await log_audit(
        db,
        request,
        action=AuditAction.LOGIN,
        user_id=user.id,
    )
    await db.commit()
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(request: Request, payload: RefreshRequest, db: DB):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token türü")
        user_id = data.get("sub")
        jti = data.get("jti")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")

    # Logout sonrasi iptal edilmis refresh token kabul edilmez
    if jti:
        revoked = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        if revoked.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token iptal edilmiş",
            )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı")

    # ─── Refresh token rotation (FAZ C4) ────────────────────────────────
    # Eski refresh'in jti'sini blacklist'e at — sizan refresh token'in
    # ikinci kez kullanilmasi engellenir. expires_at TTL kontrol icin
    # cleanup cron'da (FAZ C5) silinir.
    if jti and "exp" in data:
        db.add(
            RevokedToken(
                jti=jti,
                user_id=user.id,
                token_type="refresh",
                expires_at=datetime.fromtimestamp(data["exp"], tz=timezone.utc),
            )
        )
        try:
            await db.commit()
        except IntegrityError:
            # Idempotency: ayni token paralel iki istekte rotate edilirse
            # PK cakismasi olabilir. Rollback yapip yeni token uretmeye devam.
            await db.rollback()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    payload: LogoutRequest,
    access_token: Annotated[str, Depends(_oauth2)],
    current_user: CurrentUser,
    db: DB,
):
    """Header'daki access token'i ve (varsa) body'deki refresh token'i blacklist'e alir.

    Idempotent: ayni token tekrar logout edilirse JSON 200 doner; PRIMARY KEY
    cakismasi olursa rollback yapilip basarili sayilir.
    """
    # Access token (zaten get_current_user dogruladi)
    try:
        access_payload = decode_token(access_token)
        access_jti = access_payload.get("jti")
        if access_jti:
            db.add(
                RevokedToken(
                    jti=access_jti,
                    user_id=current_user.id,
                    token_type="access",
                    expires_at=datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc),
                )
            )
    except JWTError:
        pass  # get_current_user gecmisti zaten; ulasilmamali

    # Refresh token (opsiyonel)
    if payload.refresh_token:
        try:
            refresh_payload = decode_token(payload.refresh_token)
            if refresh_payload.get("type") == "refresh" and refresh_payload.get("sub") == str(current_user.id) and refresh_payload.get("jti"):
                db.add(
                    RevokedToken(
                        jti=refresh_payload["jti"],
                        user_id=current_user.id,
                        token_type="refresh",
                        expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
                    )
                )
        except JWTError:
            pass  # Gecersiz refresh token; sessizce yutulur

    # Audit log (commit oncesi flush'lanir, ana commit ile birlikte gider)
    await log_audit(
        db,
        request,
        action=AuditAction.LOGOUT,
        user_id=current_user.id,
    )

    try:
        await db.commit()
    except Exception:
        # Idempotency: aynI jti tekrar logout edilirse PK cakismasI olur
        await db.rollback()

    logger.info("Kullanıcı çıkış yaptı: %s", mask_email(current_user.email))
    return {"detail": "Çıkış yapıldı"}


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, payload: RegisterRequest, db: DB):
    # COMP-010 (FAZ H): 18+ yas dogrulama (KVKK 2018/482, TMK m.16).
    # Frontend register form'unda zorunlu checkbox; eksik/False ise reddet.
    if not payload.age_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kayit icin 18 yasini doldurmus olmaniz gerekir.",
        )

    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten kayıtlı")

    # SEC (audit #5): Sifre politikasi — zxcvbn + HIBP.
    # User inputs: email (local-part + tam adres). Kullanici "ada@x.com" ile
    # "ada123" sifresi sektigi zaman zxcvbn score'u kirilir.
    email_local = payload.email.split("@", 1)[0]
    is_strong, error_msg = check_password_strength(
        payload.password,
        user_inputs=[payload.email, email_local],
    )
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )
    leaked_count = await check_hibp_pwned(payload.password)
    if leaked_count >= 1:
        # PII guvenli: leaked_count log'lanir, sifre DEGIL
        logger.info(
            "Sizmis sifre reddedildi (register): email=%s leaked_count=%s",
            mask_email(payload.email),
            leaked_count,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("Bu sifre bilinen veri sizintilarinda bulundu. Lutfen baska bir sifre secin."),
        )

    token, expires_at = _new_verify_token()
    # COMP-006 (FAZ H): Acik rizalar timestamp'le kaydedilir (KVKK m.5/1 ispat yuku).
    # Eksik/False ise NULL kalir; opsiyonel rizalar (overseas) NULL durumunda
    # advice endpoint'i 403 doner.
    now = datetime.now(timezone.utc)
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        risk_profile=payload.risk_profile,
        verify_token=token,
        verify_token_expires_at=expires_at,
        overseas_consent_at=now if payload.overseas_consent else None,
        terms_accepted_at=now if payload.terms_accepted else None,
        kvkk_read_at=now if payload.kvkk_read else None,
        # Surum bildirimleri: opt-in acik riza (varsayilan False). unsubscribe_token
        # her kullaniciya kalici uretilir — opt-in olmasa bile sonradan acabilir.
        release_notes_opt_in=payload.release_notes_opt_in,
        unsubscribe_token=secrets.token_urlsafe(32),
    )
    db.add(user)
    await db.flush()  # user.id'yi al
    await log_audit(
        db,
        request,
        action=AuditAction.REGISTER,
        user_id=user.id,
        extra={"email": mask_email(payload.email), "risk_profile": payload.risk_profile},
    )
    await db.commit()
    await db.refresh(user)
    logger.info("Yeni kullanıcı kaydı: %s", mask_email(payload.email))

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
    token: Annotated[str, Query(min_length=10, max_length=128)],
    db: DB,
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
    logger.info("E-posta doğrulandı: %s", mask_email(user.email))
    return {"detail": "E-posta başarıyla doğrulandı"}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    db: DB,
):
    """Doğrulama e-postasını yeniden gönderir. Bilgi sızdırmayı önlemek için
    kullanıcı bulunmasa veya zaten doğrulanmış olsa bile aynı yanıtı döner."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Bilgi sizdirmamak icin kullanici yoksa/dogrulanmissa sessizce gec —
    # her durumda ayni generic 202 doner (anti-enumeration).
    if user and not user.email_verified:
        token, expires_at = _new_verify_token()
        user.verify_token = token
        user.verify_token_expires_at = expires_at
        await db.commit()
        await send_verification_email(to=user.email, token=token)

    return {"detail": "Doğrulama e-postası gönderilecek"}


# ─── SEC-001 (FAZ H): Password reset (OWASP Forgot Password Cheat Sheet) ───


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: DB,
):
    """Sifre sifirlama e-postasi gonderir. Bilgi sizdirmamak icin kullanici
    bulunmasa veya silinmis olsa bile generic 202 doner. Audit log her durumda
    yazilir (email payload'da) — saldirgan kullanici listesi cikaramaz.

    Token rotation: ayni email icin yeni istek eski token'i gecersiz kilar.
    """
    generic_response = {"detail": "Sifre sifirlama e-postasi gonderilecek"}

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Audit her durumda yazilir (saldirgan email listesi cikaramaz)
    await log_audit(
        db,
        request,
        action=AuditAction.PASSWORD_RESET_REQUEST,
        user_id=user.id if user else None,
        extra={"email": mask_email(payload.email), "user_exists": bool(user)},
    )

    # Sadece var olan + dogrulanmis + silinmemis kullanici icin token uret
    if user and user.email_verified and user.deleted_at is None:
        token, expires_at = _new_reset_token()
        user.reset_token = token
        user.reset_token_expires_at = expires_at
        await db.commit()
        await send_password_reset_email(to=user.email, token=token)
    else:
        await db.commit()

    return generic_response


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: DB,
):
    """Token ile yeni sifre belirler. Tek kullanimlik — token + expiry tuketilir.

    400 token gecersiz/expire (timing-safe degil ama enumerasyon icin generic
    mesaj — saldirgan eposta varligi cikaramaz).
    """
    result = await db.execute(select(User).where(User.reset_token == payload.token))
    user = result.scalar_one_or_none()

    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < datetime.now(timezone.utc):
        # Audit anonim — token'i kim denedi izlenir
        await log_audit(
            db,
            request,
            action=AuditAction.PASSWORD_RESET_COMPLETE,
            user_id=user.id if user else None,
            extra={"success": False, "reason": "invalid_or_expired_token"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sifirlama bagsantisi gecersiz ya da suresi dolmus.",
        )

    # SEC (audit #5): Reset akisinda da policy uygulanir — eski sifre crackleninse
    # bile kullanici "password123" gibi zayif sifreye geri donemez.
    email_local = user.email.split("@", 1)[0]
    is_strong, error_msg = check_password_strength(
        payload.new_password,
        user_inputs=[user.email, email_local],
    )
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )
    leaked_count = await check_hibp_pwned(payload.new_password)
    if leaked_count >= 1:
        logger.info(
            "Sizmis sifre reddedildi (reset): email=%s leaked_count=%s",
            mask_email(user.email),
            leaked_count,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("Bu sifre bilinen veri sizintilarinda bulundu. Lutfen baska bir sifre secin."),
        )

    user.password_hash = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    # SEC-002 ile uyum: sifre degistiginde lockout state'i de sifirla
    user.failed_login_count = 0
    user.locked_until = None

    await log_audit(
        db,
        request,
        action=AuditAction.PASSWORD_RESET_COMPLETE,
        user_id=user.id,
        extra={"success": True, "email": mask_email(user.email)},
    )
    await db.commit()
    logger.info("Sifre sifirlandi: %s", mask_email(user.email))
    return {"detail": "Sifre basariyla degistirildi. Yeni sifrenizle giris yapabilirsiniz."}
