"""Periyodik gelir modeli (maaş, kira vb. tahmini gelirler).

PlannedExpense ile aynı yapı. Tek seferlik (gerçekleşen) gelirler `incomes`
tablosunda kalır; bu tablo sadece "yıl sonuna kadar X kazanmayı bekliyorum"
hesabı için kullanılır.
"""

import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RecurringIncome(Base):
    __tablename__ = "recurring_incomes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # PERF-003 (FAZ H)
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # salary | rental | dividend | bonus | freelance | other
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    # one_time | monthly | quarterly | biannual | yearly | custom
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False)
    # custom recurrence için hangi aylar [1-12]
    months: Mapped[Optional[list[int]]] = mapped_column(ARRAY(Integer), nullable=True)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    start_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="recurring_incomes")
