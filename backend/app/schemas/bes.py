from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class BesHolding(BaseModel):
    plan_name: str = Field(min_length=1, max_length=200)
    contract_number: Optional[str] = Field(default=None, max_length=100)
    paid_principal: Decimal = Field(default=Decimal("0"), ge=0)
    paid_returns: Decimal = Field(default=Decimal("0"), ge=0)
    govt_contribution: Decimal = Field(default=Decimal("0"), ge=0)
    govt_returns: Decimal = Field(default=Decimal("0"), ge=0)

    @property
    def total_value_tl(self) -> Decimal:
        return self.paid_principal + self.paid_returns + self.govt_contribution + self.govt_returns
