import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CreditTransaction(Base):
    """Kredi defteri (ledger) — her bakiye degisiminin audit-trail kaydi.

    Faz 3 kredi sistemi. `users.credit_balance` denormalize anlik bakiyeyi
    tutar; bu tablo o bakiyeye giden HER hareketi (yukleme + tuketim) tutar.
    Tutarlilik invaryanti: her bakiye degisimi tek transaction'da hem buraya
    insert hem `users.credit_balance` update icerir (bkz. app/core/credits.py).

    amount isareti:
      - pozitif  → yukleme (satin alma, manuel/seed)
      - negatif  → tuketim (AI tavsiye, vb.)

    idempotency_key: iyzico webhook cift-teslimat korumasi (UNIQUE). Tuketimde
    NULL; satin almada checkout'un conversation_id'si yazilir.

    ON DELETE RESTRICT: kredi hareketi olan kullanici fiziksel silinemez
    (TTK m.82 — 10 yil saklama). KVKK soft-delete'te users.deleted_at set
    edilir, ledger korunur (user_id referans kalir, PII users tarafinda silinir).

    Index'ler:
      - (user_id) — kullanicinin kendi defterini sorgular (IDOR korumali GET /credits)
      - (created_at DESC) — en yeni hareketler
    """

    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Pozitif: yukleme, negatif: tuketim
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'purchase', 'ai_advice_medium', 'crypto_sync', 'checkout_pending' vb.
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # iyzico paymentId / advice UUID gibi dis referans
    reference_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Cift odeme/islem korumasi (webhook). Tuketimde NULL, satin almada conversation_id.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    # Ek context: {"package": "standard", "horizon": "medium", "iyzico_status": "..."}
    # NOT: SQLAlchemy'de `metadata` rezerve (Base.metadata) -> Python attribute `extra`.
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_credit_transactions_user_id", "user_id"),
        Index("ix_credit_transactions_created_at", "created_at"),
    )
