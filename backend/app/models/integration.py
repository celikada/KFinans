import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from app.models.base import Base


class Integration(Base):
    """Exchange entegrasyonları — Binance, iCrypex, TEFAS, BES (API key ile)."""

    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # binance | icrypex | tefas | bes
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_key: Mapped[Optional[str]] = mapped_column(Text)
    encrypted_secret: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="integrations")


class WalletAddress(Base):
    """Blockchain cüzdan adresleri — public key, özel anahtar saklanmaz."""

    __tablename__ = "wallet_addresses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # ethereum | sonic | avalanche_c | avalanche_p
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "chain", "address", name="uq_wallet_user_chain_address"),)

    user: Mapped["User"] = relationship(back_populates="wallet_addresses")
