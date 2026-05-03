from datetime import date as date_type
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

IncomeCategory = Literal["salary", "freelance", "rental", "dividend", "bonus", "sale", "other"]

INCOME_CATEGORIES: tuple[str, ...] = (
    "salary", "freelance", "rental", "dividend", "bonus", "sale", "other"
)

INCOME_CATEGORY_LABELS: dict[str, str] = {
    "salary":    "Maaş",
    "freelance": "Serbest Meslek",
    "rental":    "Kira Geliri",
    "dividend":  "Temettü / Faiz",
    "bonus":     "İkramiye / Prim",
    "sale":      "Varlık Satışı",
    "other":     "Diğer",
}


class IncomeCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, le=99_999_999.99)
    category: IncomeCategory
    date: date_type
    description: Optional[str] = Field(default=None, max_length=500)


class IncomeUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0, le=99_999_999.99)
    category: Optional[IncomeCategory] = None
    date: Optional[date_type] = None
    description: Optional[str] = Field(default=None, max_length=500)


class IncomeOut(BaseModel):
    id: int
    amount: Decimal
    category: str
    date: date_type
    description: Optional[str]

    model_config = {"from_attributes": True}


class IncomeCategoryBreakdown(BaseModel):
    category: str
    total: Decimal
    count: int


class IncomeSummary(BaseModel):
    year: int
    month: int
    total: Decimal
    count: int
    by_category: list[IncomeCategoryBreakdown]
