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


# SEC-001 (FAZ H): Sifre sifirlama e-postasi (OWASP Forgot Password Cheat Sheet).
def _password_reset_html(reset_url: str, expire_hours: int) -> str:
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; color: #1f2937;">
      <h2 style="color: #111827; margin-bottom: 16px;">Şifre sıfırlama isteği</h2>
      <p style="color: #4b5563; line-height: 1.5;">
        KFinans hesabınız için şifre sıfırlama talebi aldık. Yeni bir şifre belirlemek için aşağıdaki bağlantıya tıklayın:
      </p>
      <p style="margin: 24px 0;">
        <a href="{reset_url}"
           style="background: #dc2626; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; display: inline-block;">
          Şifremi Sıfırla
        </a>
      </p>
      <p style="color: #6b7280; font-size: 14px;">
        Bağlantı çalışmıyorsa kopyalayın:<br>
        <span style="font-family: monospace; word-break: break-all; color: #374151;">{reset_url}</span>
      </p>
      <p style="color: #9ca3af; font-size: 13px; margin-top: 32px; border-top: 1px solid #e5e7eb; padding-top: 16px;">
        Bu bağlantı {expire_hours} saat içinde geçerlidir.
        Bu isteği siz yapmadıysanız e-postayı görmezden gelin; hesabınız güvende.
      </p>
    </div>
    """


async def send_password_reset_email(*, to: str, token: str) -> bool:
    """Kullanıcıya sifre sifirlama linki gonderir."""
    if not _configure():
        logger.warning("RESEND_API_KEY tanımlı değil; reset e-postası gönderilmedi (to=%s)", to)
        return False

    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    payload = {
        "from": settings.email_from,
        "to": [to],
        "subject": "KFinans — Şifre sıfırlama",
        "html": _password_reset_html(reset_url, settings.password_reset_expire_hours),
    }

    try:
        await asyncio.to_thread(resend.Emails.send, payload)
        logger.info("Sifre sifirlama e-postasi gonderildi: %s", to)
        return True
    except Exception:
        logger.exception("Sifre sifirlama e-postasi gonderilemedi: %s", to)
        return False


# Surum bildirimleri (release notes) — opt-in kullanicilara CHANGELOG'tan
# turetilen surum notlarini gonderir. verify/reset mail stiliyle uyumlu sablon.
def _release_notes_html(*, version: str, body_html: str, unsubscribe_url: str) -> str:
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; color: #1f2937;">
      <h2 style="color: #111827; margin-bottom: 4px;">KFinans {version} yayınlandı</h2>
      <p style="color: #6b7280; font-size: 14px; margin-top: 0;">
        Bu sürümle gelen değişiklikler:
      </p>
      <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px 20px; color: #374151; line-height: 1.6; font-size: 14px;">
        {body_html}
      </div>
      <p style="color: #9ca3af; font-size: 13px; margin-top: 32px; border-top: 1px solid #e5e7eb; padding-top: 16px;">
        Bu e-postayı, KFinans hesabınızda sürüm bildirimlerine abone olduğunuz için
        aldınız. Aboneliği bırakmak için
        <a href="{unsubscribe_url}" style="color: #2563eb;">buraya tıklayın</a>
        veya Ayarlar sayfasından bildirimleri kapatın.
      </p>
    </div>
    """


async def send_release_notes_email(*, to: str, version: str, body_html: str, unsubscribe_url: str) -> bool:
    """Tek bir kullanıcıya sürüm bildirimi (release notes) maili gönderir.

    verify/reset pattern'i ile aynı: hata durumunda False döner, exception fırlatmaz.
    """
    if not _configure():
        logger.warning("RESEND_API_KEY tanımlı değil; sürüm bildirimi gönderilmedi (to=%s)", to)
        return False

    payload = {
        "from": settings.email_from,
        "to": [to],
        "subject": f"KFinans {version} — Yenilikler",
        "html": _release_notes_html(version=version, body_html=body_html, unsubscribe_url=unsubscribe_url),
    }

    try:
        await asyncio.to_thread(resend.Emails.send, payload)
        logger.info("Sürüm bildirimi gönderildi: %s (v=%s)", to, version)
        return True
    except Exception:
        logger.exception("Sürüm bildirimi gönderilemedi: %s", to)
        return False


