"""Kredi kartı modelleri: tanım + dönem içi borç + aylık ekstreler + taksitler."""
import uuid
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CreditCard(Base):
    __tablename__ = "credit_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    last_4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    statement_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    payment_due_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    # Dönem içi henüz ekstreye düşmemiş tutar (kullanıcı manuel günceller)
    current_period_debt: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal(0), server_default="0",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="credit_cards")
    statements: Mapped[list["CreditCardStatement"]] = relationship(
        back_populates="card", cascade="all, delete-orphan",
    )
    installments: Mapped[list["CreditCardInstallment"]] = relationship(
        back_populates="card", cascade="all, delete-orphan",
    )


class CreditCardStatement(Base):
    """Aylık ekstre kaydı (kesim tarihi + tutar + son ödeme tarihi)."""
    __tablename__ = "credit_card_statements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("credit_cards.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    statement_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    due_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )

    card: Mapped["CreditCard"] = relationship(back_populates="statements")

    __table_args__ = (
        UniqueConstraint("card_id", "period_year", "period_month", name="uq_statement_card_period"),
    )


class CreditCardInstallment(Base):
    """Gelecek aylar için bilinen taksit yükümlülüğü.

    Cash flow projeksiyonunda her ay `monthly_amount` kadar gider olarak
    sayılır (ilk taksit `first_due_date`'ten başlar, `installments_remaining`
    kadar ay devam eder).
    """
    __tablename__ = "credit_card_installments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("credit_cards.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    installments_total: Mapped[int] = mapped_column(Integer, nullable=False)
    installments_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    first_due_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
    )

    card: Mapped["CreditCard"] = relationship(back_populates="installments")
