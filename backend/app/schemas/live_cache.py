"""Canlı portföy cache (live_portfolio_cache) Pydantic şemaları.

`GET /portfolio/live` çıktısı. Sunucu-tarafı arka plan cache'inden okunur;
dashboard + detay sayfaları her açılışta dış-API çağrısı yapmadan bu hızlı
DB okumasını kullanır.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class LivePortfolioOut(BaseModel):
    """Kullanıcının en son hesaplanmış canlı portföy görünümü.

    - status: 'ok' (taze/geçerli veri) | 'refreshing' (ilk hesaplama sürüyor,
      sections boş olabilir) | 'error' (son refresh tamamen başarısız oldu;
      sections eski başarılı veriyi taşıyabilir).
    - stale: refreshed_at `live_cache_stale_minutes` dışındaysa True. Frontend
      "güncelleniyor" rozeti gösterebilir; backend zaten arka planda tazeler.
    - sections: bölüm bazlı pozisyon listeleri/özetleri (wallets, crypto, tefas,
      stocks, commodities, manual_crypto). Her biri ilgili endpoint çıktısının
      JSON-safe (Decimal→str) hâlidir.
    """

    status: str
    refreshed_at: datetime | None = None
    stale: bool
    total_value_tl: Decimal | None = None
    rates: dict[str, Any] | None = None
    health_issues: list[dict[str, Any]] | None = None
    error: str | None = None
    sections: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class RefreshAcceptedOut(BaseModel):
    """`POST /portfolio/refresh` 202 yanıtı — arka plan refresh tetiklendi."""

    status: str
    refreshed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
