"""Kullanıcı başına canlı portföy cache'i (dashboard hızlandırma + dayanıklılık).

Ağır/dış-API portföy verisi (cüzdan, TEFAS, kripto, hisse, emtia, manuel kripto)
her dashboard açılışında yeniden çekilmek yerine arka planda hesaplanıp burada
saklanır. Dashboard + detay sayfaları bu satırı **hızlı DB okumasıyla** alır;
"Yenile" butonu ve login (veri bayatsa) cache'i yeniden hesaplatır.

Tasarım:
- user_id PK → kullanıcı başına TEK satır (UPSERT).
- payload: bölüm bazlı pozisyon listeleri (endpoint response şekliyle), ör.
  {"wallets": [...], "crypto": [...], "tefas": [...], ...}.
- status: ok | refreshing | error. refreshed_at yalnız BAŞARILI refresh'te güncellenir
  (bayatlık ölçümü buna göre); updated_at her durum değişiminde.
- PortfolioSnapshot'tan AYRI: snapshot tarihsel/değişmez geçmiş; bu mutable "şu anki
  görünüm". Snapshot butonu bu cache'i okuyup snapshot'a kopyalar (yeniden çekmez).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LivePortfolioCache(Base):
    """Kullanıcı başına en son hesaplanmış canlı portföy verisi."""

    __tablename__ = "live_portfolio_cache"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Bölüm bazlı pozisyon listeleri (wallets/crypto/tefas/stocks/commodities/manual_crypto)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    total_value_tl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    # Hesaplama anındaki kurlar {usd_tl, gbp_usd, tcmb...}
    rates: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    health_issues: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)
    # ok | refreshing | error
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ok")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Son BAŞARILI refresh zamanı (bayatlık ölçümü buna göre)
    refreshed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
