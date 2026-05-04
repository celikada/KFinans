"""Nakit/banka hesabı bakiyesi şemaları."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

CurrencyType = Literal["TRY", "USD", "EUR", "GBP"]


class CashCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., ge=0, le=Decimal("999999999999.99"))
    currency: CurrencyType = "TRY"
    notes: str | None = Field(default=None, max_length=500)


class CashUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    amount: Decimal | None = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    currency: CurrencyType | None = None
    notes: str | None = Field(default=None, max_length=500)


class CashOut(BaseModel):
    id: int
    label: str
    amount: Decimal
    currency: str
    notes: str | None
    updated_at: datetime
    amount_tl: Decimal  # Endpoint'te TL'ye çevrilmiş hali

    model_config = {"from_attributes": True}


class CashSummaryOut(BaseModel):
    holdings: list[CashOut]
    total_tl: Decimal
