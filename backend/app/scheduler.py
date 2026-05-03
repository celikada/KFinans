import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.snapshot import compute_and_save_snapshot

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="Europe/Istanbul")


async def _weekly_snapshot_job() -> None:
    """Her Pazar 23:00'de tum aktif kullanicilar icin portfoy snapshot'i alir.

    Hata izolasyonu: bir kullanicinin fetch hatasi digerlerini etkilemesin diye
    her kullanici icin ayri try/except ve ayri DB session'i acilir.
    """
    logger.info("Haftalik portfoy snapshot gorevi basladi")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.email_verified.is_(True),
                User.deleted_at.is_(None),
            )
        )
        user_ids = [u.id for u in result.scalars().all()]

    success = 0
    failed = 0
    for user_id in user_ids:
        try:
            async with AsyncSessionLocal() as session:
                await compute_and_save_snapshot(user_id, session)
            success += 1
        except Exception as e:
            failed += 1
            logger.exception("Snapshot hatasi (user_id=%s): %s", user_id, e)

    logger.info(
        "Haftalik portfoy snapshot tamamlandi: %d basarili, %d hatali, toplam %d kullanici",
        success,
        failed,
        len(user_ids),
    )


def start_scheduler() -> None:
    _scheduler.add_job(
        _weekly_snapshot_job,
        CronTrigger(day_of_week="sun", hour=23, minute=0, timezone="Europe/Istanbul"),
        id="weekly_snapshot",
        replace_existing=True,
        misfire_grace_time=3600,  # uygulama yeniden başlatildiysa 1 saat icinde tekrar dene
    )
    _scheduler.start()
    logger.info("Zamanlayici baslatildi (haftalik snapshot: Pazar 23:00 Europe/Istanbul)")


def stop_scheduler() -> None:
    _scheduler.shutdown(wait=False)
    logger.info("Zamanlayici durduruldu")
