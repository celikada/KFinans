"""Web Push aboneliği: tarayıcı/PWA push subscription kaydı.

Kullanıcı service worker üzerinden `PushManager.subscribe()` ile bir endpoint +
p256dh/auth anahtar çifti üretir; backend bunu saklayıp `pywebpush` ile şifreli
bildirim gönderir. `(user_id, endpoint)` unique — aynı cihaz/tarayıcı için tek
kayıt (idempotent UPSERT).
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Push servisi endpoint URL'i (FCM/Mozilla/Apple). 512 tipik üst sınır için yeterli.
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    # Tarayıcının ürettiği ECDH public key (base64url) — payload şifreleme için.
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    # Auth secret (base64url) — payload şifreleme için.
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="push_subscriptions")

    __table_args__ = (UniqueConstraint("user_id", "endpoint", name="uq_push_subscription_user_endpoint"),)
