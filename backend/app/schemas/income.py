from datetime import date as date_type
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

IncomeCategory = Literal["salary", "freelance", "rental", "dividend", "bonus", "sale", "other"]

INCOME_CATEGORIES: tuple[str, ...] = (
    "salary",
    "freelance",
    "rental",
    "dividend",
    "bonus",
    "sale",
    "other",
)

INCOME_CATEGORY_LABELS: dict[str, str] = {
    "salary": "Maaş",
    "freelance": "Serbest Meslek",
    "rental": "Kira Geliri",
    "dividend": "Temettü / Faiz",
    "bonus": "İkramiye / Prim",
    "sale": "Varlık Satışı",
    "other": "Diğer",
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
    description: Optional[str] = None
    recurring_income_id: Optional[int] = None

    model_config = {"from_attributes": True}


class RealizeMonthRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)


class RealizeResult(BaseModel):
    realized: int  # yeni oluşturulan income kaydı sayısı
    skipped: int  # zaten realize edilmiş olduğu için atlanan
    income_ids: list[int]  # yeni kayıtların ID'leri


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


# ---------------------------------------------------------------------------
# Periyodik gelir (recurring_incomes) — maaş, kira vb. tahmini
# ---------------------------------------------------------------------------
RecurringRecurrence = Literal["one_time", "monthly", "quarterly", "biannual", "yearly", "custom"]

RECURRING_INCOME_CATEGORIES = ("salary", "rental", "dividend", "bonus", "freelance", "other")
RECURRING_INCOME_CATEGORY_LABELS: dict[str, str] = {
    "salary": "Maaş",
    "rental": "Kira Geliri",
    "dividend": "Temettü / Faiz",
    "bonus": "İkramiye / Prim",
    "freelance": "Serbest Meslek",
    "other": "Diğer",
}

RECURRING_RECURRENCE_LABELS: dict[str, str] = {
    "one_time": "Tek seferlik",
    "monthly": "Aylık",
    "quarterly": "3 aylık",
    "biannual": "6 aylık",
    "yearly": "Yıllık",
    "custom": "Özel aylar",
}


RecurringIncomeCategory = Literal["salary", "rental", "dividend", "bonus", "freelance", "other"]


class RecurringIncomeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, le=99_999_999.99)
    category: RecurringIncomeCategory
    recurrence: RecurringRecurrence
    months: Optional[list[int]] = Field(
        default=None, description="custom recurrence için ay listesi [1-12]"
    )
    day_of_month: int = Field(default=1, ge=1, le=28)
    start_date: date_type
    end_date: Optional[date_type] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class RecurringIncomeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    amount: Optional[Decimal] = Field(default=None, gt=0, le=99_999_999.99)
    category: Optional[RecurringIncomeCategory] = None
    recurrence: Optional[RecurringRecurrence] = None
    months: Optional[list[int]] = None
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class RecurringIncomeOut(BaseModel):
    id: int
    title: str
    amount: Decimal
    category: str
    recurrence: str
    months: Optional[list[int]] = None
    day_of_month: int
    start_date: date_type
    end_date: Optional[date_type] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class IncomeDashboard(BaseModel):
    """Gelir sayfası özet panel: gerçekleşen + tahmini metrikleri."""

    year: int
    month: int
    this_month_actual: Decimal  # incomes(bu ay) toplamı
    ytd_actual: Decimal  # incomes(yıl başı..bugün)
    this_month_recurring: Decimal  # recurring_incomes(bu ay aktif)
    ytd_recurring: Decimal  # recurring_incomes(yıl başı..bugün geçen)
    remaining_year_recurring: Decimal  # recurring_incomes(bugünden..yıl sonu)
    year_total_estimate: Decimal  # ytd_actual + remaining_year_recurring
