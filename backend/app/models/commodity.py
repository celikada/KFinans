import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CommodityHolding(Base):
    __tablename__ = "commodity_holdings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # gram | biga | coin
    unit_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # gold | silver — coin için her zaman "gold"
    metal: Mapped[str] = mapped_column(String(10), nullable=False)
    # A01..A08 (altın BiGA), G01..G07 (gümüş BiGA) — sadece unit_type="biga"
    biga_code: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    # ceyrek|yarim|tam|cumhuriyet|resat|ata — sadece unit_type="coin"
    coin_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # gram için gram, diğerleri için adet
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="commodity_holdings")  # noqa: F821
