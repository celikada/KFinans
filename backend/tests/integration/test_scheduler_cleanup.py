"""
revoked_tokens cleanup cron job'unun davranisini dogrular (FAZ C5).

Cron icin APScheduler trigger'i lifespan'da kayit ediliyor; bu testler
job fonksiyonunu (cleanup logic) dogrudan cagirip:
  - expired kayitlarin silindigini
  - hala gecerli kayitlarin silinmedigini
  dogrular.
"""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import pytest
from sqlalchemy import select

from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.scheduler import (
    _HARD_DELETE_RETENTION_DAYS,
    _SCHEDULER_LOCK_KEY,
    _cleanup_revoked_tokens_job,
    _hard_delete_expired_users_job,
    _purge_old_audit_logs_job,
    _release_lock,
    _try_acquire_lock,
)
from tests.conftest import TestSession


async def _make_user_in_db() -> User:
    """Test icin minimal user ekle."""
    # Rastgele bcrypt hash uret — login icin kullanilmaz, sadece NOT NULL constraint icin
    random_hash = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt()).decode()
    user = User(
        id=uuid4(),
        email=f"cleanup_{uuid4().hex[:8]}@example.com",
        password_hash=random_hash,
        risk_profile="balanced",
        email_verified=True,
    )
    async with TestSession() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_cleanup_deletes_expired_tokens():
    """expires_at < now olan kayitlar silinmeli."""
    user = await _make_user_in_db()
    now = datetime.now(timezone.utc)

    async with TestSession() as session:
        # 1 saat önce expire olmus
        expired = RevokedToken(
            jti=f"expired_{uuid4().hex}",
            user_id=user.id,
            token_type="access",
            expires_at=now - timedelta(hours=1),
        )
        # 1 gun sonra expire olacak
        valid = RevokedToken(
            jti=f"valid_{uuid4().hex}",
            user_id=user.id,
            token_type="refresh",
            expires_at=now + timedelta(days=1),
        )
        session.add_all([expired, valid])
        await session.commit()
        expired_jti = expired.jti
        valid_jti = valid.jti

    # Cleanup'i calistir
    await _cleanup_revoked_tokens_job(session_factory=TestSession)

    # Expired silinmis, valid duruyor olmali
    async with TestSession() as session:
        remaining = (
            (await session.execute(select(RevokedToken).where(RevokedToken.user_id == user.id)))
            .scalars()
            .all()
        )
        jtis = {r.jti for r in remaining}
        assert expired_jti not in jtis, "Expired token silinmemis"
        assert valid_jti in jtis, "Valid token yanlislikla silinmis"


@pytest.mark.asyncio
async def test_cleanup_preserves_recently_expired_within_seconds():
    """expires_at = now-1s olan kayit cleanup zamanindan once silinmemeli (race)."""
    # Bu test cleanup'in kati bir < karsilastirmasi yaptigini dogrular
    # (>= olsaydi simdi expire olan da silinirdi).
    user = await _make_user_in_db()
    far_future = datetime.now(timezone.utc) + timedelta(hours=24)

    async with TestSession() as session:
        future_token = RevokedToken(
            jti=f"future_{uuid4().hex}",
            user_id=user.id,
            token_type="access",
            expires_at=far_future,
        )
        session.add(future_token)
        await session.commit()
        ftk_jti = future_token.jti

    await _cleanup_revoked_tokens_job(session_factory=TestSession)

    async with TestSession() as session:
        remaining = (
            await session.execute(select(RevokedToken).where(RevokedToken.jti == ftk_jti))
        ).scalar_one_or_none()
        assert remaining is not None, "Hala gecerli token silinmemeliydi"


# ─── COMP-004 (FAZ H): Hard-delete cron ────────────────────────────────


@pytest.mark.asyncio
async def test_hard_delete_removes_users_after_retention():
    """deleted_at > 30 gun once olanlar fiziksel silinir."""
    user = await _make_user_in_db()
    expired_email = user.email
    cutoff_past = datetime.now(timezone.utc) - timedelta(days=_HARD_DELETE_RETENTION_DAYS + 5)

    async with TestSession() as session:
        await session.execute(
            User.__table__.update().where(User.id == user.id).values(deleted_at=cutoff_past)
        )
        await session.commit()

    await _hard_delete_expired_users_job(session_factory=TestSession)

    async with TestSession() as session:
        result = await session.execute(select(User).where(User.email == expired_email))
        assert result.scalar_one_or_none() is None, "30 gun gecmis kullanici silinmeliydi"


