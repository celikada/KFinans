from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.currency import CurrencyType

BucketType = Literal["fundamental", "fun", "future"]


class BudgetUpsert(BaseModel):
    amount: Decimal = Field(..., gt=0, le=Decimal("99999999.99"))
    # Çoklu para birimi (v0.3.0) — None → kullanıcının default_currency / "TRY".
    currency: Optional[CurrencyType] = None


class BudgetOut(BaseModel):
    id: int
    category: str
    amount: Decimal
    updated_at: datetime
    currency: str = "TRY"

    model_config = {"from_attributes": True}


class BudgetComparison(BaseModel):
    category: str
    budget_amount: Optional[Decimal] = None  # orijinal para biriminde
    # Karşılaştırma TL bazlı yapılır (harcamalar amount_tl, bütçe güncel kurla TL).
    budget_amount_tl: Optional[Decimal] = None
    budget_currency: str = "TRY"
    actual_amount: Decimal  # harcama (amount_tl toplamı, TL)
    remaining: Optional[Decimal] = None  # TL
    pct_used: Optional[float] = None
    over_budget: bool
    # Görüntüleme para birimi karşılıkları (Faz B). actual → gerçekleşmiş giderin
    # tarihsel kuru; budget → güncel kurla display'e. display==TRY → *_display == TL.
    display_currency: str = "TRY"
    budget_amount_display: Optional[Decimal] = None
    actual_amount_display: Decimal = Decimal(0)
    remaining_display: Optional[Decimal] = None


# ─────────────────────────── Bütçe v2 (hibrit) ───────────────────────────


class BudgetLineUpsert(BaseModel):
    """Bir ızgara hücresi (kategori, yıl, ay) için planlanan tutar."""

    amount: Decimal = Field(..., gt=0, le=Decimal("99999999.99"))
    currency: Optional[CurrencyType] = None


class BudgetGridCell(BaseModel):
    """Tek (kategori, ay) hücresi: planlanan + gerçekleşen."""

    month: int
    planned: Optional[Decimal] = None  # orijinal para biriminde (line varsa)
    planned_currency: Optional[str] = None
    planned_display: Optional[Decimal] = None  # görüntüleme birimi
    actual_display: Decimal = Decimal(0)  # gerçekleşen (tarihsel kur → display)


class BudgetGridRow(BaseModel):
    """Bir kategorinin 12 aylık satırı + yıllık toplamlar (display birimi)."""

    category: str
    bucket: BucketType
    cells: list[BudgetGridCell]
    planned_total_display: Decimal = Decimal(0)
    actual_total_display: Decimal = Decimal(0)


class BudgetGridResponse(BaseModel):
    year: int
    display_currency: str = "TRY"
    rows: list[BudgetGridRow]
    # Ay bazında sütun toplamları (12 eleman) + genel toplam (display birimi)
    monthly_planned_display: list[Decimal]
    monthly_actual_display: list[Decimal]
    planned_total_display: Decimal = Decimal(0)
    actual_total_display: Decimal = Decimal(0)


class BucketCategoryRow(BaseModel):
    category: str
    budget_display: Decimal = Decimal(0)
    actual_display: Decimal = Decimal(0)
    difference_display: Decimal = Decimal(0)  # budget - actual
    pct_used: Optional[float] = None
    over_budget: bool = False
    # Aylık-olmayan planlı giderden türetilmiş ağırlıklı satır (yıllık/12) mı?
    weighted: bool = False


class BucketBlock(BaseModel):
    bucket: BucketType
    target_ratio: float
    budget_total_display: Decimal = Decimal(0)
    actual_total_display: Decimal = Decimal(0)
    difference_display: Decimal = Decimal(0)
    actual_ratio: Optional[float] = None  # bu kovanın toplam gider içindeki payı
    categories: list[BucketCategoryRow]


class MonthlyBudgetResponse(BaseModel):
    year: int
    month: int
    display_currency: str = "TRY"
    income_display: Decimal = Decimal(0)
    expense_total_display: Decimal = Decimal(0)
    net_display: Decimal = Decimal(0)  # income - expense
    buckets: list[BucketBlock]


class BudgetSettingsOut(BaseModel):
    fundamental_ratio: float
    fun_ratio: float
    future_ratio: float
    category_buckets: dict[str, BucketType]  # tam çözümlenmiş (default + override)

    model_config = {"from_attributes": True}


class BudgetSettingsUpdate(BaseModel):
    fundamental_ratio: float = Field(..., ge=0, le=1)
    fun_ratio: float = Field(..., ge=0, le=1)
    future_ratio: float = Field(..., ge=0, le=1)
    # Yalnız override edilen kategoriler; boş → kod-içi default.
    category_buckets: Optional[dict[str, BucketType]] = None

    @field_validator("category_buckets")
    @classmethod
    def _valid_category_keys(cls, v: Optional[dict[str, "BucketType"]]):
        """Override anahtarları geçerli kategori olmalı (rastgele/sınırsız anahtar
        saklanmasını engelle — storage abuse + tutarsız kova map'i)."""
        if not v:
            return v
        from app.schemas.expense import EXPENSE_CATEGORIES

        valid = set(EXPENSE_CATEGORIES) | {"savings"}
        invalid = [k for k in v if k not in valid]
        if invalid:
            raise ValueError(f"Geçersiz kategori anahtarı: {', '.join(invalid[:5])}")
        return v

    @model_validator(mode="after")
    def _ratios_sum_to_one(self):
        total = self.fundamental_ratio + self.fun_ratio + self.future_ratio
        if abs(total - 1.0) > 0.001:
            raise ValueError("Kova oranları toplamı 1.0 olmalı")
        return self


class MonthNoteOut(BaseModel):
    year: int
    month: int
    analysis: Optional[str] = None
    action_plan: Optional[str] = None

    model_config = {"from_attributes": True}


class MonthNoteUpdate(BaseModel):
    analysis: Optional[str] = Field(None, max_length=5000)
    action_plan: Optional[str] = Field(None, max_length=5000)

    @field_validator("analysis", "action_plan")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None
