from decimal import Decimal
from app.services.base import BaseIntegration, AssetData


class BesService(BaseIntegration):
    """
    BES (Bireysel Emeklilik Sistemi) entegrasyonu.
    Faz 1: Manuel giriş — kullanıcı birikim tutarını direkt girer.
    Faz 2: Sigorta şirketi portal scraping.
    """

    def __init__(self, manual_value_tl: Decimal, company: str = "BES"):
        self.manual_value_tl = manual_value_tl
        self.company = company

    async def fetch(self) -> list[AssetData]:
        return [
            AssetData(
                symbol="BES",
                name=f"BES — {self.company}",
                provider="bes",
                asset_type="pension",
                source_type="exchange",
                liquid_quantity=Decimal(1),
                unit_price_tl=self.manual_value_tl,
            )
        ]

    async def health_check(self) -> bool:
        return True