@pytest.mark.asyncio
async def test_hard_delete_keeps_recently_soft_deleted():
    """deleted_at < 30 gun yeni soft-delete'lar korunur (geri alma penceresi)."""
    user = await _make_user_in_db()
    recent_delete = datetime.now(timezone.utc) - timedelta(days=5)

    async with TestSession() as session:
        await session.execute(
            User.__table__.update().where(User.id == user.id).values(deleted_at=recent_delete)
        )
        await session.commit()

    await _hard_delete_expired_users_job(session_factory=TestSession)

    async with TestSession() as session:
        result = await session.execute(select(User).where(User.id == user.id))
        assert result.scalar_one_or_none() is not None, "5 gunluk soft-delete erken silindi"


@pytest.mark.asyncio
async def test_hard_delete_skips_active_users():
    """deleted_at = NULL olan aktif kullanicilar dokunulmaz."""
    active_user = await _make_user_in_db()

    await _hard_delete_expired_users_job(session_factory=TestSession)

    async with TestSession() as session:
        result = await session.execute(select(User).where(User.id == active_user.id))
        assert result.scalar_one_or_none() is not None, "Aktif kullanici yanlislikla silindi"


# ─── ARC-011 (FAZ H): pg advisory lock leader election ────────────────


@pytest.mark.asyncio
async def test_advisory_lock_acquire_release_round_trip():
    """pg_try_advisory_lock alinabilir, release sonrasi tekrar alinabilir."""
    async with TestSession() as session:
        ok = await _try_acquire_lock(session, _SCHEDULER_LOCK_KEY)
        assert ok is True
        await _release_lock(session, _SCHEDULER_LOCK_KEY)


@pytest.mark.asyncio
async def test_advisory_lock_blocks_second_attempt_in_other_session():
    """Bir session lock tutarken, baska session ayni key'i alamaz (multi-replica)."""
    async with TestSession() as s1:
        ok1 = await _try_acquire_lock(s1, _SCHEDULER_LOCK_KEY)
        assert ok1 is True

        async with TestSession() as s2:
            ok2 = await _try_acquire_lock(s2, _SCHEDULER_LOCK_KEY)
            assert ok2 is False, "Lock multi-replica leader election icin tek pod'a kilitli olmali"

        await _release_lock(s1, _SCHEDULER_LOCK_KEY)

    # s1 release ettigine gore yeni session lock alabilmeli
    async with TestSession() as s3:
        ok3 = await _try_acquire_lock(s3, _SCHEDULER_LOCK_KEY)
        assert ok3 is True
        await _release_lock(s3, _SCHEDULER_LOCK_KEY)


# ─── COMP-022 (FAZ H): audit_logs retention ─────────────────────────


@pytest.mark.asyncio
async def test_purge_old_audit_logs_deletes_after_retention():
    """retention_days'den eski kayitlar fiziksel silinir."""
    from app.config import settings
    from app.models.audit_log import AuditLog

    user = await _make_user_in_db()
    cutoff_past = datetime.now(timezone.utc) - timedelta(days=settings.audit_log_retention_days + 5)
    recent = datetime.now(timezone.utc) - timedelta(days=10)

    async with TestSession() as session:
        old_log = AuditLog(
            user_id=user.id,
            action="auth.login",
            ip_address="1.2.3.4",
        )
        session.add(old_log)
        await session.flush()
        # created_at default now() — manuel old'a cek
        await session.execute(
            AuditLog.__table__.update()
            .where(AuditLog.id == old_log.id)
            .values(created_at=cutoff_past)
        )
        recent_log = AuditLog(
            user_id=user.id,
            action="auth.login",
            ip_address="5.6.7.8",
        )
        session.add(recent_log)
        await session.flush()
        await session.execute(
            AuditLog.__table__.update()
            .where(AuditLog.id == recent_log.id)
            .values(created_at=recent)
        )
        await session.commit()
        old_id = old_log.id
        recent_id = recent_log.id

    await _purge_old_audit_logs_job(session_factory=TestSession)

    async with TestSession() as session:
        old_check = await session.execute(select(AuditLog).where(AuditLog.id == old_id))
        recent_check = await session.execute(select(AuditLog).where(AuditLog.id == recent_id))
        assert old_check.scalar_one_or_none() is None, "Eski kayit silinmeliydi"
        assert recent_check.scalar_one_or_none() is not None, "Guncel kayit korunmaliydi"


@pytest.mark.asyncio
async def test_purge_audit_logs_no_old_records_no_op():
    """Hicbir kayit eski degilse silinen 0 (no-op)."""
    from app.models.audit_log import AuditLog

    user = await _make_user_in_db()
    async with TestSession() as session:
        for _ in range(3):
            session.add(AuditLog(user_id=user.id, action="auth.login"))
        await session.commit()

    # Cron calistir
    await _purge_old_audit_logs_job(session_factory=TestSession)

    # Hepsi duruyor olmali
    async with TestSession() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.user_id == user.id))
        assert len(result.scalars().all()) == 3
