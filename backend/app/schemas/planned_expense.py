from datetime import date as date_type
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.services.currency import CurrencyType

PlannedCategory = Literal["loan", "tax", "insurance", "subscription", "rent", "utility", "other"]
PlannedRecurrence = Literal["one_time", "monthly", "quarterly", "biannual", "yearly", "custom"]

PLANNED_CATEGORIES = ("loan", "tax", "insurance", "subscription", "rent", "utility", "other")
PLANNED_RECURRENCES = ("one_time", "monthly", "quarterly", "biannual", "yearly", "custom")

PLANNED_CATEGORY_LABELS: dict[str, str] = {
    "loan": "Kredi / Borç",
    "tax": "Vergi",
    "insurance": "Sigorta",
    "subscription": "Abonelik",
    "rent": "Kira",
    "utility": "Fatura",
    "other": "Diğer",
}

PLANNED_RECURRENCE_LABELS: dict[str, str] = {
    "one_time": "Tek seferlik",
    "monthly": "Aylık",
    "quarterly": "3 aylık",
    "biannual": "6 aylık",
    "yearly": "Yıllık",
    "custom": "Özel aylar",
}


class PlannedExpenseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, le=99999999.99)
    is_estimated: bool = False
    category: PlannedCategory
    recurrence: PlannedRecurrence
    months: Optional[list[int]] = Field(default=None, description="custom recurrence icin ay listesi [1-12]")
    day_of_month: int = Field(default=1, ge=1, le=28)
    start_date: date_type
    end_date: Optional[date_type] = None
    remaining_count: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = Field(default=None, max_length=500)
    credit_card_id: Optional[int] = None
    is_paid: bool = False
    # Çoklu para birimi (v0.3.0) — tahmin; güncel kurla TL'ye çevrilir.
    currency: Optional[CurrencyType] = None


class PlannedExpenseUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    amount: Optional[Decimal] = Field(default=None, gt=0, le=99999999.99)
    is_estimated: Optional[bool] = None
    category: Optional[PlannedCategory] = None
    recurrence: Optional[PlannedRecurrence] = None
    months: Optional[list[int]] = None
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    remaining_count: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = Field(default=None, max_length=500)
    credit_card_id: Optional[int] = None
    is_paid: Optional[bool] = None
    currency: Optional[CurrencyType] = None


class PlannedExpenseOut(BaseModel):
    id: int
    title: str
    amount: Decimal
    is_estimated: bool
    category: str
    recurrence: str
    months: Optional[list[int]] = None
    day_of_month: int
    start_date: date_type
    end_date: Optional[date_type] = None
    remaining_count: Optional[int] = None
    notes: Optional[str] = None
    credit_card_id: Optional[int] = None
    is_paid: bool = False
    currency: str = "TRY"

    model_config = {"from_attributes": True}


class ForecastItem(BaseModel):
    id: int
    title: str
    amount: Decimal
    category: str
    is_estimated: bool


class ForecastMonth(BaseModel):
    month: int
    total: Decimal
    items: list[ForecastItem]


class ForecastResult(BaseModel):
    year: int
    months: list[ForecastMonth]
    year_total: Decimal
