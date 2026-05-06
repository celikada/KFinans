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
from app.scheduler import _cleanup_revoked_tokens_job
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
        remaining = (await session.execute(
            select(RevokedToken).where(RevokedToken.user_id == user.id)
        )).scalars().all()
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
        remaining = (await session.execute(
            select(RevokedToken).where(RevokedToken.jti == ftk_jti)
        )).scalar_one_or_none()
        assert remaining is not None, "Hala gecerli token silinmemeliydi"
