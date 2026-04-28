from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class AssetData:
    """Herhangi bir kaynaktan normalize edilmiş varlık verisi."""
    symbol: str
    name: str
    provider: str
    asset_type: str                         # crypto | staked_crypto | fund | pension | cash
    source_type: str                        # exchange | blockchain
    liquid_quantity: Decimal = Decimal(0)
    staked_quantity: Decimal = Decimal(0)
    pending_rewards: Decimal = Decimal(0)
    unit_price_usd: Decimal = Decimal(0)    # aggregator TL'ye çevirir
    unit_price_tl: Decimal = Decimal(0)     # doğrudan TL fiyatı varsa (fonlar gibi)
    wallet_address_id: str | None = None


class BaseIntegration(ABC):
    """Tüm entegrasyon servislerinin uygulaması gereken arayüz."""

    @abstractmethod
    async def fetch(self) -> list[AssetData]:
        """Kaynaktan varlık verilerini çeker ve AssetData listesi döner."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Bağlantı/yetkilendirme sağlıklı mı kontrol eder."""
        ...


class BaseExchangeIntegration(BaseIntegration):
    """API key/secret gerektiren merkezi borsa entegrasyonları için temel sınıf."""

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret


class BaseBlockchainIntegration(BaseIntegration):
    """Public cüzdan adresi ile çalışan blockchain entegrasyonları için temel sınıf."""

    def __init__(self, address: str, wallet_address_id: str | None = None):
        self.address = address
        self.wallet_address_id = wallet_address_id