# Ödeme hatırlatması — push'a alternatif, opt-in kullanıcılara ödemesi yaklaşan
# kredi kartı borçlarını özetleyen e-posta. verify/reset stiliyle uyumlu şablon.
def _reminder_status(days) -> tuple[str, str]:
    """days_until_due → (durum metni, renk). <0 gecikti, 0 son gün, >0 kaldı."""
    if isinstance(days, int) and days < 0:
        return f"{abs(days)} gün gecikti", "#dc2626"
    if days == 0:
        return "Son gün", "#dc2626"
    if isinstance(days, int):
        return f"{days} gün kaldı", "#d97706"
    return "-", "#6b7280"


def _payment_reminder_row(item: dict) -> str:
    status_text, status_color = _reminder_status(item.get("days_until_due"))
    card_name = item.get("card_name", "-")
    amount = f"{item.get('amount', '-')} {item.get('currency', '')}"
    due_date = item.get("due_date", "-")
    cell = "padding: 8px 12px; border-bottom: 1px solid #e5e7eb;"
    return f"""
      <tr>
        <td style="{cell}">{card_name}</td>
        <td style="{cell} text-align: right; white-space: nowrap;">{amount}</td>
        <td style="{cell} white-space: nowrap;">{due_date}</td>
        <td style="{cell} color: {status_color}; font-weight: 500; white-space: nowrap;">{status_text}</td>
      </tr>
    """


def _payment_reminder_html(items: list[dict]) -> str:
    rows = "".join(_payment_reminder_row(item) for item in items)
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; color: #1f2937;">
      <h2 style="color: #111827; margin-bottom: 4px;">Yaklaşan kart ödemeleri</h2>
      <p style="color: #6b7280; font-size: 14px; margin-top: 0;">
        Aşağıdaki kredi kartı ekstrelerinin son ödeme tarihi yaklaşıyor:
      </p>
      <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 16px;">
        <thead>
          <tr style="background: #f9fafb; color: #374151; text-align: left;">
            <th style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">Kart</th>
            <th style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">Tutar</th>
            <th style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">Son Ödeme</th>
            <th style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">Durum</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="color: #9ca3af; font-size: 13px; margin-top: 32px; border-top: 1px solid #e5e7eb; padding-top: 16px;">
        Bu e-postayı, KFinans hesabınızda ödeme hatırlatması e-postalarını açtığınız
        için aldınız. Bildirimleri kapatmak için Ayarlar sayfasını kullanın.
      </p>
    </div>
    """


async def send_payment_reminder_email(*, to: str, items: list[dict]) -> bool:
    """Tek bir kullanıcıya ödemesi yaklaşan kart borçlarını özetleyen mail gönderir.

    `items`: her biri {card_name, amount, currency, due_date, days_until_due} dict'i.
    verify/reset pattern'i ile aynı: hata durumunda False döner, exception fırlatmaz.
    RESEND_API_KEY yoksa veya items boşsa no-op + False döner.
    """
    if not items:
        return False
    if not _configure():
        logger.warning("RESEND_API_KEY tanımlı değil; ödeme hatırlatması gönderilmedi (to=%s)", to)
        return False

    payload = {
        "from": settings.email_from,
        "to": [to],
        "subject": "KFinans — Yaklaşan kart ödemeleri",
        "html": _payment_reminder_html(items),
    }

    try:
        await asyncio.to_thread(resend.Emails.send, payload)
        logger.info("Ödeme hatırlatması gönderildi: %s (%d kalem)", to, len(items))
        return True
    except Exception:
        logger.exception("Ödeme hatırlatması gönderilemedi: %s", to)
        return False
