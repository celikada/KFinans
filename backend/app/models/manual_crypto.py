"""Manuel kripto borsa pozisyon modeli (API'siz borsalar için).

BinanceTR ve iCrypex gibi public read-only API anahtarı vermeyen borsalar için
kullanıcı bakiyeyi manuel girer. Snapshot servisi anlık fiyatlarla TL/USD
değer hesaplar.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ManualCryptoHolding(Base):
    __tablename__ = "manual_crypto_holdings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    exchange: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    avg_cost_tl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    # 'auto' (Binance+CoinGecko), 'manual' (kullanıcı), 'gold_gram', 'silver_gram'
    price_source: Mapped[str] = mapped_column(String(20), nullable=False, default="auto", server_default="auto")
    manual_unit_price_tl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="manual_crypto_holdings")
