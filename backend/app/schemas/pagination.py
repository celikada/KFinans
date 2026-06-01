"""PERF-001 (FAZ H): Ortak pagination schema.

Generic PaginatedResponse[T] — list endpoint'leri buyuk veri'de yavaslamasin
diye `total_count + has_next + items` formati. limit/offset query param.
"""

from pydantic import BaseModel, Field


class PageParams(BaseModel):
    """Query string'ten alinan pagination parametreleri.

    Default 50 — dashboard'da makul; max 500 (DoS koruma)."""

    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper.

    items: filtrelenmis ve sayfalanan satirlar
    total_count: filtrelere uyan TUM satirlarin sayisi (offset/limit oncesi)
    has_next: items + offset < total_count ise True
    """

    items: list[T]
    total_count: int
    limit: int
    offset: int
    has_next: bool
