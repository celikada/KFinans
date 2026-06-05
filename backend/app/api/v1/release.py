"""Sürüm bildirimleri (release notes) uçları.

- POST /release-notes/send      (admin)  → CHANGELOG'tan sürümü ayrıştır, opt-in
                                            + email_verified kullanıcılara mail.
- GET  /release-notes/preview   (admin)  → bir sürümün ayrıştırılmış notu.
- GET  /release-notes/unsubscribe        → AUTH YOK; token ile aboneliği kapatır.
- PUT  /release-notes/opt-in    (auth)   → kullanıcı kendi aboneliğini aç/kapat.

Markdown→HTML: harici lib yok; `_markdown_to_html` minimal güvenli dönüşüm
(başlık, madde işareti, **kalın**) yapar — kullanıcı içeriği değil, repo'daki
CHANGELOG olduğu için XSS riski düşük; yine de html.escape ile kaçışlanır.
"""

import html as html_lib
import logging
import re
import secrets
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin, get_current_user, get_db
from app.core.limiter import limiter
from app.core.security import decode_token
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.release import (
    OptInStatusOut,
    OptInUpdateRequest,
    ReleaseNotesPreviewOut,
    SendReleaseRequest,
    SendReleaseResult,
)
from app.services import changelog
from app.services.audit import AuditAction, log_audit
from app.services.email import send_release_notes_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/release-notes", tags=["release-notes"])

CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_current_admin)]
DB = Annotated[AsyncSession, Depends(get_db)]

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


async def authorize_release_sender(
    db: DB,
    x_release_token: Annotated[Optional[str], Header()] = None,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Optional[User]:
    """Release-notes gönderim yetkisi: `X-Release-Token` (CI) VEYA admin JWT.

    Token yolu CI/CD otomasyonu için: `settings.release_notes_token` set ise ve
    header sabit-zaman (compare_digest) eşleşiyorsa yetkilidir (kullanıcı yok →
    None döner). Token yoksa/eşleşmezse Bearer admin JWT zorunlu (UI/manuel yol).
    Token boşsa (dev) yalnızca admin JWT geçerlidir."""
    cfg_token = settings.release_notes_token
    if cfg_token and x_release_token and secrets.compare_digest(x_release_token, cfg_token):
        return None  # CI token ile yetkili (audit user_id=None)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekir",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:]
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        jti = payload.get("jti")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")
    if jti:
        revoked = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        if revoked.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token iptal edilmiş")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kimlik doğrulama başarısız")
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için yönetici yetkisi gerekir")
    return user


ReleaseSender = Annotated[Optional[User], Depends(authorize_release_sender)]


def _inline_md(text: str) -> str:
    """Satır içi markdown: önce html.escape, sonra **kalın** → <strong>."""
    escaped = html_lib.escape(text)
    return _BOLD_RE.sub(r"<strong>\1</strong>", escaped)


