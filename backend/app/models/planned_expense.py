import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlannedExpense(Base):
    __tablename__ = "planned_expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # PERF-003 (FAZ H)
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # loan | tax | insurance | subscription | rent | utility | other
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    # one_time | monthly | quarterly | biannual | yearly | custom
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False)
    # custom recurrence icin hangi aylar [1-12]
    months: Mapped[Optional[list[int]]] = mapped_column(ARRAY(Integer), nullable=True)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    start_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    remaining_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Opsiyonel kredi kartı bağlantısı (çift sayım kuralı için)
    credit_card_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("credit_cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Planlı harcama gerçekleşti mi? (default=false; "yapıldı" olarak işaretlenince
    # cash flow forecast'tan çıkar — kart ile ödendiyse zaten kart borcu sayar.)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="planned_expenses")
