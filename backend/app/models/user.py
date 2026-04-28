import uuid
from datetime import datetime
from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # conservative | balanced | aggressive
    risk_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="balanced")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    integrations: Mapped[list["Integration"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    wallet_addresses: Mapped[list["WalletAddress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    portfolio_snapshots: Mapped[list["PortfolioSnapshot"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    investment_advice: Mapped[list["InvestmentAdvice"]] = relationship(back_populates="user", cascade="all, delete-orphan")
