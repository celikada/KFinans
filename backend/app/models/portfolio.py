import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy import String, Text, Date, Boolean, ForeignKey, UniqueConstraint, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB
from app.models.base import Base


class PortfolioSnapshot(Base):
    """Her Pazar alınan haftalık portföy anlık görüntüsü."""

    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # DBA-001 (FAZ H): User silinince snapshot cascade.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value_tl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # Snapshot anındaki TCMB USD/TRY kuru — geçmiş USD eğimi için (anlık kur değil)
    usd_try_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    # 0/hata veren kaynaklar listesi: [{"source": "ethereum", "code": "rpc_failed", "msg": "..."}]
    health_issues: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "snapshot_date", name="uq_snapshot_user_date"),)

    user: Mapped["User"] = relationship(back_populates="portfolio_snapshots")
    asset_positions: Mapped[list["AssetPosition"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
    investment_advice: Mapped[list["InvestmentAdvice"]] = relationship(back_populates="snapshot")


class AssetPosition(Base):
    """Snapshot içindeki her varlık pozisyonu."""

    __tablename__ = "asset_positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # DBA-001 (FAZ H): Snapshot silinince asset_positions cascade.
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio_snapshots.id", ondelete="CASCADE"), nullable=False,
    )

    # exchange | blockchain
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # binance | icrypex | sonic | avalanche | ethereum | tefas | bes
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # crypto | staked_crypto | fund | pension | cash
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)

    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    liquid_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False, default=0)
    staked_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False, default=0)
    pending_rewards: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False, default=0)

    # FIN-018 (FAZ H): SHIB/PEPE gibi mikro fiyatlar (0.0000003 USD) icin
    # 4 ondalik yetersiz; 28,10 ile 0.0000000001 TRY hassasiyet.
    unit_price_tl: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    total_value_tl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    weight_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)

    # Blockchain pozisyonlar için hangi cüzdandan geldiği.
    # DBA-001 (FAZ H): Wallet silinince asset_position kaybolmasin (history koru); SET NULL.
    wallet_address_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallet_addresses.id", ondelete="SET NULL"),
    )

    snapshot: Mapped["PortfolioSnapshot"] = relationship(back_populates="asset_positions")
