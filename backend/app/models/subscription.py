"""Abonelik (fatura/utility) modelleri: tanım + aylık fatura dönemleri.

Elektrik/doğalgaz/internet/telefon gibi düzenli faturaların abone no ile manuel
takibi. 3 durumlu yaşam döngüsü:

1. **budget** — fatura çıkmadan; tahmini değer = ``Subscription.budget_amount``
   (``subscription_bills`` satırı YOK; implicit). Cash-flow forecast'ta sayılır.
2. **issued** — fatura geldi; gerçek tutar ``SubscriptionBill`` satırında, ödenmedi
   (``paid_at IS NULL``). Forecast'ta ``bill_amount`` kullanılır.
3. **paid** — ödendi; bağlı ``Expense`` kaydı (``expense_id``) oluşur. Ödeme şekli
   ``credit_card_id``'yi belirler → mevcut çift-sayım kuralı devreye girer.
"""

import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Subscription(Base):
    """Abonelik tanımı (kurum + abone no + aylık bütçe değeri)."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Katalog kodu: esgaz | osmangazi_elektrik | ttnet | vodafone
    provider_code: Mapped[str] = mapped_column(String(40), nullable=False)
    # gas | electricity | internet | phone (provider'dan türetilir, filtre/ikon için saklanır)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    subscriber_no: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Aylık tahmini/bütçe değeri ("henüz gerçekleşmemiş" taban)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="TRY")
    # Abonelik başlangıcı — bütçe bu tarihten itibaren forecast/planlı gider olarak sayılır.
    start_date: Mapped[date_type] = mapped_column(Date, nullable=False, server_default=func.current_date())
    # Tahmini kesim günü (hatırlatma: "fatura gir") ve son ödeme günü
    billing_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    due_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # PDF fatura import'tan gelen sonraki beklenen fatura + son ödeme tarihleri (hatırlatma).
    next_bill_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Son kullanılan ödeme şekli/kartı — sonraki fatura ödemesinde ön-seçili gelir.
    # Ödeme yapıldıkça (pay_bill) güncellenir; kullanıcı kolaylığı (default).
    default_payment_method: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    default_credit_card_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("credit_cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    bills: Mapped[list["SubscriptionBill"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class SubscriptionBill(Base):
    """Bir aboneliğin belirli ay-yılı için fatura dönemi.

    Yalnızca fatura GİRİLDİĞİNDE (issue) materialize edilir; satırı olmayan aylar
    implicit "budget" durumundadır. Durum ``paid_at`` ile türetilir.
    """

    __tablename__ = "subscription_bills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="TRY")
    bill_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    bill_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    due_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    # PDF import'tan gelen fatura no (referans + ileride dedup).
    bill_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # Ödeme şekli: cash | credit_card (ödendiğinde set edilir)
    payment_method: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    # Kredi kartıyla ödendiyse hangi kart (çift-sayım için Expense'e taşınır)
    credit_card_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("credit_cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Ödendiğinde oluşan gerçek gider kaydı
    expense_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("expenses.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="bills")

    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "period_year",
            "period_month",
            name="uq_subscription_bill_period",
        ),
    )
