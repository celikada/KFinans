import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_serializer


RiskProfile = Literal["conservative", "balanced", "aggressive"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    risk_profile: RiskProfile = "balanced"


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterResponse(BaseModel):
    id: uuid.UUID
    email: str
    risk_profile: str
    email_verified: bool
    verification_email_sent: bool

    @field_serializer("id")
    def serialize_id(self, v: uuid.UUID) -> str:
        return str(v)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    risk_profile: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("id")
    def serialize_id(self, v: uuid.UUID) -> str:
        return str(v)
