import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


EXCHANGE_PROVIDERS = {"binance", "binancetr", "icrypex", "tefas", "bes"}
CHAINS = {"ethereum", "sonic", "avalanche_c", "avalanche_p"}


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
