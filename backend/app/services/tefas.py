import logging
import httpx
from datetime import date, timedelta
from decimal import Decimal
from app.services.base import BaseIntegration, AssetData

logger = logging.getLogger(__name__)


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


class TefasService(BaseIntegration):
    """
    TEFAS yatırım fonu birim fiyatlarını resmi export API'sinden çeker.
    holdings: [{"code": "YAC", "quantity": 150.5, "name": "..."}, ...]
    """

    def __init__(self, holdings: list[dict]):
        self.holdings = holdings

    async def fetch(self) -> list[AssetData]:
        prices = await self._fetch_prices()
        assets = []
        for h in self.holdings:
            code = h["code"].upper()
            price_tl = prices.get(code)
            if price_tl is None:
                raise ValueError(f"TEFAS'ta fon bulunamadı: {code}")
            assets.append(AssetData(
                symbol=code,
                name=h.get("name", code),
                provider="tefas",
                asset_type="fund",
                source_type="exchange",
                liquid_quantity=Decimal(str(h["quantity"])),
                unit_price_tl=price_tl,
            ))
        return assets

    async def _fetch_prices(self) -> dict[str, Decimal]:
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
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
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
