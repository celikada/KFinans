import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from app.models.base import Base


class InvestmentAdvice(Base):
    """Claude API tarafından üretilen yatırım tavsiyeleri."""

    __tablename__ = "investment_advice"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolio_snapshots.id"))
    # medium (3-12 ay) | long (1-3 yıl)
    horizon: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    credits_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="investment_advice")
    snapshot: Mapped[Optional["PortfolioSnapshot"]] = relationship(back_populates="investment_advice")
