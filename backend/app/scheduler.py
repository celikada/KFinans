import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete, distinct, select, text

from app.api.v1.credit_cards import _DUE_SOON_DAYS as _CREDIT_CARD_DUE_SOON_DAYS
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.credit_card import CreditCard, CreditCardStatement
from app.models.push_subscription import PushSubscription
from app.models.revoked_token import RevokedToken
from app.models.subscription import Subscription, SubscriptionBill
from app.models.user import User
from app.services.email import send_payment_reminder_email
from app.services.historical_rates import ensure_date_cached
from app.services.push import send_to_user
from app.services.snapshot import compute_and_save_snapshot

logger = logging.getLogger(__name__)
_TZ = "Europe/Istanbul"
_ISTANBUL = ZoneInfo(_TZ)
_scheduler = AsyncIOScheduler(timezone=_TZ)

# Ödemesi bu kadar gün içinde olan (veya gecikmiş) ekstreler için hatırlatma
# (hem push hem e-posta). credit_cards.py `_DUE_SOON_DAYS` (girişteki popup
# hatırlatması) tek kaynaktır; import edilerek tutarlılık garanti edilir.
_DUE_SOON_DAYS = _CREDIT_CARD_DUE_SOON_DAYS

# ARC-011 (FAZ H): Multi-replica safety — sadece 1 pod scheduler'i baslatir.
# K8s deployment'ta `SCHEDULER_ENABLED=true` sadece 1 replica'ya verilir
# (env: SCHEDULER_ENABLED=true icin 1 leader pod, digerleri scheduler kapali).
# Default True (test/dev tek pod). Production multi-replica'da explicit false.
_SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() in ("1", "true", "yes")

# ARC-011: pg advisory lock — birden fazla replica yanlislikla SCHEDULER_ENABLED=true
# alirsa job-icinde defence-in-depth. Lock key sabit; ayni job sadece bir pod'da
# calisir. pg_try_advisory_xact_lock transaction-scoped (commit/rollback ile auto release).
_SCHEDULER_LOCK_KEY = 0x4B46494E_414E5300  # "KFINANS\x00" hex

# Ödeme hatırlatması e-posta cron'u için AYRI lock key — push job (09:00) ile
# e-posta job (09:05) aynı anda farklı pod'larda paralel çalışabilsin diye
# bağımsız leader election. (Aynı lock olsaydı iki job birbirini bloklardı.)
_EMAIL_REMINDER_LOCK_KEY = 0x4B46494E_454D4C00  # "KFINEML\x00" hex

# Tarihsel TCMB kuru cron'u için AYRI lock key — diğer job'larla paralel farklı
# pod'larda çalışabilsin diye bağımsız leader election.
_DAILY_RATE_LOCK_KEY = 0x4B46494E_52415400  # "KFINRAT\x00" hex

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
                success,
                failed,
                len(user_ids),
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
        result = await session.execute(delete(RevokedToken).where(RevokedToken.expires_at < now))
        await session.commit()
        deleted = result.rowcount or 0
    logger.info("revoked_tokens cleanup: %d expired kayit silindi", deleted)


