from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AdviceGenerateRequest(BaseModel):
    horizon: str  # medium | long

    def model_post_init(self, __context):
        if self.horizon not in {"medium", "long"}:
            raise ValueError("horizon 'medium' veya 'long' olmalıdır")


class AdviceOut(BaseModel):
    id: str
    horizon: str
    content: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    generated_at: datetime

    class Config:
        from_attributes = True
