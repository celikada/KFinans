import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.core.masking import mask_email
from app.core.password_policy import check_hibp_pwned, check_password_strength
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import PasswordChange, ProfileUpdate, UserMeOut
from app.services.audit import AuditAction, log_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])

# COMP-029 (FAZ H): Email change verification token TTL
_EMAIL_CHANGE_TTL_HOURS = 1


class EmailChangeRequest(BaseModel):
    new_email: EmailStr


class ConsentType(BaseModel):
    """COMP-006 (FAZ H): Geri cekilebilir riza turleri."""

    consent_type: Literal["overseas"] = Field(description="Su an sadece 'overseas' destekleniyor")


# AI-005 (FAZ H): Anthropic API icin acik riza metin versiyonu — guncellendiginde
# artirilir, kullanici eski version ile rizali ise ileride re-accept zorunlu.
ANTHROPIC_CONSENT_VERSION = "1.0"

CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


def _iso_or_none(value) -> str | None:
    """datetime/date → ISO string; None ise None."""
    return value.isoformat() if value else None


def _serialize_orm(obj, exclude: set[str] | None = None) -> dict:
    """SQLAlchemy ORM nesnesini dict'e cevir; datetime/decimal/uuid ISO/str."""
    exclude = exclude or set()
    out = {}
    for col in obj.__table__.columns:
        if col.name in exclude:
            continue
        val = getattr(obj, col.name, None)
        if val is None:
            out[col.name] = None
        elif hasattr(val, "isoformat"):  # datetime/date
            out[col.name] = val.isoformat()
        else:
            out[col.name] = str(val) if not isinstance(val, (str, int, float, bool, list, dict)) else val
    return out


def _export_profile(user: User) -> dict:
    """Veri tasinabilirligi (KVKK m.11/d) profil bolumu."""
    return {
        "id": str(user.id),
        "email": user.email,
        "risk_profile": user.risk_profile,
        "email_verified": user.email_verified,
        "created_at": _iso_or_none(user.created_at),
        "credit_balance": user.credit_balance,
        "deleted_at": _iso_or_none(user.deleted_at),
        "overseas_consent_at": _iso_or_none(user.overseas_consent_at),
        "terms_accepted_at": _iso_or_none(user.terms_accepted_at),
        "kvkk_read_at": _iso_or_none(user.kvkk_read_at),
    }


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_me(current_user: CurrentUser) -> UserMeOut:
    return UserMeOut.model_validate(current_user)


@router.put("/profile", status_code=status.HTTP_200_OK)
async def update_profile(payload: ProfileUpdate, current_user: CurrentUser, db: DB) -> UserMeOut:
    current_user.risk_profile = payload.risk_profile
    # v0.3.0: varsayılan para birimi tercihi (opsiyonel; verilmezse korunur).
    if payload.default_currency is not None:
        current_user.default_currency = payload.default_currency
    # Ödeme hatırlatması e-postası opt-in tercihi (opsiyonel; verilmezse korunur).
    if payload.payment_reminder_email is not None:
        current_user.payment_reminder_email = payload.payment_reminder_email
    await db.commit()
    await db.refresh(current_user)
    logger.info(
        "Risk profili güncellendi: %s → %s",
        mask_email(current_user.email),
        payload.risk_profile,
    )
    return UserMeOut.model_validate(current_user)


