import logging
from datetime import date, timedelta
from decimal import Decimal

import httpx

from app.config import settings
from app.core.cache import AsyncTTLCache
from app.services.base import AssetData, BaseIntegration

logger = logging.getLogger(__name__)

# TEFAS fiyat gridi (tüm YAT fonları) holdings'ten bağımsız tek istekte gelir →
# tek anahtarla cache'lenir (single-flight: dashboard'ın paralel TEFAS çağrıları
# tek upstream isteği paylaşır). Fiyatlar günde 1 değişir → uzun TTL güvenli.
_TEFAS_PRICE_CACHE: AsyncTTLCache[dict[str, Decimal]] = AsyncTTLCache(ttl_sec=settings.tefas_cache_ttl_sec)
# TTL sonrası bile saklanan son-başarılı grid. Prod 2026-06-13: TEFAS export
# endpoint'i ConnectTimeout veriyor (sunucu/IP block) → erişilemediğinde boş dict
# yerine son bilinen fiyatları döndürüp veriyi ekranda tutarız (issue ile işaretli).
_TEFAS_LAST_GOOD: dict[str, Decimal] = {}
_TEFAS_CACHE_KEY = "all"


def reset_tefas_cache() -> None:
    """Test izolasyonu: modül-seviyesi TEFAS fiyat cache'i + son-iyi gridi temizler."""
    global _TEFAS_LAST_GOOD
    _TEFAS_PRICE_CACHE.invalidate()
    _TEFAS_LAST_GOOD = {}


# ARC-001 (FAZ H): API katmaninin (api/v1/manual_crypto.py) onceden bu helper'i
# tasidigi durum kaldirildi — service katmani API'ye bagimli olamaz (dependency
# inversion). Manuel kripto + snapshot servisleri linked_id 'tefas:CODE' icin
# burayi cagirir.


async def fetch_tefas_prices_by_codes(codes: list[str]) -> dict[str, Decimal]:
    """Verilen TEFAS fon kodlari icin TL/birim fiyat doner. Bulunmayanlar yer almaz.

    Hata durumunda (httpx error, JSON parse vb.) bos dict doner — caller best-effort
    enrichment yapar (manual_unit_price_tl=None ise pozisyon 0 TL gozukur).
    """
    if not codes:
        return {}
    payload = [{"code": c, "quantity": 1, "name": c} for c in codes]
    try:
        assets = await TefasService(payload).fetch()
        return {a.symbol: a.unit_price_tl for a in assets if a.unit_price_tl > 0}
    except Exception as e:
        logger.warning("TEFAS linked fiyat cekilemedi: %s", e)
        return {}


_EXPORT_URL = "https://www.tefas.gov.tr/api/fund-returns/export"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.tefas.gov.tr/",
    "Content-Type": "application/json",
}


async def _fetch_price_grid() -> dict[str, Decimal]:
    """TEFAS export API'sinden tüm YAT fon birim fiyatlarını çeker (ham HTTP)."""
    today = date.today()
    # Hafta sonu veya tatil dışında son 7 günlük pencere — en az 1 işlem günü içerir
    start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    payload = {
        "format": "json",
        "listingType": "size",
        "fundType": "YAT",
        "locale": "tr",
        "filters": {
            "basTarih": start,
            "bitTarih": end,
            "calismaTipi": 1,
        },
    }
    async with httpx.AsyncClient(timeout=settings.tefas_timeout, headers=_HEADERS) as client:
        resp = await client.post(_EXPORT_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # data: list[{fonKodu, fonUnvan, sonPortfoyDegeri, sonPayAdedi, ...}]
    prices: dict[str, Decimal] = {}
    for row in data:
        kod = row.get("fonKodu", "")
        portfoy = row.get("sonPortfoyDegeri")
        pay = row.get("sonPayAdedi")
        if kod and portfoy and pay and pay > 0:
            prices[kod] = Decimal(str(round(portfoy / pay, 6)))
    return prices


async def _cached_price_grid() -> dict[str, Decimal]:
    """Cache'li fiyat gridi. TEFAS erişilemezse son-başarılı fiyatlara düşer."""
    global _TEFAS_LAST_GOOD

    async def factory() -> dict[str, Decimal]:
        grid = await _fetch_price_grid()
        if grid:  # başarılı + dolu → son-iyi fallback'i güncelle
            _TEFAS_LAST_GOOD = grid
        return grid

    try:
        return await _TEFAS_PRICE_CACHE.get_or_compute(_TEFAS_CACHE_KEY, factory)
    except Exception as e:
        if _TEFAS_LAST_GOOD:
            logger.warning(
                "TEFAS fiyatları çekilemedi (%s) — son başarılı fiyatlar kullanılıyor (%d fon)",
                e,
                len(_TEFAS_LAST_GOOD),
            )
            return _TEFAS_LAST_GOOD
        raise


class TefasService(BaseIntegration):
    """
    TEFAS yatırım fonu birim fiyatlarını resmi export API'sinden çeker.
    holdings: [{"code": "YAC", "quantity": 150.5, "name": "..."}, ...]
    """

    def __init__(self, holdings: list[dict]):
        self.holdings = holdings
        # skip_missing=True çağrısında fiyatlanamayan fon kodları (uyarı için).
        self.missing_codes: list[str] = []

    async def fetch(self, *, skip_missing: bool = False) -> list[AssetData]:
        """Holding'leri canlı fiyatlarla AssetData'ya çevirir.

        ``skip_missing=False`` (preview/validation): fiyatlanamayan fon → ValueError.
        ``skip_missing=True`` (dashboard/live cache): fiyatlanamayan fon ATLANIR
        (``self.missing_codes``'a eklenir) → tek geçici fiyatsız fon (ör. 0 portföy
        değerli) tüm TEFAS kartını çökertmez. Caller eksik kodları uyarıya çevirir.
        """
        prices = await self._fetch_prices()
        assets = []
        self.missing_codes = []
        for h in self.holdings:
            code = h["code"].upper()
            price_tl = prices.get(code)
            if price_tl is None:
                if skip_missing:
                    self.missing_codes.append(code)
                    continue
                raise ValueError(f"TEFAS'ta fon bulunamadı: {code}")
            assets.append(
                AssetData(
                    symbol=code,
                    name=h.get("name", code),
                    provider="tefas",
                    asset_type="fund",
                    source_type="exchange",
                    liquid_quantity=Decimal(str(h["quantity"])),
                    unit_price_tl=price_tl,
                )
            )
        return assets

    async def _fetch_prices(self) -> dict[str, Decimal]:
        # Cache + son-iyi fallback üzerinden tüm fiyat gridini al.
        return await _cached_price_grid()

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10, headers=_HEADERS) as client:
                r = await client.post(
                    _EXPORT_URL,
                    json={
                        "format": "json",
                        "listingType": "size",
                        "fundType": "YAT",
                        "locale": "tr",
                        "filters": {"calismaTipi": 2},
                    },
                )
                return r.status_code == 200
        except Exception:
            return False
