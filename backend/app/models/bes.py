import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BesHolding(Base):
    """BES (Bireysel Emeklilik Sistemi) manuel girilen fon bakiyeleri.

    Faz 1'de scraping yok — kullanici plan adi ve toplam TL degeri girer.
    Ileride bes.py soyut servis olarak yazilirsa fiyat birimi alanlari eklenir.
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
    total_value_tl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    user: Mapped["User"] = relationship(back_populates="bes_holdings")
