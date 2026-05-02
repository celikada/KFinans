import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Integer, String, Text, func
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
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verify_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    verify_token_expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    credit_balance: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    integrations: Mapped[list["Integration"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    wallet_addresses: Mapped[list["WalletAddress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    portfolio_snapshots: Mapped[list["PortfolioSnapshot"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    investment_advice: Mapped[list["InvestmentAdvice"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tefas_holdings: Mapped[list["TefasHolding"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    stock_holdings: Mapped[list["StockHolding"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    bes_holdings: Mapped[list["BesHolding"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    planned_expenses: Mapped[list["PlannedExpense"]] = relationship(back_populates="user", cascade="all, delete-orphan")
