"""Tarihsel TCMB döviz kuru cache'i (Faz A altyapı).

Belirli bir TARİHTEKİ 1 birim döviz = X TL kurunu saklar. Çoklu para birimi
raporlamasında "işlem tarihindeki kur" dönüşümünün temeli (Faz B kayıt-bazlı
dönüşümde kullanır).

Tasarım kararları:
- PK (rate_date, currency) — bir gün+döviz için tek satır.
- TRY saklanmaz (=1, kodda sabit) — gereksiz satır şişmesi yok.
- Yalnız GERÇEK TCMB yayın günleri tutulur. Hafta sonu/tatil için ayrı
  forward-fill satırı YAZILMAZ; lookup sırasında dinamik forward-fill yapılır
  (en yakın rate_date <= aranan tarih).
"""

from datetime import date, datetime

from sqlalchemy import Date, Numeric, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyRate(Base):
    """Tek bir (tarih, döviz) için TCMB ForexBuying kuru (1 birim = X TL)."""

    __tablename__ = "daily_rates"

    rate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    rate_to_try: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="tcmb")
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
