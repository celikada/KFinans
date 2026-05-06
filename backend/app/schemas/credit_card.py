"""Kredi kartı şemaları (tanım + dönem içi borç)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CreditCardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    bank_name: Optional[str] = Field(default=None, max_length=60)
    last_4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    credit_limit: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    statement_day: int = Field(default=1, ge=1, le=28)
    payment_due_day: int = Field(default=10, ge=1, le=28)
    current_period_debt: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("999999999999.99"))
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("last_4")
    @classmethod
    def _digits_only(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not v.isdigit():
            raise ValueError("last_4 sadece rakam içerebilir")
        return v


class CreditCardUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    bank_name: Optional[str] = Field(default=None, max_length=60)
    last_4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    credit_limit: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    statement_day: Optional[int] = Field(default=None, ge=1, le=28)
    payment_due_day: Optional[int] = Field(default=None, ge=1, le=28)
    current_period_debt: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("999999999999.99"))
    notes: Optional[str] = Field(default=None, max_length=500)


class CreditCardOut(BaseModel):
    id: int
    name: str
    bank_name: Optional[str] = None
    last_4: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    statement_day: int
    payment_due_day: int
    current_period_debt: Decimal
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreditCardSummaryOut(BaseModel):
    """Tüm kartların özet bilgisi (dashboard kartı için)."""
    cards: list[CreditCardOut]
    total_current_period_debt: Decimal  # tüm kartların dönem içi borç toplamı
