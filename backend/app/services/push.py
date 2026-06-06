"""Web Push gönderim servisi (VAPID + pywebpush).

`send_web_push` tek bir aboneliğe şifreli bildirim gönderir; 404/410 dönen
(expired/unsubscribed) abonelikleri çağırana bildirir (caller DB'den siler).
`send_to_user` bir kullanıcının tüm aboneliklerine gönderir, expired olanları
temizler, gönderilen sayısını döner. VAPID anahtarı yoksa tüm gönderim no-op.

Bildirim JSON payload sözleşmesi (frontend service worker bunu bekler):
    {"title": str, "body": str, "url": str, "tag": str | None}
"""

import json
import logging
from typing import Optional
from uuid import UUID

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)

# Bu HTTP durum kodları aboneliğin artık geçersiz olduğunu gösterir
# (kullanıcı izni geri aldı / tarayıcı endpoint'i sildi) — DB'den temizlenmeli.
_EXPIRED_STATUS = (404, 410)


def send_web_push(subscription: dict, payload: dict, app_settings: Settings) -> bool:
    """Tek bir aboneliğe push gönderir.

    `subscription`: {"endpoint": str, "keys": {"p256dh": str, "auth": str}}.
    Returns:
        True  — gönderildi.
        False — abonelik expired (404/410); caller bu aboneliği silmeli.
    Raises:
        WebPushException — expired dışındaki gönderim hataları (geçici sorun).
    """
    webpush(
        subscription_info={
            "endpoint": subscription["endpoint"],
            "keys": {
                "p256dh": subscription["keys"]["p256dh"],
                "auth": subscription["keys"]["auth"],
            },
        },
        data=json.dumps(payload),
        vapid_private_key=app_settings.vapid_private_key,
        vapid_claims={"sub": app_settings.vapid_subject},
    )
    return True


def _deliver_one(sub: PushSubscription, payload: dict, cfg: Settings) -> str:
    """Tek aboneliğe gönderir; sonucu sınıflandırır: 'sent' | 'expired' | 'error'.

    Try/except dallarını send_to_user'dan ayırır (cognitive complexity)."""
    sub_info = {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
    try:
        send_web_push(sub_info, payload, cfg)
        return "sent"
    except WebPushException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in _EXPIRED_STATUS:
            logger.info("Push abonelik expired (status=%s) — siliniyor (id=%s)", status_code, sub.id)
            return "expired"
        logger.warning("Push gönderim hatası (id=%s status=%s): %s", sub.id, status_code, exc)
        return "error"
    except Exception as exc:
        logger.warning("Push gönderim beklenmeyen hata (id=%s): %s", sub.id, exc)
        return "error"


async def send_to_user(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    body: str,
    url: str,
    tag: Optional[str] = None,
    app_settings: Optional[Settings] = None,
) -> int:
    """Kullanıcının tüm aboneliklerine bildirim gönderir; expired olanları siler.

    Best-effort: bir aboneliğin hatası diğerlerini bozmaz. Gönderilen (başarılı)
    abonelik sayısını döner. VAPID public key yoksa hiç gönderim yapmaz (0 döner).
    """
    cfg = app_settings or settings
    if not cfg.vapid_public_key or not cfg.vapid_private_key:
        logger.warning("Web Push devre dışı (VAPID anahtarı tanımsız) — bildirim atlanıyor (user=%s)", user_id)
        return 0

    payload = {"title": title, "body": body, "url": url, "tag": tag}
    subs = (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars().all()

    sent = 0
    expired_ids: set[int] = set()
    for sub in subs:
        result = _deliver_one(sub, payload, cfg)
        if result == "sent":
            sent += 1
        elif result == "expired":
            expired_ids.add(sub.id)

    if expired_ids:
        for sub in subs:
            if sub.id in expired_ids:
                await db.delete(sub)
        await db.commit()

    return sent
