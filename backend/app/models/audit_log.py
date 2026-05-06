import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Kritik kullanici eylemlerinin denetim kaydi (FAZ C6).

    KVKK m.12 incident tracing + KVKK Veri Ihlali Bildirim prosedurleri icin
    forensic temel. Loglanan eylemler:
      - auth: login (success/fail), logout, password_change
      - integration: add, delete
      - wallet: add, delete
      - kvkk: data_export
      - snapshot: delete
      - account: soft_delete

    user_id NULL olabilir (anonim eylemler — failed login, registration).

    Index'ler:
      - (user_id, created_at DESC) — kullanicinin kendi log'larini hizli sorgular
      - (action, created_at DESC) — admin/security: tipe gore arama
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Action kategori: auth.login, auth.logout, auth.password_change,
    # integration.add, integration.delete, wallet.add, wallet.delete,
    # kvkk.data_export, snapshot.delete, account.soft_delete, auth.login_failed
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    # Etkilenen resource referansi: "wallet:<uuid>", "integration:binance", "user:<uuid>"
    resource: Mapped[Optional[str]] = mapped_column(String(128))
    # Istemci IP'si (X-Forwarded-For varsa o, yoksa direkt client.host)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 max 45 char
    # User-Agent header'i (truncated)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    # Ek context (parametreler, hata mesajlari, vs.) — JSONB ile esnek
    extra: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
    )
