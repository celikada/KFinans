from decimal import Decimal
from pydantic import BaseModel, Field


class BesHolding(BaseModel):
    plan_name: str = Field(min_length=1, max_length=200)
    total_value_tl: Decimal = Field(ge=0)
