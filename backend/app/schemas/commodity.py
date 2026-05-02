"""Kıymetli maden (altın/gümüş) Pydantic şemaları."""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.services.commodity import BIGA_GRAM_WEIGHTS, BIGA_METAL, COIN_GRAM_WEIGHTS

VALID_BIGA_CODES = frozenset(BIGA_GRAM_WEIGHTS.keys())
VALID_COIN_TYPES = frozenset(COIN_GRAM_WEIGHTS.keys())


class CommodityCreate(BaseModel):
    unit_type: Literal["gram", "biga", "coin"]
    metal: Literal["gold", "silver"] = "gold"  # coin için görmezden gelinir
    biga_code: Optional[str] = None
    coin_type: Optional[str] = None
    quantity: Decimal = Field(..., gt=0, le=Decimal("99999999.9999"))
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_type(self) -> "CommodityCreate":
        if self.unit_type == "biga":
            if not self.biga_code or self.biga_code not in VALID_BIGA_CODES:
                raise ValueError("Geçerli bir BiGA kodu girin")
            self.metal = BIGA_METAL[self.biga_code]
        elif self.unit_type == "coin":
            if not self.coin_type or self.coin_type not in VALID_COIN_TYPES:
                raise ValueError("Geçerli bir sikke türü girin")
            self.metal = "gold"
        return self


class CommodityUpdate(BaseModel):
    quantity: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("99999999.9999"))
    notes: Optional[str] = Field(default=None, max_length=500)


class CommodityOut(BaseModel):
    id: int
    unit_type: str
    metal: str
    biga_code: Optional[str]
    coin_type: Optional[str]
    quantity: Decimal
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CommodityPositionOut(CommodityOut):
    gram_equivalent: Decimal
    total_value_tl: Decimal
    gold_price_tl: Decimal
    silver_price_tl: Decimal


class CommoditySummaryOut(BaseModel):
    positions: list[CommodityPositionOut]
    total_gold_gram: Decimal
    total_silver_gram: Decimal
    total_value_tl: Decimal
    gold_price_tl: Decimal
    silver_price_tl: Decimal
