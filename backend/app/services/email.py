import asyncio
import logging

import resend

from app.config import settings

logger = logging.getLogger(__name__)


def _configure() -> bool:
    if not settings.resend_api_key:
        return False
    resend.api_key = settings.resend_api_key
    return True


def _verify_email_html(verify_url: str) -> str:
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; color: #1f2937;">
      <h2 style="color: #111827; margin-bottom: 16px;">KFinans'a hoş geldiniz</h2>
      <p style="color: #4b5563; line-height: 1.5;">
        Hesabınızı aktifleştirmek için aşağıdaki bağlantıya tıklayın:
      </p>
      <p style="margin: 24px 0;">
        <a href="{verify_url}"
           style="background: #2563eb; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; display: inline-block;">
          E-postamı Doğrula
        </a>
      </p>
      <p style="color: #6b7280; font-size: 14px;">
        Bağlantı çalışmıyorsa kopyalayın:<br>
        <span style="font-family: monospace; word-break: break-all; color: #374151;">{verify_url}</span>
      </p>
      <p style="color: #9ca3af; font-size: 13px; margin-top: 32px; border-top: 1px solid #e5e7eb; padding-top: 16px;">
        Bu bağlantı {settings.verify_token_expire_hours} saat içinde geçerlidir.
        Kayıt isteğini siz yapmadıysanız bu e-postayı yok sayabilirsiniz.
      </p>
    </div>
    """


async def send_verification_email(*, to: str, token: str) -> bool:
    """Kullanıcıya e-posta doğrulama linki gönderir.

    Returns True on success, False on failure (no exception raised).
    """
    if not _configure():
        logger.warning("RESEND_API_KEY tanımlı değil; e-posta gönderilmedi (to=%s)", to)
        return False

    verify_url = f"{settings.frontend_url.rstrip('/')}/verify-email?token={token}"
    payload = {
        "from": settings.email_from,
        "to": [to],
        "subject": "KFinans — E-posta doğrulama",
        "html": _verify_email_html(verify_url),
    }

    try:
        await asyncio.to_thread(resend.Emails.send, payload)
        logger.info("Doğrulama e-postası gönderildi: %s", to)
        return True
    except Exception:
        logger.exception("Doğrulama e-postası gönderilemedi: %s", to)
        return False
