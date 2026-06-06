from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.services.currency import CurrencyType


class UserMeOut(BaseModel):
    email: str
    risk_profile: str
    created_at: datetime
    email_verified: bool
    credit_balance: int
    is_admin: bool = False
    release_notes_opt_in: bool = False
    # Ödeme hatırlatması e-postası (opt-in, default kapalı).
    payment_reminder_email: bool = False
    # v0.3.0 çoklu para birimi: kayıt formu varsayılan para birimi tercihi.
    default_currency: str = "TRY"

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    risk_profile: Literal["conservative", "balanced", "aggressive"]
    # v0.3.0: opsiyonel — verilirse kullanıcının varsayılan para birimi güncellenir.
    default_currency: Optional[CurrencyType] = None
    # Ödeme hatırlatması e-postası tercihi (opsiyonel; verilmezse korunur).
    payment_reminder_email: Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
