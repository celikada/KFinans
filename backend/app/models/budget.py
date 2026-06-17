import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

_USERS_FK = "users.id"


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_budget_user_category"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(_USERS_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,  # PERF-003 (FAZ H)
    )
    # same categories as Expense
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # Çoklu para birimi (v0.3.0). Bütçe hedefi — karşılaştırmada güncel kurla
    # TL'ye çevrilip harcama (amount_tl) ile kıyaslanır (hibrit kur).
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="TRY")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="budgets")


class BudgetLine(Base):
    """Bütçe v2 ızgara hücresi — her (kategori, yıl, ay) için ayrı planlanan tutar.

    Mevcut düz ``Budget`` (kategori başına tek tutar) korunur; ``BudgetLine`` onun
    aydan-aya değişebilen tam ızgara karşılığıdır (butce26.xlsx 12 aylık ızgara).
    Actual harcama burada TUTULMAZ — her zaman ``expenses`` tablosundan türetilir.
    """

    __tablename__ = "budget_lines"
    __table_args__ = (UniqueConstraint("user_id", "year", "month", "category", name="uq_budget_line_period_cat"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(_USERS_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Expense kategorisi ya da "savings" (Future You kovası hedefi).
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="TRY")
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="budget_lines")


class BudgetSettings(Base):
    """Kullanıcı başına 3-kova ayarı (Fundamental/Fun/Future You hedef oranları +
    kategori→kova override map). Tek satır (user_id PK)."""

    __tablename__ = "budget_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(_USERS_FK, ondelete="CASCADE"),
        primary_key=True,
    )
    fundamental_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, server_default="0.5")
    fun_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, server_default="0.3")
    future_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, server_default="0.2")
    # category -> bucket override map ({"food": "fundamental", ...}); boşsa kod-içi default.
    category_buckets: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="budget_settings")


class BudgetMonthNote(Base):
    """Aylık serbest metin: "Ayın analizi" + "Aksiyon planı" (Budget empty May/June)."""

    __tablename__ = "budget_month_notes"
    __table_args__ = (UniqueConstraint("user_id", "year", "month", name="uq_budget_note_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(_USERS_FK, ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="budget_month_notes")
