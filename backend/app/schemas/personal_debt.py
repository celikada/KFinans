from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.services.currency import CurrencyType

DebtKind = Literal["debt", "receivable"]


class PersonalDebtCreate(BaseModel):
    counterparty: str = Field(..., min_length=1, max_length=120)
    kind: DebtKind
    amount: Decimal = Field(..., gt=0, le=Decimal("999999999.99"))
    currency: Optional[CurrencyType] = None
    due_date: Optional[date_type] = None
    note: Optional[str] = Field(None, max_length=255)


class PersonalDebtUpdate(BaseModel):
    counterparty: Optional[str] = Field(None, min_length=1, max_length=120)
    kind: Optional[DebtKind] = None
    amount: Optional[Decimal] = Field(None, gt=0, le=Decimal("999999999.99"))
    currency: Optional[CurrencyType] = None
    due_date: Optional[date_type] = None
    note: Optional[str] = Field(None, max_length=255)


class PersonalDebtOut(BaseModel):
    id: int
    counterparty: str
    kind: str
    amount: Decimal
    currency: str = "TRY"
    due_date: Optional[date_type] = None
    note: Optional[str] = None
    settled_at: Optional[datetime] = None
    # Görüntüleme para birimi karşılığı (güncel kur — açık bakiye tahmini niteliğinde).
    amount_display: Decimal = Decimal(0)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonalDebtListOut(BaseModel):
    display_currency: str = "TRY"
    items: list[PersonalDebtOut]
    # Açık (settled olmayan) bakiyeler — görüntüleme biriminde
    total_debt_display: Decimal = Decimal(0)  # kullanıcının borçları
    total_receivable_display: Decimal = Decimal(0)  # alacakları
    net_display: Decimal = Decimal(0)  # receivable - debt
