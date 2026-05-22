"""API'siz borsa hesapları için manuel kripto pozisyon şemaları."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PriceSource = Literal["auto", "manual", "linked"]
LinkedSource = Literal["binance", "coingecko", "tefas", "commodity"]


class ManualCryptoCreate(BaseModel):
    exchange: str = Field(..., min_length=1, max_length=40)
    label: str | None = Field(default=None, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=20)
    quantity: Decimal = Field(..., gt=0, le=Decimal("9999999999999999.999999999999"))
    avg_cost_tl: Decimal | None = Field(default=None, ge=0, le=Decimal("999999999999.999999"))
    price_source: PriceSource = "auto"
    manual_unit_price_tl: Decimal | None = Field(default=None, ge=0, le=Decimal("999999999999.999999"))
    linked_source: LinkedSource | None = None
    linked_id: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("avg_cost_tl")
    @classmethod
    def _zero_to_none(cls, v: Decimal | None) -> Decimal | None:
        # 0 veya negatif → None (kullanıcı bilmiyorsa boş bırakabilir)
        if v is None or v <= 0:
            return None
        return v


class ManualCryptoUpdate(BaseModel):
    exchange: str | None = Field(default=None, min_length=1, max_length=40)
    label: str | None = Field(default=None, max_length=100)
    symbol: str | None = Field(default=None, min_length=1, max_length=20)
    quantity: Decimal | None = Field(default=None, gt=0, le=Decimal("9999999999999999.999999999999"))
    avg_cost_tl: Decimal | None = Field(default=None, ge=0, le=Decimal("999999999999.999999"))
    price_source: PriceSource | None = None
    manual_unit_price_tl: Decimal | None = Field(default=None, ge=0, le=Decimal("999999999999.999999"))
    linked_source: LinkedSource | None = None
    linked_id: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v

    @field_validator("avg_cost_tl")
    @classmethod
    def _zero_to_none(cls, v: Decimal | None) -> Decimal | None:
        if v is None or v <= 0:
            return None
        return v


class ManualCryptoOut(BaseModel):
    id: int
    exchange: str
    label: str | None
    symbol: str
    quantity: Decimal
    avg_cost_tl: Decimal | None
    price_source: str
    manual_unit_price_tl: Decimal | None
    linked_source: str | None
    linked_id: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ManualCryptoPositionOut(BaseModel):
    """Anlık fiyatla zenginleştirilmiş pozisyon. Frontend listesi bunu kullanır."""

    id: int
    exchange: str
    label: str | None
    symbol: str
    quantity: Decimal
    avg_cost_tl: Decimal | None
    price_source: str
    manual_unit_price_tl: Decimal | None
    linked_source: str | None
    linked_id: str | None
    unit_price_usd: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal
    cost_basis_tl: Decimal | None
    gain_loss_tl: Decimal | None
    gain_loss_pct: float | None
    notes: str | None


class AssetCatalogItem(BaseModel):
    """Asset catalog endpoint sonucu — fiyat kaynaklarına bağlanabilir bir varlık."""

    source: LinkedSource
    id: str  # binance: 'BTC' (USDT pair base), coingecko: 'bitcoin', tefas: 'AFA', commodity: 'XAU'
    symbol: str | None = None
    name: str


class ManualCryptoSummaryOut(BaseModel):
    positions: list[ManualCryptoPositionOut]
    total_value_tl: Decimal
    unknown_symbols: list[str]
