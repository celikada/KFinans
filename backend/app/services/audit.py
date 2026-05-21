"""Audit log servisi (FAZ C6).

Kritik kullanici eylemlerini `audit_logs` tablosuna yazar. KVKK m.12 incident
tracing icin gerekli minimum bilgi: kim, ne, ne zaman, nereden.

Kullanim:
    from app.services.audit import log_audit, AuditAction
    await log_audit(
        db, request,
        action=AuditAction.WALLET_ADD,
        user_id=current_user.id,
        resource=f"wallet:{wallet.id}",
        extra={"chain": wallet.chain},
    )

Performans: log yazma fail ederse ana endpoint patlamamali — try/except ile
sarilip warning log yazilir, kullanici islemi devam eder. Audit log eksik
olur ama veri tutarliligi korunur.
"""

import logging
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Standart audit action isimleri (string enum — DB'de string olarak yazilir)."""

    # Auth
    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGE = "auth.password_change"
    EMAIL_VERIFIED = "auth.email_verified"
    REGISTER = "auth.register"
    # SEC-001 (FAZ H): Password reset akisi
    PASSWORD_RESET_REQUEST = "auth.password_reset_request"
    PASSWORD_RESET_COMPLETE = "auth.password_reset_complete"
    # COMP-029 (FAZ H): E-posta degistirme — KVKK m.11/d duzeltme hakki
    EMAIL_CHANGE_REQUEST = "user.email_change_request"
    EMAIL_CHANGE_COMPLETE = "user.email_change_complete"
    # COMP-006 (FAZ H): Acik riza geri cekme — KVKK m.5/1
    CONSENT_REVOKE = "user.consent_revoke"
    # AI-005 (FAZ H): Anthropic ozel acik riza — KVKK m.9
    ANTHROPIC_CONSENT_GRANT = "kvkk.anthropic_consent_grant"
    ANTHROPIC_CONSENT_REVOKE = "kvkk.anthropic_consent_revoke"
    # COMP-003 (FAZ H): Veri tasinabilirligi (KVKK m.11/d, GDPR Art.20)
    DATA_EXPORT = "user.data_export"

    # Integrations (exchange API key'ler)
    INTEGRATION_ADD = "integration.add"
    INTEGRATION_DELETE = "integration.delete"

    # Wallets (blockchain adresleri)
    WALLET_ADD = "wallet.add"
    WALLET_DELETE = "wallet.delete"
    WALLET_EXPORT = "wallet.export"  # FAZ H — COMP-024 (xpub Excel export izleme)

    # KVKK
    KVKK_DATA_EXPORT = "kvkk.data_export"

    # Snapshot
    SNAPSHOT_DELETE = "snapshot.delete"

    # Account
    ACCOUNT_SOFT_DELETE = "account.soft_delete"

    # AI / Advice (FAZ H — AI-004)
    ADVICE_GENERATE = "advice.generate"

    # MFA — TOTP (audit #5 MFA)
    MFA_SETUP = "auth.mfa.setup"
    MFA_ENABLED = "auth.mfa.enabled"
    MFA_DISABLED = "auth.mfa.disabled"
    MFA_VERIFY_SUCCESS = "auth.mfa.verify_success"
    MFA_VERIFY_FAILED = "auth.mfa.verify_failed"
    MFA_RECOVERY_USED = "auth.mfa.recovery_used"
    LOGIN_MFA_REQUIRED = "auth.login_mfa_required"


def _client_ip(request: Optional[Request]) -> Optional[str]:
    """SEC-004 (FAZ H): Sadece `request.client.host` kullan.

    Onceki kod X-Forwarded-For'u kor korune okuyordu — saldirgan
    `X-Forwarded-For: 127.0.0.1` gondererek audit log + rate limit'i
    spoofing edebilirdi. Uvicorn `--proxy-headers` + `--forwarded-allow-ips`
    flag'i ile **trusted proxy** zincirinden gelen X-F-F'i `request.client.host`
    olarak normalize eder; biz sadece bu (dogrulanmis) degeri okuyoruz.

    Production setup (k8s/Oracle):
      uvicorn ... --proxy-headers --forwarded-allow-ips="10.0.0.0/8,127.0.0.0/8"
    Bu flag yoksa Uvicorn X-F-F'i hic dikkate almaz — direkt client.host doner.
    """
    if request is None:
        return None
    if request.client:
        return request.client.host
    return None


def _user_agent(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    ua = request.headers.get("user-agent", "")
    return ua[:512] if ua else None


async def log_audit(
    db: AsyncSession,
    request: Optional[Request],
    *,
    action: AuditAction | str,
    user_id: Optional[UUID] = None,
    resource: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """audit_logs tablosuna bir kayit ekler. Hata durumunda yutar (best-effort).

    Caller'in `db.commit()`'inden once cagrilirsa kayit ayni transaction'da
    flush olur; sonra cagrilirsa ayrica commit gerekir. Genelde endpoint'in
    sonunda, ana commit'ten once cagirilmasi tercih edilir.
    """
    try:
        log = AuditLog(
            user_id=user_id,
            action=action.value if isinstance(action, AuditAction) else action,
            resource=resource,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
            extra=extra,
        )
        db.add(log)
        await db.flush()  # commit caller'a birakilir
    except Exception as exc:
        # Audit fail ana endpoint'i bozmamali
        logger.warning(
            "audit log yazilamadi: action=%s user=%s resource=%s err=%s",
            action,
            user_id,
            resource,
            exc,
        )
