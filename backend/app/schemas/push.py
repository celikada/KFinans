"""Web Push abonelik + bildirim şemaları (Pydantic v2).

Frontend service worker `PushManager.subscribe()` çıktısını (`endpoint` + `keys`)
`PushSubscriptionIn` ile gönderir; backend `pywebpush` ile şifreli payload iletir.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PushKeys(BaseModel):
    """Tarayıcının ürettiği ECDH anahtar çifti (base64url)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    p256dh: str = Field(..., min_length=1, max_length=255)
    auth: str = Field(..., min_length=1, max_length=255)


class PushSubscriptionIn(BaseModel):
    """Yeni abonelik kaydı (service worker subscription nesnesi)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    endpoint: str = Field(..., min_length=1, max_length=512)
    keys: PushKeys
    user_agent: Optional[str] = Field(default=None, max_length=400)

    @field_validator("endpoint")
    @classmethod
    def _validate_endpoint(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("endpoint geçerli bir URL olmalı")
        return v


class PushUnsubscribeIn(BaseModel):
    """Abonelik silme — sadece endpoint ile (kendi aboneliği, IDOR-safe)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    endpoint: str = Field(..., min_length=1, max_length=512)


class VapidPublicKeyOut(BaseModel):
    """Frontend'in `PushManager.subscribe()` için ihtiyaç duyduğu public key."""

    public_key: str


class PushTestResult(BaseModel):
    """Test bildirimi sonucu: kaç aboneliğe gönderildi."""

    sent: int
