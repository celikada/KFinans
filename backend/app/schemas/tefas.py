from decimal import Decimal

from pydantic import BaseModel, field_validator


class TefasHolding(BaseModel):
    code: str
    quantity: float
    name: str = ""
    avg_cost_tl: float | None = None  # TRY/adet
    distributor: str | None = None  # Örn: "Ziraat", "Foneria", "İş Bankası"

    @field_validator("avg_cost_tl")
    @classmethod
    def normalize_avg_cost(cls, v: float | None) -> float | None:
        # 0 veya negatif değer → None (maliyet bilinmiyor anlamında)
        if v is not None and v <= 0:
            return None
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
    distributor: str | None = None
    # TEFAS export'ta o an fiyatlanamayan fon (ör. geçici 0 portföy değeri):
    # pozisyon listede kalır (kullanıcı holding'ini görür) ama fiyat/değer 0 +
    # bu bayrak False → dashboard "fiyat alınamadı" uyarısı gösterir. Tek fiyatsız
    # fon ARTIK tüm TEFAS kartını çökertmez (fault-tolerance).
    price_available: bool = True