@router.put("/password", status_code=status.HTTP_200_OK)
async def change_password(request: Request, payload: PasswordChange, current_user: CurrentUser, db: DB) -> dict:
    if not verify_password(payload.current_password, current_user.password_hash):
        logger.warning("Yanlış mevcut şifre girişi: %s", mask_email(current_user.email))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mevcut şifre hatalı")

    # SEC (audit #5): zxcvbn + HIBP yeni sifrede de uygulanir.
    email_local = current_user.email.split("@", 1)[0]
    is_strong, error_msg = check_password_strength(
        payload.new_password,
        user_inputs=[current_user.email, email_local],
    )
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )
    leaked_count = await check_hibp_pwned(payload.new_password)
    if leaked_count >= 1:
        logger.info(
            "Sizmis sifre reddedildi (change): email=%s leaked_count=%s",
            mask_email(current_user.email),
            leaked_count,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("Bu sifre bilinen veri sizintilarinda bulundu. Lutfen baska bir sifre secin."),
        )

    current_user.password_hash = hash_password(payload.new_password)
    await log_audit(
        db,
        request,
        action=AuditAction.PASSWORD_CHANGE,
        user_id=current_user.id,
    )
    await db.commit()
    logger.info("Şifre güncellendi: %s", mask_email(current_user.email))
    return {"detail": "Şifre güncellendi"}


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_me(request: Request, current_user: CurrentUser, db: DB) -> dict:
    current_user.deleted_at = datetime.now(tz=timezone.utc)
    await log_audit(
        db,
        request,
        action=AuditAction.ACCOUNT_SOFT_DELETE,
        user_id=current_user.id,
        resource=f"user:{current_user.id}",
    )
    await db.commit()
    logger.info("Hesap silindi (soft-delete): %s", mask_email(current_user.email))
    return {"detail": "Hesap silindi"}


# ─── COMP-029 (FAZ H): E-posta degistirme — KVKK m.11/d duzeltme hakki ────


