"""Kişisel borç/alacak (kredi kartı dışı) — Budget empty.xlsx "Debt" sayfası.

Kredi kartı borcu ``credit_cards`` ile izlenir; bu tablo kişiler/kurumlar arası
ikili borç-alacak (örn. "Ezgi'ye borç", "İlkem alacak") içindir. Bütçe modülü
özet (toplam borç / alacak / net) gösterir; cash-flow'a OTOMATİK girmez (manuel takip).
"""

import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PersonalDebt(Base):
    __tablename__ = "personal_debts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counterparty: Mapped[str] = mapped_column(String(120), nullable=False)
    # debt = kullanıcı borçlu; receivable = kullanıcıya borçlu (alacak)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="TRY")
    due_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Kapatıldığında set edilir (ödendi/tahsil edildi); None → açık.
    settled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="personal_debts")
