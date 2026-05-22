from datetime import date as date_type
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Sabit kategori listesi — frontend'de label haritasi var.
# Yeni kategori eklemek istenirse hem buraya hem frontend'e eklenmeli.
ExpenseCategory = Literal[
    "food",  # Yiyecek (restoran, dis yemek)
    "groceries",  # Market, yiyecek alisverisi
    "transport",  # Ulasim (yakit, toplu tasima, taksi)
    "bills",  # Faturalar (elektrik, su, internet, telefon)
    "health",  # Saglik (doktor, ilac, hastane)
    "entertainment",  # Eglence (sinema, oyun, abonelik)
    "clothing",  # Giyim
    "home",  # Ev (kira, mobilya, tamir)
    "tax",  # Vergi, harc
    "other",  # Diger
]

EXPENSE_CATEGORIES: tuple[str, ...] = (
    "food",
    "groceries",
    "transport",
    "bills",
    "health",
    "entertainment",
    "clothing",
    "home",
    "tax",
    "other",
)


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    category: ExpenseCategory
    date: date_type
    description: Optional[str] = Field(default=None, max_length=500)
    credit_card_id: Optional[int] = None
    is_paid: bool = True


class ExpenseUpdate(BaseModel):
    """Tum alanlar opsiyonel — partial update."""

    amount: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("99999999.99"))
    category: Optional[ExpenseCategory] = None
    date: Optional[date_type] = None
    description: Optional[str] = Field(default=None, max_length=500)
    credit_card_id: Optional[int] = None
    is_paid: Optional[bool] = None


class ExpenseOut(BaseModel):
    id: int
    amount: Decimal
    category: str
    date: date_type
    description: Optional[str] = None
    credit_card_id: Optional[int] = None
    is_paid: bool = True

    model_config = {"from_attributes": True}


class CategoryBreakdown(BaseModel):
    category: str
    total: Decimal
    count: int


class ExpenseSummary(BaseModel):
    year: int
    month: int
    total: Decimal
    count: int
    by_category: list[CategoryBreakdown]