async def _purge_old_audit_logs_job(session_factory=None) -> None:
    """COMP-022 (FAZ H): KVKK m.7 saklama suresi sonu — eski audit_logs sil.

    Default 365 gun (settings.audit_log_retention_days). Forensic icin 1 yillik
    pencere yeterli; ondan eski kayitlar IP/user_agent/email PII icerdiginden
    fiziksel silinir (anonimlestirme yetersiz — kombinasyondan kimlik cikar).

    Her gun 04:30 Europe/Istanbul'da calisir.
    """
    sf = session_factory or AsyncSessionLocal
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audit_log_retention_days)
    async with sf() as session:
        result = await session.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
        await session.commit()
        deleted = result.rowcount or 0
    if deleted:
        logger.info(
            "COMP-022 audit retention: %d eski kayit silindi (>%d gun)",
            deleted,
            settings.audit_log_retention_days,
        )
    else:
        logger.debug("COMP-022 audit retention: silinecek kayit yok")


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
    # credit_transactions.user_id ON DELETE RESTRICT (TTK saklama). Tek set-based
    # DELETE'te ledger'lı TEK kullanıcı tüm batch'i IntegrityError ile düşürürdü →
    # KVKK hard-delete sessizce hiç çalışmazdı. Ledger'lı kullanıcıları hariç tut,
    # ayrıca sayıp uyar (bunlar için anonimleştirme politikası gerekiyor — backlog).
    from app.models.credit_transaction import CreditTransaction

    has_ledger = select(CreditTransaction.id).where(CreditTransaction.user_id == User.id).exists()
    async with sf() as session:
        blocked = (await session.execute(select(User.id).where(User.deleted_at.is_not(None), User.deleted_at < cutoff, has_ledger))).scalars().all()
        if blocked:
            logger.warning(
                "COMP-004 hard-delete: %d kullanici kredi ledger (RESTRICT) nedeniyle fiziksel SILINEMEDI — anonimlestirme politikasi gerekli",
                len(blocked),
            )
        result = await session.execute(
            delete(User).where(
                User.deleted_at.is_not(None),
                User.deleted_at < cutoff,
                ~has_ledger,
            )
        )
        await session.commit()
        deleted = result.rowcount or 0
    if deleted:
        logger.info(
            "COMP-004 hard-delete: %d kullanici fiziksel silindi (%d gun retention sonu)",
            deleted,
            _HARD_DELETE_RETENTION_DAYS,
        )
    else:
        logger.debug("COMP-004 hard-delete: silinecek kayit yok")


async def _due_statements_for_user(session, user_id, today) -> list[CreditCardStatement]:
    """DRY: bir kullanıcının ödemesi yaklaşan/gecikmiş kart ekstrelerini döner.

    `paid_at IS NULL` ve `due_date <= bugün + _DUE_SOON_DAYS` koşulunu sağlayan
    `CreditCardStatement` kayıtları (kullanıcının kartlarına join). Hem push
    (`_push_due_payments_job`) hem e-posta (`_email_due_payments_job`) cron'ları
    bu helper'ı kullanır (SonarQube S4144 duplication önlenir).
    """
    cutoff = today + timedelta(days=_DUE_SOON_DAYS)
    result = await session.execute(
        select(CreditCardStatement)
        .join(CreditCard, CreditCard.id == CreditCardStatement.card_id)
        .where(
            CreditCard.user_id == user_id,
            CreditCardStatement.paid_at.is_(None),
            CreditCardStatement.due_date <= cutoff,
        )
    )
    return list(result.scalars().all())


async def _due_subscription_bills_for_user(session, user_id, today) -> list[SubscriptionBill]:
    """DRY: bir kullanıcının ödemesi yaklaşan/gecikmiş abonelik faturaları.

    `paid_at IS NULL` + `due_date <= bugün + _DUE_SOON_DAYS` olan, kullanıcının
    aktif aboneliklerine bağlı `SubscriptionBill` kayıtları. Kart ekstreleriyle
    aynı hatırlatma pencerelerinde (push 09:00 + e-posta 09:05) kullanılır.
    """
    cutoff = today + timedelta(days=_DUE_SOON_DAYS)
    result = await session.execute(
        select(SubscriptionBill)
        .join(Subscription, Subscription.id == SubscriptionBill.subscription_id)
        .where(
            Subscription.user_id == user_id,
            Subscription.active.is_(True),
            SubscriptionBill.paid_at.is_(None),
            SubscriptionBill.due_date <= cutoff,
        )
    )
    return list(result.scalars().all())


