from decimal import Decimal
from pydantic import BaseModel


class TefasHolding(BaseModel):
    code: str
    quantity: float
    name: str = ""


class TefasPositionOut(BaseModel):
    code: str
    name: str
    quantity: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal
