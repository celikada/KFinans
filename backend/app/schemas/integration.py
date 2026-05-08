import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_serializer

from app.core.masking import mask_address


EXCHANGE_PROVIDERS = {"binance", "binancetr", "icrypex", "tefas", "bes"}
CHAINS = {
    "ethereum", "sonic", "avalanche_c", "avalanche_p", "bitcoin",
    "solana", "cardano", "algorand", "polkadot", "litecoin",
}


class IntegrationCreate(BaseModel):
    provider: str
    api_key: str
    api_secret: Optional[str] = None

    def model_post_init(self, __context):
        if self.provider not in EXCHANGE_PROVIDERS:
            raise ValueError(f"Geçersiz provider. Desteklenenler: {EXCHANGE_PROVIDERS}")


class IntegrationOut(BaseModel):
    id: uuid.UUID
    provider: str
    is_active: bool
    last_synced_at: Optional[datetime]

    class Config:
        from_attributes = True


class WalletCreate(BaseModel):
    chain: str
    address: str
    label: Optional[str] = None

    def model_post_init(self, __context):
        if self.chain not in CHAINS:
            raise ValueError(f"Geçersiz zincir. Desteklenenler: {CHAINS}")


class WalletOut(BaseModel):
    id: uuid.UUID
    chain: str
    address: str
    label: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True

    # BACK-013 (FAZ H): xpub leak engeli — JSON response'ta address maskelenir.
    # DB'de Fernet sifreli (FAZ C1); buradaki maskeleme network/proxy/log sizmasini
    # da onler. Excel export full adresi opt-in audit'li dondurur (wallets.py).
    @field_serializer("address")
    def _serialize_address(self, addr: str) -> str:
        return mask_address(addr)
