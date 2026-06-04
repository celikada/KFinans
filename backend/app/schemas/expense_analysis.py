"""Faz 3: Harcama AI analizi request/response schema'lari (Pydantic v2).

Sonuc KALICI tabloda saklanmaz (MVP karari) — ephemeral markdown doner.
Kredi tuketimi credit_transactions ledger'inda izlenir.
"""

from pydantic import BaseModel, ConfigDict, Field


class ExpenseAnalysisRequest(BaseModel):
    """Kac ay geriye analiz edilecegini belirler (bu ay dahil son N ay)."""

    months: int = Field(
        default=6,
        ge=3,
        le=12,
        description="Analiz edilecek geriye donuk ay sayisi (bu ay dahil). 3-12 arasi.",
    )


class AnalysisPeriod(BaseModel):
    """Analiz edilen donemin ozeti (frontend baslik/rozet icin)."""

    months: int
    month_from: str  # "YYYY-MM"
    month_to: str  # "YYYY-MM"
    total_expense: float
    expense_count: int


class ExpenseAnalysisOut(BaseModel):
    analysis: str  # markdown analiz metni (disclaimer dahil)
    credits_used: int
    period: AnalysisPeriod

    model_config = ConfigDict(from_attributes=True)
