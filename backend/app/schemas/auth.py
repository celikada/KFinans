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
    # COMP-010 (FAZ H): 18+ yas dogrulama (KVKK Kurul karari 2018/482, TMK m.16).
    # Frontend zorunlu checkbox; backend False/eksik -> 422.
    age_confirmed: bool = Field(
        default=False,
        description="18 yasimi doldurdum (KVKK 2018/482, TMK m.16)",
    )


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# SEC-001 (FAZ H): Password reset akisi (OWASP Forgot Password Cheat Sheet).
# 1) /forgot-password (email) -> token uretilir, mail gonderilir, generic 202 doner.
# 2) /reset-password (token + new_password) -> token dogrulanip yeni hash kaydedilir.
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    """Refresh token opsiyonel: yoksa sadece header'daki access blacklist'e alinir."""
    refresh_token: str | None = None


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
