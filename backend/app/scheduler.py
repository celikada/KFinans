import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def _weekly_snapshot_job():
    """Her Pazar 23:00'de tüm kullanıcılar için portföy snapshot'ı alır."""
    logger.info("Haftalık portföy snapshot görevi başladı")
    # TODO: tüm aktif kullanıcıları çek, her biri için servis çağır, snapshot kaydet
    logger.info("Haftalık portföy snapshot görevi tamamlandı")


def start_scheduler():
    _scheduler.add_job(
        _weekly_snapshot_job,
        CronTrigger(day_of_week="sun", hour=23, minute=0),
        id="weekly_snapshot",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Zamanlayıcı başlatıldı")


def stop_scheduler():
    _scheduler.shutdown(wait=False)
    logger.info("Zamanlayıcı durduruldu")
