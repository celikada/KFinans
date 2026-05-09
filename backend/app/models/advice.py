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
    # DBA-001 (FAZ H): User silinince advice cascade; snapshot silinince advice
    # tarihce bilgisini kaybetmeyelim — SET NULL (snapshot_id zaten optional).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio_snapshots.id", ondelete="SET NULL"),
    )
    # medium (3-12 ay) | long (1-3 yıl)
    horizon: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    # AI-002 (FAZ H): Anthropic prompt caching token metrikleri.
    # cache_read_tokens > 0 -> system prompt cache HIT (%95 maliyet tasarrufu).
    # cache_creation_tokens > 0 -> ilk istek (cache yazildi, bedeli orta).
    # Cache hit oranı = sum(cache_read) / sum(cache_read + cache_creation + prompt)
    cache_read_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    cache_creation_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    credits_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="investment_advice")
    snapshot: Mapped[Optional["PortfolioSnapshot"]] = relationship(back_populates="investment_advice")
