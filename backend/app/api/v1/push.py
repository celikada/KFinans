"""Web Push abonelik endpoint'leri (/api/v1/push/...).

Frontend service worker akışı:
1. GET /push/vapid-public-key — `PushManager.subscribe()` için public key alır.
2. POST /push/subscribe — üretilen subscription'ı kaydeder (idempotent UPSERT).
3. POST /push/unsubscribe — kendi aboneliğini siler (IDOR-safe).
4. POST /push/test — caller'ın tüm aboneliklerine test bildirimi gönderir.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.schemas.push import (
    PushSubscriptionIn,
    PushTestResult,
    PushUnsubscribeIn,
    VapidPublicKeyOut,
)
from app.services.audit import AuditAction, log_audit
from app.services.push import send_to_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key", response_model=VapidPublicKeyOut)
async def get_vapid_public_key(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Frontend'in abonelik oluşturması için VAPID public key (base64url)."""
    return VapidPublicKeyOut(public_key=settings.vapid_public_key)


@router.post("/subscribe", status_code=status.HTTP_201_CREATED, response_model=None)
@limiter.limit("10/minute")
async def subscribe(
    request: Request,
    payload: PushSubscriptionIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Push aboneliği oluştur/güncelle — (user_id, endpoint) UPSERT (idempotent)."""
    existing = (
        await db.execute(
            select(PushSubscription).where(
                PushSubscription.user_id == current_user.id,
                PushSubscription.endpoint == payload.endpoint,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.user_agent = payload.user_agent
    else:
        db.add(
            PushSubscription(
                user_id=current_user.id,
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
                user_agent=payload.user_agent,
            )
        )

    await log_audit(db, request, action=AuditAction.PUSH_SUBSCRIBE, user_id=current_user.id)
    await db.commit()
    return {"status": "ok"}


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    request: Request,
    payload: PushUnsubscribeIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Kendi aboneliğini sil (yalnızca user_id+endpoint eşleşmesi — IDOR-safe)."""
    sub = (
        await db.execute(
            select(PushSubscription).where(
                PushSubscription.user_id == current_user.id,
                PushSubscription.endpoint == payload.endpoint,
            )
        )
    ).scalar_one_or_none()
    if sub is not None:
        await db.delete(sub)
        await log_audit(db, request, action=AuditAction.PUSH_UNSUBSCRIBE, user_id=current_user.id)
        await db.commit()


@router.post("/test", response_model=PushTestResult)
@limiter.limit("5/minute")
async def send_test_notification(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Caller'ın tüm aboneliklerine test bildirimi gönderir (lokal doğrulama)."""
    sent = await send_to_user(
        db,
        current_user.id,
        title="KFinans test bildirimi",
        body="Web Push aboneliğiniz çalışıyor.",
        url="/dashboard",
        tag="kfinans-test",
    )
    return PushTestResult(sent=sent)
