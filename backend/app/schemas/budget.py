from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.services.currency import CurrencyType


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
