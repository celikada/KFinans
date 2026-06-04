import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Expense(Base):
    """Kullanicinin manuel olarak girdigi harcama kaydi.

    Faz 3 MVP: manuel giris. Sonraki iteration'larda banka/kredi karti
    ekstre import'i ve TCMB Acik Bankacilik entegrasyonu eklenecek.
    """

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # PERF-003 (FAZ H)
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # food | transport | bills | groceries | health | entertainment |
    # clothing | home | tax | other
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Opsiyonel: harcama bir kredi kartından yapıldıysa kart ID'si.
    # Boş = nakit/banka. Çift sayım kuralı için kullanılır.
    credit_card_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("credit_cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Periyodik gider tanımından (planned_expense) realize edildiyse kaynak ID.
    # Boş = doğrudan girilmiş harcama. Çift realize'ı önleyen partial unique
    # index (planned_expense_id, date) ile birlikte kullanılır.
    planned_expense_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("planned_expenses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Harcama gerçekleşti mi? (default=true; planlı kayıttan dönüştürülen
    # nadir senaryolarda false olabilir.)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="expenses")
