"""Periyodik gelir/gider için dönem-bazlı 'gerçekleşmeyecek' işareti."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RecurringSkip(Base):
    """Bir periyodik tanımın (gelir/gider) belirli bir döneminin atlandığı kaydı.

    `kind` + `ref_id` polimorfik referans: income → recurring_incomes.id,
    expense → planned_expenses.id. Tanım silinirse skip orphan kalır ama zararsız
    (pending hesabında ref bulunamayınca zaten dikkate alınmaz).
    """

    __tablename__ = "recurring_skips"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # "income" | "expense"
    ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "kind",
            "ref_id",
            "period_year",
            "period_month",
            name="uq_recurring_skip_period",
        ),
    )
