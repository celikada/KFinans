"""Faz 3 kredi sistemi Pydantic semalari.

PERF-001 standardi: liste PaginatedResponse[T] ile dondurulur.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.pagination import PaginatedResponse


class CreditTransactionOut(BaseModel):
    """Kredi defteri tek hareket cikti semasi."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: int
    reason: str
    reference_id: Optional[str] = None
    extra: Optional[dict] = None
    created_at: datetime


class CreditBalanceOut(BaseModel):
    """GET /credits cikti — anlik bakiye + sayfalanan hareket gecmisi."""

    balance: int
    transactions: PaginatedResponse[CreditTransactionOut]