def _markdown_to_html(md: str) -> str:
    """Basit, güvenli markdown→HTML (başlık, madde, kalın).

    CHANGELOG bloğu satır satır işlenir:
      - "### Başlık" / "## Başlık" → <h4>/<h3>
      - "- madde" / "* madde"      → <ul><li>
      - diğer dolu satırlar         → <p>
    Tüm metin html.escape'ten geçer (defence-in-depth).
    """
    out: list[str] = []
    in_list = False

    def _close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in md.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            _close_list()
            continue
        if stripped.startswith("### "):
            _close_list()
            out.append(f"<h4 style='margin:12px 0 4px;'>{_inline_md(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            _close_list()
            out.append(f"<h3 style='margin:16px 0 4px;'>{_inline_md(stripped[3:])}</h3>")
        elif stripped.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul style='margin:4px 0 4px 18px; padding:0;'>")
                in_list = True
            out.append(f"<li>{_inline_md(stripped[2:])}</li>")
        else:
            _close_list()
            out.append(f"<p style='margin:6px 0;'>{_inline_md(stripped)}</p>")

    _close_list()
    return "\n".join(out)


def _unsubscribe_url(token: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/release-notes/unsubscribe?token={token}"


@router.post("/send", response_model=SendReleaseResult)
@limiter.limit("5/hour")
async def send_release_notes(
    request: Request,
    payload: SendReleaseRequest,
    sender: ReleaseSender,
    db: DB,
):
    """CHANGELOG'tan sürümü ayrıştırıp opt-in + email_verified kullanıcılara mail.

    Yetki: admin JWT (UI/manuel) VEYA `X-Release-Token` (CI/CD otomasyonu)."""
    body_md = changelog.parse_changelog(payload.version)
    if body_md is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CHANGELOG'da '{payload.version}' sürümü bulunamadı",
        )

    body_html = _markdown_to_html(body_md)

    result = await db.execute(
        select(User).where(
            User.release_notes_opt_in.is_(True),
            User.email_verified.is_(True),
            User.deleted_at.is_(None),
        )
    )
    recipients = result.scalars().all()

    sent = 0
    failed = 0
    for user in recipients:
        # unsubscribe_token eski kayitlarda None olabilir — guvenli fallback.
        token = user.unsubscribe_token or ""
        ok = await send_release_notes_email(
            to=user.email,
            version=payload.version,
            body_html=body_html,
            unsubscribe_url=_unsubscribe_url(token),
        )
        if ok:
            sent += 1
        else:
            failed += 1

    await log_audit(
        db,
        request,
        action=AuditAction.RELEASE_NOTES_SENT,
        user_id=sender.id if sender else None,
        resource=f"release:{payload.version}",
        extra={
            "recipients": len(recipients),
            "sent": sent,
            "failed": failed,
            "via": "admin" if sender else "ci_token",
        },
    )
    await db.commit()

    logger.info(
        "Sürüm bildirimi gönderildi: v=%s alıcı=%s başarılı=%s başarısız=%s",
        payload.version,
        len(recipients),
        sent,
        failed,
    )
    return SendReleaseResult(
        version=payload.version,
        recipients=len(recipients),
        sent=sent,
        failed=failed,
    )


@router.get("/preview", response_model=ReleaseNotesPreviewOut)
async def preview_release_notes(
    admin: AdminUser,
    version: Annotated[str, Query(min_length=1, max_length=40)],
):
    """Bir sürümün ayrıştırılmış (markdown) notunu döndürür — gönderim önizleme."""
    body_md = changelog.parse_changelog(version)
    if body_md is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CHANGELOG'da '{version}' sürümü bulunamadı",
        )
    return ReleaseNotesPreviewOut(version=version, body_markdown=body_md)


@router.put("/opt-in", response_model=OptInStatusOut)
async def update_opt_in(
    payload: OptInUpdateRequest,
    current_user: CurrentUser,
    db: DB,
):
    """Kullanıcının sürüm bildirimi aboneliğini aç/kapat (ayarlar sayfası)."""
    current_user.release_notes_opt_in = payload.opt_in
    await db.commit()
    return OptInStatusOut(release_notes_opt_in=current_user.release_notes_opt_in)


@router.get("/opt-in", response_model=OptInStatusOut)
async def get_opt_in(current_user: CurrentUser):
    """Mevcut abonelik durumunu döndürür."""
    return OptInStatusOut(release_notes_opt_in=current_user.release_notes_opt_in)


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(
    db: DB,
    token: Annotated[str, Query(min_length=1, max_length=128)],
):
    """AUTH YOK: token ile eşleşen kullanıcının aboneliğini kapatır.

    Mail içindeki bağlantıdan çağrılır. Geçersiz token → 404. Başarılı durumda
    basit bir HTML onay döner (tarayıcıda doğrudan açılabilir).
    """
    result = await db.execute(select(User).where(User.unsubscribe_token == token))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geçersiz veya süresi dolmuş bağlantı",
        )

    user.release_notes_opt_in = False
    await db.commit()

    return HTMLResponse(
        content=(
            "<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
            "<title>KFinans — Abonelik İptali</title></head>"
            "<body style=\"font-family: -apple-system, 'Segoe UI', sans-serif; "
            'max-width: 480px; margin: 48px auto; padding: 0 24px; color: #1f2937;">'
            "<h2>Aboneliğiniz iptal edildi</h2>"
            "<p>Artık KFinans sürüm bildirimi e-postaları almayacaksınız. "
            "Dilerseniz Ayarlar sayfasından yeniden açabilirsiniz.</p>"
            "</body></html>"
        )
    )
