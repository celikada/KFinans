import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from app.core.masking import mask_address

EXCHANGE_PROVIDERS = {"binance", "binancetr", "icrypex", "tefas", "bes"}
CHAINS = {
    "ethereum",
    "sonic",
    "avalanche_c",
    "avalanche_p",
    "bitcoin",
    "solana",
    "cardano",
    "algorand",
    "polkadot",
    "litecoin",
}


class IntegrationCreate(BaseModel):
    provider: str
    api_key: str
    api_secret: Optional[str] = None

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        if v not in EXCHANGE_PROVIDERS:
            raise ValueError(f"Geçersiz provider. Desteklenenler: {EXCHANGE_PROVIDERS}")
        return v


class IntegrationOut(BaseModel):
    id: uuid.UUID
    provider: str
    is_active: bool
    last_synced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WalletCreate(BaseModel):
    chain: str
    address: str
    label: Optional[str] = None

    @field_validator("chain")
    @classmethod
    def _validate_chain(cls, v: str) -> str:
        if v not in CHAINS:
            raise ValueError(f"Geçersiz zincir. Desteklenenler: {CHAINS}")
        return v


class WalletOut(BaseModel):
    id: uuid.UUID
    chain: str
    address: str
    label: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

    # BACK-013 (FAZ H): xpub leak engeli — JSON response'ta address maskelenir.
    # DB'de Fernet sifreli (FAZ C1); buradaki maskeleme network/proxy/log sizmasini
    # da onler. Excel export full adresi opt-in audit'li dondurur (wallets.py).
    @field_serializer("address")
    def _serialize_address(self, addr: str) -> str:
        return mask_address(addr)
