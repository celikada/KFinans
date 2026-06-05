"""Periyodik gelir/gider gerçekleşme (realize) + atlama (skip) + bekleyen (pending) şemaları."""

from datetime import date as date_type
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

RecurringKind = Literal["income", "expense"]


class RealizeMonthRequest(BaseModel):
    """Tek bir dönem (ay-yıl) için gerçekleştirme girdisi."""

    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)


class RealizeResult(BaseModel):
    """Realize sonucu: kaç dönem gerçekleşti / atlandı + üretilen kayıt ID'leri."""

    realized: int
    skipped: int
    ids: list[int] = Field(default_factory=list)


class SkipRequest(BaseModel):
    """Bir periyodik tanımın belirli dönemini 'gerçekleşmeyecek' işaretleme."""

    kind: RecurringKind
    ref_id: int
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)


class SkipOut(BaseModel):
    id: int
    kind: RecurringKind
    ref_id: int
    period_year: int
    period_month: int

    model_config = {"from_attributes": True}


class PendingItem(BaseModel):
    """Tarihi geçmiş ama gerçekleşti/gerçekleşmeyecek işaretlenmemiş bir dönem."""

    kind: RecurringKind
    ref_id: int
    title: str
    category: str
    amount: Decimal
    period_year: int
    period_month: int
    occurrence_date: date_type  # o dönemin gerçekleşme tarihi (day_of_month)


class PendingResponse(BaseModel):
    items: list[PendingItem] = Field(default_factory=list)


class RecurringPeriodStatus(BaseModel):
    """Bir periyodik gelirin tek bir dönemi (ay-yıl) ve gerçekleşme durumu.

    status: 'pending' | 'realized' (income_id) | 'skipped' (skip_id). Geri alma:
    realized → /recurring/{id}/unrealize (income silinir), skipped → DELETE
    /recurring/skips/{skip_id}. Planlı gider PeriodStatus ile simetrik."""

    year: int
    month: int
    target_date: date_type
    status: Literal["pending", "realized", "skipped"]
    income_id: Optional[int] = None
    skip_id: Optional[int] = None


class RecurringPeriodsResult(BaseModel):
    periods: list[RecurringPeriodStatus] = Field(default_factory=list)


class RecurringUnrealizeResult(BaseModel):
    """Gelir realize geri alma sonucu: silinen gerçek income sayısı (0 veya 1)."""

    removed: int
