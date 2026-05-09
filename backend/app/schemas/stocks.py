from decimal import Decimal
from pydantic import BaseModel, field_validator


class StockHolding(BaseModel):
    ticker: str
    quantity: float
    name: str = ""
    avg_cost_tl: float | None = None  # TRY/adet
    distributor: str | None = None     # Örn: "İş Yatırım", "Garanti BBVA Yatırım"

    @field_validator("avg_cost_tl")
    @classmethod
    def normalize_avg_cost(cls, v: float | None) -> float | None:
        # 0 veya negatif değer → None (maliyet bilinmiyor anlamında)
        if v is not None and v <= 0:
            return None
        return v


class StockPositionOut(BaseModel):
    ticker: str
    name: str
    quantity: Decimal
    currency: str
    unit_price_original: Decimal
    unit_price_tl: Decimal
    total_value_tl: Decimal
    # Kâr/zarar — avg_cost_tl girilmemişse None
    avg_cost_tl: Decimal | None = None
    cost_basis_tl: Decimal | None = None
    gain_loss_tl: Decimal | None = None
    gain_loss_pct: float | None = None
    distributor: str | None = None
    # FIN-004 (FAZ H): Eski fiyat (chartPreviousClose fallback ya da regularMarketTime
    # >30 saat). True ise UI rozet gosterir; halted/delisted ihtimaline karsi uyari.
    is_stale: bool = False
    market_state: str | None = None
