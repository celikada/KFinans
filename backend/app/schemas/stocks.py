from decimal import Decimal
from pydantic import BaseModel


class StockHolding(BaseModel):
    ticker: str
    quantity: float
    name: str = ""


class StockPositionOut(BaseModel):
    ticker: str
    name: str
    quantity: Decimal
    currency: str
    unit_price_original: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal
