from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.expense import EXPENSE_CATEGORIES, ExpenseCategory


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
    budget_amount: Optional[Decimal]
    actual_amount: Decimal
    remaining: Optional[Decimal]
    pct_used: Optional[float]
    over_budget: bool
