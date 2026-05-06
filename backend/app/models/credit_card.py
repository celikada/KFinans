"""Kredi kartı modeli (tanım + dönem içi borç).

Aylık ekstreler ve taksitler ayrı tablolar olarak ileride eklenecek
(credit_card_statements, credit_card_installments).
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CreditCard(Base):
    __tablename__ = "credit_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    last_4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    statement_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    payment_due_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    # Dönem içi henüz ekstreye düşmemiş tutar (kullanıcı manuel günceller)
    current_period_debt: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal(0), server_default="0",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="credit_cards")
