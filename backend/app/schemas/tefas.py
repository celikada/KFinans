from decimal import Decimal
from pydantic import BaseModel, field_validator


class TefasHolding(BaseModel):
    code: str
    quantity: float
    name: str = ""
    avg_cost_tl: float | None = None  # TRY/adet

    @field_validator("avg_cost_tl")
    @classmethod
    def avg_cost_must_be_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("avg_cost_tl sıfırdan büyük olmalıdır")
        return v


class TefasPositionOut(BaseModel):
    code: str
    name: str
    quantity: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal
    avg_cost_tl: Decimal | None = None
    cost_basis_tl: Decimal | None = None
    gain_loss_tl: Decimal | None = None
    gain_loss_pct: float | None = None