async def _push_due_payments_job(session_factory=None) -> None:
    """Her gün 09:00 Europe/Istanbul: ödemesi yaklaşan kart borçları için push.

    Push aboneliği olan her kullanıcı için, `_due_statements_for_user` ile yaklaşan
    ekstreleri bulur; en az bir tane varsa o kullanıcıya TEK özet bildirim gönderir.

    ARC-011: pg advisory lock — multi-replica deploy'da sadece bir pod yürütür.

    `session_factory`: test'te TestSession enjekte etmek için; default production'da
    AsyncSessionLocal.
    """
    sf = session_factory or AsyncSessionLocal
    today = datetime.now(_ISTANBUL).date()

    async with sf() as lock_session:
        if not await _try_acquire_lock(lock_session, _SCHEDULER_LOCK_KEY):
            logger.info("Push due-payments job: pg advisory lock alinamadi, baska pod calisiyor — skip")
            return

        try:
            async with sf() as session:
                # Push aboneliği olan kullanıcılar
                user_ids = (await session.execute(select(distinct(PushSubscription.user_id)))).scalars().all()
                total_sent = 0
                for user_id in user_ids:
                    n = len(await _due_statements_for_user(session, user_id, today))
                    n += len(await _due_subscription_bills_for_user(session, user_id, today))
                    if n == 0:
                        continue
                    sent = await send_to_user(
                        session,
                        user_id,
                        title="Yaklaşan kart ödemesi",
                        body=f"{n} ödeme yaklaşıyor/gecikti",
                        url="/dashboard/credit-cards",
                        tag="kfinans-due-payments",
                    )
                    total_sent += sent
            logger.info("Push due-payments job tamamlandi: %d bildirim gonderildi", total_sent)
        finally:
            await _release_lock(lock_session, _SCHEDULER_LOCK_KEY)


def _statement_to_reminder_item(stmt: CreditCardStatement, card_name: str, today) -> dict:
    """Ekstre → e-posta hatırlatma satırı dict'i (DRY, S7500 dict() kaçınma)."""
    return {
        "card_name": card_name,
        "amount": f"{stmt.statement_amount:,.2f}",
        "currency": stmt.currency,
        "due_date": stmt.due_date.isoformat(),
        "days_until_due": (stmt.due_date - today).days,
    }


def _subscription_bill_to_reminder_item(bill: SubscriptionBill, name: str, today) -> dict:
    """Abonelik faturası → e-posta hatırlatma satırı (kart ekstresiyle aynı şekil)."""
    return {
        "card_name": name,
        "amount": f"{bill.bill_amount:,.2f}",
        "currency": bill.currency,
        "due_date": bill.due_date.isoformat(),
        "days_until_due": (bill.due_date - today).days,
    }


async def _subscription_reminder_items(session, sub_bills: list[SubscriptionBill], today) -> list[dict]:
    """Abonelik faturalarını e-posta hatırlatma satırlarına çevirir (provider/label adıyla)."""
    if not sub_bills:
        return []
    from app.schemas.subscription import PROVIDERS

    sub_ids = {b.subscription_id for b in sub_bills}
    subs = (await session.execute(select(Subscription).where(Subscription.id.in_(sub_ids)))).scalars().all()
    sub_by_id = {s.id: s for s in subs}
    items: list[dict] = []
    for bill in sub_bills:
        sub = sub_by_id.get(bill.subscription_id)
        if sub is None:
            continue
        name = sub.label or PROVIDERS.get(sub.provider_code, (sub.provider_code, sub.category))[0]
        items.append(_subscription_bill_to_reminder_item(bill, name, today))
    return items


async def _email_due_payments_job(session_factory=None) -> None:
    """Her gün 09:05 Europe/Istanbul: ödemesi yaklaşan kart borçları için e-posta.

    Push'a alternatif (Google/tarayıcı bağımsız). `payment_reminder_email=True`
    VE `email_verified=True` VE `deleted_at IS NULL` her kullanıcı için
    `_due_statements_for_user` ile yaklaşan ekstreleri bulur; en az bir tane
    varsa Resend ile TEK özet e-posta gönderir (best-effort).

    Push job (09:00) ile çakışmasın diye 5 dk sonra + AYRI advisory lock key.

    `session_factory`: test'te TestSession enjekte etmek için; default production'da
    AsyncSessionLocal.
    """
    sf = session_factory or AsyncSessionLocal
    today = datetime.now(_ISTANBUL).date()

    async with sf() as lock_session:
        if not await _try_acquire_lock(lock_session, _EMAIL_REMINDER_LOCK_KEY):
            logger.info("Email due-payments job: pg advisory lock alinamadi, baska pod calisiyor — skip")
            return

        try:
            async with sf() as session:
                users = (
                    (
                        await session.execute(
                            select(User).where(
                                User.payment_reminder_email.is_(True),
                                User.email_verified.is_(True),
                                User.deleted_at.is_(None),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                total_sent = 0
                for user in users:
                    statements = await _due_statements_for_user(session, user.id, today)
                    sub_bills = await _due_subscription_bills_for_user(session, user.id, today)
                    if not statements and not sub_bills:
                        continue
                    # Kart adlarını tek sorguda çek (N+1 önle).
                    card_ids = {s.card_id for s in statements}
                    cards = (await session.execute(select(CreditCard).where(CreditCard.id.in_(card_ids)))).scalars().all()
                    card_names = {c.id: c.name for c in cards}
                    items = [_statement_to_reminder_item(s, card_names.get(s.card_id, "-"), today) for s in statements]
                    items.extend(await _subscription_reminder_items(session, sub_bills, today))
                    try:
                        if await send_payment_reminder_email(to=user.email, items=items):
                            total_sent += 1
                    except Exception as e:
                        logger.exception("Ödeme hatırlatması e-postası gönderilemedi (user=%s): %s", user.id, e)
            logger.info("Email due-payments job tamamlandi: %d kullaniciya e-posta gonderildi", total_sent)
        finally:
            await _release_lock(lock_session, _EMAIL_REMINDER_LOCK_KEY)


async def _fetch_daily_rate_job(session_factory=None) -> None:
    """Her gün 16:00 Europe/Istanbul: bugünün TCMB kurunu daily_rates'e cache'ler.

    TCMB döviz kurlarını ~15:30'da yayınlar; 16:00 güvenli pencere. Tarihsel kur
    altyapısının (historical_rates) günlük beslemesi — Faz B kayıt-bazlı dönüşüm
    için "işlem tarihindeki kur"un birikmesini sağlar.

    Hafta sonu/tatil → TCMB o gün veri yayınlamaz (404) → `ensure_date_cached`
    no-op (forward-fill lookup zaten önceki iş gününü bulur).

    ARC-011: pg advisory lock (AYRI key) — multi-replica deploy'da sadece bir pod
    yürütür. `session_factory`: test'te enjekte edilir; default AsyncSessionLocal.
    """
    sf = session_factory or AsyncSessionLocal
    today = datetime.now(_ISTANBUL).date()

    async with sf() as lock_session:
        if not await _try_acquire_lock(lock_session, _DAILY_RATE_LOCK_KEY):
            logger.info("Daily rate job: pg advisory lock alinamadi, baska pod calisiyor — skip")
            return

        try:
            async with sf() as session:
                await ensure_date_cached(session, today)
            logger.info("Daily rate job tamamlandi: %s TCMB kuru cache'lendi (varsa)", today.isoformat())
        except Exception as e:
            logger.exception("Daily rate job hatasi (%s): %s", today.isoformat(), e)
        finally:
            await _release_lock(lock_session, _DAILY_RATE_LOCK_KEY)


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
    _scheduler.add_job(
        _purge_old_audit_logs_job,
        CronTrigger(hour=4, minute=30, timezone=_TZ),
        id="purge_old_audit_logs",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _push_due_payments_job,
        CronTrigger(hour=9, minute=0, timezone=_TZ),
        id="push_due_payments",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _email_due_payments_job,
        CronTrigger(hour=9, minute=5, timezone=_TZ),
        id="email_due_payments",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _fetch_daily_rate_job,
        CronTrigger(hour=16, minute=0, timezone=_TZ),
        id="fetch_daily_rate",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info(
        "Zamanlayici baslatildi (haftalik snapshot: Pazar 23:00, "
        "revoked_tokens cleanup: gunluk 03:00, hard-delete: 04:00, "
        "audit retention: 04:30, push hatirlatma: 09:00, "
        "e-posta hatirlatma: 09:05, gunluk kur: 16:00 Europe/Istanbul)"
    )


def stop_scheduler() -> None:
    if not _SCHEDULER_ENABLED:
        return
    _scheduler.shutdown(wait=False)
    logger.info("Zamanlayici durduruldu")
