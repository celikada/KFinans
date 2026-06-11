"""Web Push abonelik + bildirim şemaları (Pydantic v2).

Frontend service worker `PushManager.subscribe()` çıktısını (`endpoint` + `keys`)
`PushSubscriptionIn` ile gönderir; backend `pywebpush` ile şifreli payload iletir.
"""

from typing import Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Yalnız bilinen tarayıcı push servisleri (SSRF koruması): kullanıcı keyfi bir
# `endpoint` kaydedip sunucunun (anında /push/test + her gün cron ile) iç ağa
# (169.254.169.254 metadata, localhost, K8s servis IP'leri) POST atmasını engeller.
_ALLOWED_PUSH_HOST_SUFFIXES = (
    "googleapis.com",  # fcm.googleapis.com, android.googleapis.com (Chrome/Android)
    "push.services.mozilla.com",  # Firefox
    "notify.windows.com",  # Edge / WNS
    "push.apple.com",  # Safari / WebKit
)


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
        parts = urlsplit(v)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("endpoint geçerli bir HTTPS URL olmalı")
        host = parts.hostname.lower()
        # Tam eşleşme ya da alt-domain (".suffix") — "evilgoogleapis.com" eşleşmez.
        if not any(host == s or host.endswith("." + s) for s in _ALLOWED_PUSH_HOST_SUFFIXES):
            raise ValueError("endpoint tanınan bir push servisine ait değil")
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
