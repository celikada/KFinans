import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete, select, text

from app.database import AsyncSessionLocal
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.services.snapshot import compute_and_save_snapshot

logger = logging.getLogger(__name__)
_TZ = "Europe/Istanbul"
_scheduler = AsyncIOScheduler(timezone=_TZ)

# ARC-011 (FAZ H): Multi-replica safety — sadece 1 pod scheduler'i baslatir.
# K8s deployment'ta `SCHEDULER_ENABLED=true` sadece 1 replica'ya verilir
# (env: SCHEDULER_ENABLED=true icin 1 leader pod, digerleri scheduler kapali).
# Default True (test/dev tek pod). Production multi-replica'da explicit false.
_SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() in ("1", "true", "yes")

# ARC-011: pg advisory lock — birden fazla replica yanlislikla SCHEDULER_ENABLED=true
# alirsa job-icinde defence-in-depth. Lock key sabit; ayni job sadece bir pod'da
# calisir. pg_try_advisory_xact_lock transaction-scoped (commit/rollback ile auto release).
_SCHEDULER_LOCK_KEY = 0x4B46494E_414E5300  # "KFINANS\x00" hex

# ARC-003 (FAZ H): Paralel snapshot semaphore — 100 kullanici icin sirali for
# loop yerine 5'er paralel grup. Her kullanici dis API'ye birden fazla istek
# atar (~10 entegrasyon * 0.5sn); 5 paralel guvenli rate limit altinda kalir.
_SNAPSHOT_PARALLELISM = int(os.getenv("SNAPSHOT_PARALLELISM", "5"))

# COMP-004 (FAZ H): KVKK m.7 + Saklama ve Imha Politikasi yonetmeligi.
# Soft-delete sonrasi 30 gun "geri alma" suresi geciktikten sonra fiziksel silme.
# audit_logs.user_id ON DELETE SET NULL oldugu icin (FAZ C6) audit kayitlari
# anonim kalir (forensic icin korunur). Cascade ile kullanicinin tum FK'lari
# (integrations, wallets, snapshots, holdings vb.) DBA-001'le birlikte zaten silinir.
_HARD_DELETE_RETENTION_DAYS = 30


async def _try_acquire_lock(session, key: int) -> bool:
    """ARC-011: pg_try_advisory_lock — non-blocking, session-scoped.
    Lock release session.close() veya pg_advisory_unlock ile."""
    result = await session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
    return bool(result.scalar())


async def _release_lock(session, key: int) -> None:
    await session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})


async def _snapshot_one_user(user_id, semaphore: asyncio.Semaphore) -> tuple[bool, str | None]:
    """Tek kullanici icin snapshot al. Semaphore ile paralelizm sinirli.
    Returns (success, error_msg)."""
    async with semaphore:
        try:
            async with AsyncSessionLocal() as session:
                await compute_and_save_snapshot(user_id, session)
            return True, None
        except Exception as e:
            logger.exception("Snapshot hatasi (user_id=%s): %s", user_id, e)
            return False, str(e)[:200]


async def _weekly_snapshot_job() -> None:
    """Her Pazar 23:00'de tum aktif kullanicilar icin portfoy snapshot'i alir.

    ARC-011: pg advisory lock — multi-replica deploy'da sadece bir pod yurutur.
    Kilit alinamazsa job skip edilir (digeri zaten calisiyor demek).

    ARC-003: asyncio.gather + Semaphore(_SNAPSHOT_PARALLELISM) — sirali for
    loop yerine 5 (default) kullanici paralel. 100 user 30sn/user -> 50dk
    yerine 10dk.

    Hata izolasyonu: her kullanici ayri DB session, exception izole.
    """
    async with AsyncSessionLocal() as lock_session:
        if not await _try_acquire_lock(lock_session, _SCHEDULER_LOCK_KEY):
            logger.info("Haftalik snapshot job: pg advisory lock alinamadi, baska pod calisiyor — skip")
            return

        try:
            logger.info("Haftalik portfoy snapshot gorevi basladi (paralelizm=%d)", _SNAPSHOT_PARALLELISM)

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(
                        User.email_verified.is_(True),
                        User.deleted_at.is_(None),
                    )
                )
                user_ids = [u.id for u in result.scalars().all()]

            semaphore = asyncio.Semaphore(_SNAPSHOT_PARALLELISM)
            results = await asyncio.gather(
                *[_snapshot_one_user(uid, semaphore) for uid in user_ids],
                return_exceptions=False,
            )

            success = sum(1 for ok, _ in results if ok)
            failed = len(results) - success

            logger.info(
                "Haftalik portfoy snapshot tamamlandi: %d basarili, %d hatali, toplam %d kullanici",
                success, failed, len(user_ids),
            )
        finally:
            await _release_lock(lock_session, _SCHEDULER_LOCK_KEY)


