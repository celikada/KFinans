"""Sürüm bildirimleri (release notes) şemaları."""

from pydantic import BaseModel, ConfigDict, Field


class SendReleaseRequest(BaseModel):
    """Admin: belirli bir sürümün notlarını opt-in kullanıcılara gönder."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(..., min_length=1, max_length=40, description="CHANGELOG'taki sürüm token'ı, örn. '0.2.0'")


class SendReleaseResult(BaseModel):
    """Gönderim sonucu: kaç alıcıya başarılı/başarısız gidildiği."""

    version: str
    recipients: int
    sent: int
    failed: int


class ReleaseNotesPreviewOut(BaseModel):
    """Bir sürümün ayrıştırılmış (markdown) notu — önizleme."""

    version: str
    body_markdown: str


class OptInUpdateRequest(BaseModel):
    """Kullanıcının sürüm bildirimi aboneliğini aç/kapat."""

    model_config = ConfigDict(extra="forbid")

    opt_in: bool


class OptInStatusOut(BaseModel):
    """Mevcut abonelik durumu."""

    release_notes_opt_in: bool
