import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class AdviceGenerateRequest(BaseModel):
    horizon: str  # medium | long

    @field_validator("horizon")
    @classmethod
    def _validate_horizon(cls, v: str) -> str:
        if v not in {"medium", "long"}:
            raise ValueError("horizon 'medium' veya 'long' olmalıdır")
        return v


class AdviceOut(BaseModel):
    # AI-007 (FAZ H): id artik UUID (DB tipi); from_attributes ile UUID otomatik
    # cekilir, JSON response'ta string'e cevrilir.
    id: uuid.UUID
    horizon: str
    content: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    credits_used: int
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id")
    def _serialize_id(self, v: uuid.UUID) -> str:
        return str(v)
