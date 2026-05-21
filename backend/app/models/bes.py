import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BesHolding(Base):
    """BES (Bireysel Emeklilik Sistemi) plan bakiye detayi.

    BES'te 4 ana metrik birbirinden ayri izlenir:
      - paid_principal:    yatirilan ana para (kumulatif)
      - paid_returns:      bu paranin getirisi
      - govt_contribution: devlet katkisi (yatirimin %30'u, yillik tavanli)
      - govt_returns:      devlet katkisinin getirisi

    contract_number: sozlesme numarasi (kullanicinin kendi referansi; Acik
    Finans regulasyonu BES'i kapsadiginda otomatik fetch icin kullanilabilir).
    """

    __tablename__ = "bes_holdings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_name: Mapped[str] = mapped_column(Text, nullable=False)
    contract_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_principal: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    paid_returns: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    govt_contribution: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    govt_returns: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )

    user: Mapped["User"] = relationship(back_populates="bes_holdings")

    @property
    def total_value_tl(self) -> Decimal:
        """4 metric toplami — snapshot ve dashboard ozetinde kullanilir."""
        return self.paid_principal + self.paid_returns + self.govt_contribution + self.govt_returns
