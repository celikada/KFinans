from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class BudgetUpsert(BaseModel):
    amount: Decimal = Field(..., gt=0, le=Decimal("99999999.99"))


class BudgetOut(BaseModel):
    id: int
    category: str
    amount: Decimal
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetComparison(BaseModel):
    category: str
    budget_amount: Optional[Decimal] = None
    actual_amount: Decimal
    remaining: Optional[Decimal] = None
    pct_used: Optional[float] = None
    over_budget: bool
