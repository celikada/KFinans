"""MFA TOTP schemas (audit #5 MFA).

RFC 6238 standartina uyumlu (Google Authenticator / Authy / 1Password).
Pydantic v2 modern stil — `model_config = ConfigDict(...)` (DEPS-001).
"""

from pydantic import BaseModel, ConfigDict, Field


class MFASetupOut(BaseModel):
    """Setup yanitinda kullaniciya base32 secret + otpauth URI + QR PNG dataURL doneriz.

    `secret_base32` manuel girisi destekler (QR taranamadiginda klavyeyle).
    `qr_png_base64` `data:image/png;base64,...` format'inda — <img src="..."> direkt.
    """

    model_config = ConfigDict(extra="forbid")

    secret_base32: str = Field(description="160-bit base32 TOTP secret (manuel giris icin)")
    otpauth_url: str = Field(description="otpauth://totp/KFinans:email?secret=...&issuer=KFinans")
    qr_png_base64: str = Field(description="data:image/png;base64,... formatinda QR kod")


class MFAEnableIn(BaseModel):
    """Setup'tan sonra ilk dogrulama — kullanicidan 6-haneli TOTP kod ister."""

    model_config = ConfigDict(extra="forbid")

    totp_code: str = Field(
        min_length=6, max_length=8, description="Authenticator uygulamasinin 6 hanesi"
    )


class MFAEnableOut(BaseModel):
    """Enable basarili — recovery code'lari **tek seferlik** plaintext doneriz.

    Kullanicinin bu kodlari guvenli bir yere not etmesi gerekir; DB'de bcrypt
    hash olarak saklanir. Daha sonra GET endpoint'i ile gosterilmez.
    """

    model_config = ConfigDict(extra="forbid")

    recovery_codes: list[str] = Field(
        min_length=10,
        max_length=10,
        description="10 adet tek-kullanimlik recovery kodu (her biri 12 hex)",
    )


class MFAVerifyIn(BaseModel):
    """Login sonrasi pre_mfa_token ile yapilan dogrulama.

    `totp_code` veya `recovery_code` birinin dolu olmasi gerekir; ikisi de
    dolu / ikisi de bos ise 422 verilir (endpoint'te kontrol).
    """

    model_config = ConfigDict(extra="forbid")

    pre_mfa_token: str = Field(min_length=10, max_length=1024)
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=64)


class MFADisableIn(BaseModel):
    """MFA kapatma — totp_code VEYA recovery_code zorunlu."""

    model_config = ConfigDict(extra="forbid")

    totp_code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=64)


class MFALoginRequiredOut(BaseModel):
    """Login response — TOTP enabled ise full access yerine bu doner.

    Frontend `mfa_required=true` gorunce TOTP ekranina yonlendirir; pre_mfa_token
    sadece `/mfa/verify` endpoint'inde gecerli, 15 dk TTL.
    """

    model_config = ConfigDict(extra="forbid")

    mfa_required: bool = True
    pre_mfa_token: str
    expires_in_seconds: int = Field(description="pre_mfa_token gecerlilik suresi (sn)")