async def _cleanup_revoked_tokens_job(session_factory=None) -> None:
    """Suresi dolmus revoked_tokens kayitlarini siler (FAZ C5).

    Her gun 03:00 Europe/Istanbul'da calisir. Token zaten expire oldugu icin
    blacklist'te tutulmasi gereksiz — DB sonsuz sismesin diye.
    Refresh token TTL = 7 gun, access TTL = 30 dk; bu cron en kotu durumda
    1 hafta + 1 gun gecikmeyle temizler.

    `session_factory`: test'te TestSession enjekte etmek icin; default
    production'da AsyncSessionLocal (app.database).
    """
    sf = session_factory or AsyncSessionLocal
    now = datetime.now(timezone.utc)
    async with sf() as session:
        result = await session.execute(
            delete(RevokedToken).where(RevokedToken.expires_at < now)
        )
        await session.commit()
        deleted = result.rowcount or 0
    logger.info("revoked_tokens cleanup: %d expired kayit silindi", deleted)


async def _hard_delete_expired_users_job(session_factory=None) -> None:
    """COMP-004 (FAZ H): Soft-delete'ten 30 gun gecmis kullanicilari fiziksel siler.

    `users.deleted_at < now - 30 gun` sarti saglayan satirlar `DELETE FROM users`
    ile silinir. DBA-001 ile FK CASCADE aktif (integrations/wallets/snapshots/
    advice cascade silinir). audit_logs.user_id ON DELETE SET NULL oldugu icin
    audit kayitlari anonim kalir (KVKK m.12 forensic gereksinimi karsilanir).

    Her gun 04:00 Europe/Istanbul'da calisir.

    `session_factory`: test'te TestSession enjekte etmek icin; default production'da
    AsyncSessionLocal.
    """
    sf = session_factory or AsyncSessionLocal
    cutoff = datetime.now(timezone.utc) - timedelta(days=_HARD_DELETE_RETENTION_DAYS)
    async with sf() as session:
        result = await session.execute(
            delete(User).where(
                User.deleted_at.is_not(None),
                User.deleted_at < cutoff,
            )
        )
        await session.commit()
        deleted = result.rowcount or 0
    if deleted:
        logger.info(
            "COMP-004 hard-delete: %d kullanici fiziksel silindi (%d gun retention sonu)",
            deleted, _HARD_DELETE_RETENTION_DAYS,
        )
    else:
        logger.debug("COMP-004 hard-delete: silinecek kayit yok")


def start_scheduler() -> None:
    # ARC-011 (FAZ H): Multi-replica safety — sadece SCHEDULER_ENABLED=true
    # olan pod scheduler'i baslatir. Defence-in-depth: job icinde de pg advisory
    # lock var; flag yanlis set edilse bile cift cagrilamaz.
    if not _SCHEDULER_ENABLED:
        logger.info("APScheduler devre disi (SCHEDULER_ENABLED=false) — multi-replica leader degil")
        return

    _scheduler.add_job(
        _weekly_snapshot_job,
        CronTrigger(day_of_week="sun", hour=23, minute=0, timezone=_TZ),
        id="weekly_snapshot",
        replace_existing=True,
        misfire_grace_time=3600,  # uygulama yeniden başlatildiysa 1 saat icinde tekrar dene
    )
    _scheduler.add_job(
        _cleanup_revoked_tokens_job,
        CronTrigger(hour=3, minute=0, timezone=_TZ),
        id="revoked_tokens_cleanup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _hard_delete_expired_users_job,
        CronTrigger(hour=4, minute=0, timezone=_TZ),
        id="hard_delete_expired_users",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info(
        "Zamanlayici baslatildi (haftalik snapshot: Pazar 23:00, "
        "revoked_tokens cleanup: gunluk 03:00, hard-delete cron: gunluk 04:00 Europe/Istanbul)"
    )


def stop_scheduler() -> None:
    if not _SCHEDULER_ENABLED:
        return
    _scheduler.shutdown(wait=False)
    logger.info("Zamanlayici durduruldu")
