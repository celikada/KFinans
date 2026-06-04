from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserMeOut(BaseModel):
    email: str
    risk_profile: str
    created_at: datetime
    email_verified: bool
    credit_balance: int
    is_admin: bool = False
    release_notes_opt_in: bool = False

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    risk_profile: Literal["conservative", "balanced", "aggressive"]


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
