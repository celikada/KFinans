import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_serializer


class AdviceGenerateRequest(BaseModel):
    horizon: str  # medium | long

    def model_post_init(self, __context):
        if self.horizon not in {"medium", "long"}:
            raise ValueError("horizon 'medium' veya 'long' olmalıdır")


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

    class Config:
        from_attributes = True

    @field_serializer("id")
    def _serialize_id(self, v: uuid.UUID) -> str:
        return str(v)