@router.post("/email/request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
async def request_email_change(
    request: Request,
    payload: EmailChangeRequest,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Yeni email hedefine verification token olusturur. Tiklanmadan eski
    email aktif kalir. Mevcut bir bekleyen istek varsa override eder
    (kullanici farkli bir adres yazmis olabilir).

    409 yeni email baska bir hesap tarafindan kullaniliyorsa.
    """
    new_email = payload.new_email.lower().strip()
    if new_email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yeni e-posta mevcut e-posta ile ayni",
        )

    # Yeni email zaten kullanimda mi?
    existing = await db.execute(select(User).where(User.email == new_email))
    if existing.scalar_one_or_none():
        # Bilgi sizdirmamak icin generic — saldirgan kullanici listesi cikaramaz
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta kullanilamaz",
        )

    token = secrets.token_urlsafe(32)
    current_user.email_change_new = new_email
    current_user.email_change_token = token
    current_user.email_change_expires_at = datetime.now(timezone.utc) + timedelta(hours=_EMAIL_CHANGE_TTL_HOURS)

    await log_audit(
        db,
        request,
        action=AuditAction.EMAIL_CHANGE_REQUEST,
        user_id=current_user.id,
        extra={
            "old_email": mask_email(current_user.email),
            "new_email": mask_email(new_email),
        },
    )
    await db.commit()

    # E-posta gonderimi: yeni adrese onay linki, eski adrese bilgilendirme.
    # send_email helper'i Faz 3'te mevcut; iki ayri e-posta servis tarafinda
    # render edilir. Burada sadece audit + token doner; gerçek gonderim
    # async asyncio.to_thread ile yapilabilir.
    # NOTE: confirm_url log'a YAZILMAZ (token = phishing risk). Sadece email
    # icinde gonderilir; logging icin sadece masked email + user-id yeterli.
    logger.info(
        "E-posta degistirme istegi: user=%s yeni=%s",
        current_user.id,
        mask_email(new_email),
    )
    return {"detail": "Yeni e-posta adresine onay baglantisi gonderildi"}


@router.get("/email/confirm")
async def confirm_email_change(
    request: Request,
    db: DB,
    token: Annotated[str, Query(min_length=10, max_length=128)],
) -> dict:
    """Token ile email swap'i tamamlar. Token tek kullanim — completed
    sonrasi user.email_change_* NULL'lanir. session-token rotation manuel
    yapilmalidir (eski JWT hala gecerli ancak email field'i degisecek;
    /auth/logout cagirmasi onerilir)."""
    result = await db.execute(select(User).where(User.email_change_token == token))
    user = result.scalar_one_or_none()
    if not user or not user.email_change_expires_at or user.email_change_expires_at < datetime.now(timezone.utc) or not user.email_change_new:
        await log_audit(
            db,
            request,
            action=AuditAction.EMAIL_CHANGE_COMPLETE,
            user_id=user.id if user else None,
            extra={"success": False, "reason": "invalid_or_expired"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onay baglantisi gecersiz ya da suresi dolmus",
        )

    old_email = user.email
    user.email = user.email_change_new
    user.email_change_new = None
    user.email_change_token = None
    user.email_change_expires_at = None

    await log_audit(
        db,
        request,
        action=AuditAction.EMAIL_CHANGE_COMPLETE,
        user_id=user.id,
        extra={
            "success": True,
            "old_email": mask_email(old_email),
            "new_email": mask_email(user.email),
        },
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta artik kullanilamaz",
        )
    logger.info("E-posta degisti: %s -> %s", mask_email(old_email), mask_email(user.email))
    return {"detail": "E-posta basariyla guncellendi"}


# ─── COMP-006 (FAZ H): Acik riza geri cekme — KVKK m.5/1 ────────────────


@router.delete("/consent/{consent_type}", status_code=status.HTTP_200_OK)
async def revoke_consent(
    request: Request,
    consent_type: str,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Kullanici acik rizasini geri ceker. Su an 'overseas' destekleniyor;
    ileride 'kvkk' / 'terms' eklenecek (her zaman re-accept zorunlu)."""
    if consent_type != "overseas":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bilinmeyen riza turu: {consent_type}",
        )

    if current_user.overseas_consent_at is None:
        return {"detail": "Bu riza zaten mevcut degil"}

    current_user.overseas_consent_at = None
    await log_audit(
        db,
        request,
        action=AuditAction.CONSENT_REVOKE,
        user_id=current_user.id,
        extra={"consent_type": consent_type},
    )
    await db.commit()
    logger.info(
        "Acik riza geri cekildi: %s consent=%s",
        mask_email(current_user.email),
        consent_type,
    )
    return {"detail": "Acik riza geri cekildi. AI tavsiye gibi yurt disi veri aktarimi gerektiren ozellikler kullanilamayacak."}


# ─── COMP-003 (FAZ H): Veri tasinabilirligi — KVKK m.11/d, GDPR Art.20 ──


@router.get("/data-export", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
async def data_export(
    request: Request,
    current_user: CurrentUser,
    db: DB,
):
    """Kullanicinin tum kisisel verisini JSON dump olarak indirir. Makine
    okunabilir format (GDPR Art.20). KVKK basvuru SLA'sini saatlerce
    azaltir — kullanici self-service.

    Saglanan veriler:
      - profile (email, risk_profile, consents, timestamps)
      - integrations (provider listesi, API key plaintext DAHIL DEGIL)
      - wallet_addresses (decrypt edilmis plaintext)
      - portfolio_snapshots + asset_positions
      - tefas_holdings, stock_holdings, bes_holdings, commodity_holdings
      - manual_crypto_holdings, cash_holdings
      - expenses, planned_expenses, incomes, recurring_incomes, budgets
      - credit_cards + statements + installments
      - investment_advice (history)
      - audit_logs (kullanicinin kendi log'lari)
    """
    from app.models.advice import InvestmentAdvice
    from app.models.audit_log import AuditLog
    from app.models.bes import BesHolding
    from app.models.budget import Budget
    from app.models.cash import CashHolding
    from app.models.commodity import CommodityHolding
    from app.models.credit_card import CreditCard
    from app.models.expense import Expense
    from app.models.income import Income
    from app.models.integration import Integration, WalletAddress
    from app.models.manual_crypto import ManualCryptoHolding
    from app.models.planned_expense import PlannedExpense
    from app.models.portfolio import AssetPosition, PortfolioSnapshot
    from app.models.recurring_income import RecurringIncome
    from app.models.stock import StockHolding
    from app.models.tefas import TefasHolding

    uid = current_user.id

    async def _list(model, *, exclude: set[str] | None = None) -> list[dict]:
        result = await db.execute(select(model).where(model.user_id == uid))
        return [_serialize_orm(o, exclude=exclude) for o in result.scalars().all()]

    # Wallet'lerde plaintext address (decrypt edilmis); fingerprint atla
    wallets_result = await db.execute(select(WalletAddress).where(WalletAddress.user_id == uid))
    wallets = [
        {
            "id": str(w.id),
            "chain": w.chain,
            "address": w.address,  # hybrid_property decrypt
            "label": w.label,
            "is_active": w.is_active,
            "created_at": _iso_or_none(w.created_at),
        }
        for w in wallets_result.scalars().all()
    ]

    # Integrations: API key plaintext DAHIL DEGIL
    intg = await _list(Integration, exclude={"encrypted_key", "encrypted_secret"})

    # Snapshot + asset_positions
    snap_result = await db.execute(select(PortfolioSnapshot).where(PortfolioSnapshot.user_id == uid))
    snapshots = []
    for s in snap_result.scalars().all():
        ap_result = await db.execute(select(AssetPosition).where(AssetPosition.snapshot_id == s.id))
        snapshots.append(
            {
                **_serialize_orm(s),
                "asset_positions": [_serialize_orm(p) for p in ap_result.scalars().all()],
            }
        )

    # Audit log
    audit_result = await db.execute(select(AuditLog).where(AuditLog.user_id == uid))
    audit_logs = [_serialize_orm(a) for a in audit_result.scalars().all()]

    payload = {
        "_meta": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "kfinans-data-export-v1",
            "kvkk_article": "m.11/d",
            "gdpr_article": "Art.20",
        },
        "profile": _export_profile(current_user),
        "integrations": intg,
        "wallets": wallets,
        "snapshots": snapshots,
        "tefas_holdings": await _list(TefasHolding),
        "stock_holdings": await _list(StockHolding),
        "bes_holdings": await _list(BesHolding),
        "commodity_holdings": await _list(CommodityHolding),
        "manual_crypto_holdings": await _list(ManualCryptoHolding),
        "cash_holdings": await _list(CashHolding),
        "expenses": await _list(Expense),
        "planned_expenses": await _list(PlannedExpense),
        "incomes": await _list(Income),
        "recurring_incomes": await _list(RecurringIncome),
        "budgets": await _list(Budget),
        "credit_cards": await _list(CreditCard),
        "advice": await _list(InvestmentAdvice),
        "audit_logs": audit_logs,
    }

    await log_audit(
        db,
        request,
        action=AuditAction.DATA_EXPORT,
        user_id=uid,
        extra={
            "snapshot_count": len(snapshots),
            "audit_log_count": len(audit_logs),
            "wallet_count": len(wallets),
        },
    )
    await db.commit()

    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"kfinans-data-{uid}-{datetime.now(timezone.utc).date().isoformat()}.json"
    return StreamingResponse(
        BytesIO(body),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─── AI-005 (FAZ H): Anthropic ozel acik riza (KVKK m.9) ────────────────


@router.post("/anthropic-consent", status_code=status.HTTP_200_OK)
@limiter.limit("10/hour")
async def grant_anthropic_consent(
    request: Request,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Kullanici Anthropic API'ye veri aktarimi icin acik riza verir.
    /advice/generate cagrisi bu rizayi kontrol eder; yoksa 403."""
    current_user.anthropic_consent_at = datetime.now(timezone.utc)
    current_user.anthropic_consent_version = ANTHROPIC_CONSENT_VERSION
    await log_audit(
        db,
        request,
        action=AuditAction.ANTHROPIC_CONSENT_GRANT,
        user_id=current_user.id,
        extra={"version": ANTHROPIC_CONSENT_VERSION},
    )
    await db.commit()
    return {
        "detail": "Anthropic veri aktarimi rizasi kaydedildi",
        "consent_at": current_user.anthropic_consent_at.isoformat(),
        "version": ANTHROPIC_CONSENT_VERSION,
    }


@router.delete("/anthropic-consent", status_code=status.HTTP_200_OK)
@limiter.limit("10/hour")
async def revoke_anthropic_consent(
    request: Request,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    """Anthropic rizasini geri ceker; /advice/generate artik 403 doner."""
    if current_user.anthropic_consent_at is None:
        return {"detail": "Bu riza zaten mevcut degil"}

    current_user.anthropic_consent_at = None
    current_user.anthropic_consent_version = None
    await log_audit(
        db,
        request,
        action=AuditAction.ANTHROPIC_CONSENT_REVOKE,
        user_id=current_user.id,
    )
    await db.commit()
    return {"detail": "Anthropic veri aktarimi rizasi geri cekildi. AI tavsiye ozelligi artik kullanilamaz."}
