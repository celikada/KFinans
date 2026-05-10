"""TEST-016 (FAZ H): services/email.py — Resend SDK call surface testleri.

resend.Emails.send mock'lanir; gercek HTTP yapilmaz. 4 senaryo:
- Basarili gonderim -> True
- API key tanimsiz -> False (no exception)
- Resend exception (rate_limit / domain not verified) -> False
- _password_reset_html / _verify_email_html dogru URL'i icerir
"""
from unittest.mock import MagicMock, patch

import pytest
import resend

from app.config import settings
from app.services.email import (
    _password_reset_html,
    _verify_email_html,
    send_password_reset_email,
    send_verification_email,
)


@pytest.fixture(autouse=True)
def _restore_resend_key():
    original = settings.resend_api_key
    yield
    settings.resend_api_key = original


# ─── send_verification_email ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_verification_email_sends_when_api_key_set():
    """API key varsa Resend.Emails.send cagrilir, True doner."""
    settings.resend_api_key = "re_test_dummy"

    mock_send = MagicMock(return_value={"id": "msg_123"})
    with patch("resend.Emails.send", mock_send):
        ok = await send_verification_email(to="user@example.com", token="tok123")

    assert ok is True
    mock_send.assert_called_once()
    payload = mock_send.call_args.args[0]
    assert payload["to"] == ["user@example.com"]
    assert "token=tok123" in payload["html"]


@pytest.mark.asyncio
async def test_verification_email_returns_false_without_api_key():
    """API key yoksa False (no exception) — test/dev ortaminda kayit yine
    basarili olmali, frontend `verification_email_sent: False` doner."""
    settings.resend_api_key = ""

    ok = await send_verification_email(to="user@example.com", token="tok123")
    assert ok is False


@pytest.mark.asyncio
async def test_verification_email_swallows_resend_exception():
    """Resend rate limit / domain not verified -> False (logger.exception),
    register endpoint 201 dondurur (kullanici verify-resend ile tekrar deneyebilir)."""
    settings.resend_api_key = "re_test_dummy"

    mock_send = MagicMock(side_effect=Exception("domain not verified"))
    with patch("resend.Emails.send", mock_send):
        ok = await send_verification_email(to="user@example.com", token="tok123")

    assert ok is False  # Exception yakalandi


# ─── send_password_reset_email ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_password_reset_email_sends():
    settings.resend_api_key = "re_test_dummy"

    mock_send = MagicMock(return_value={"id": "msg_456"})
    with patch("resend.Emails.send", mock_send):
        ok = await send_password_reset_email(to="reset@example.com", token="rtok456")

    assert ok is True
    payload = mock_send.call_args.args[0]
    assert "reset-password?token=rtok456" in payload["html"]
    assert payload["subject"] == "KFinans — Şifre sıfırlama"


@pytest.mark.asyncio
async def test_password_reset_email_returns_false_without_api_key():
    settings.resend_api_key = ""
    ok = await send_password_reset_email(to="reset@example.com", token="rtok")
    assert ok is False


@pytest.mark.asyncio
async def test_password_reset_email_swallows_exception():
    settings.resend_api_key = "re_test_dummy"
    mock_send = MagicMock(side_effect=resend.exceptions.ResendError(
        message="rate_limit", code=429, suggested_action="retry", error_type="rate_limit",
    ))
    with patch("resend.Emails.send", mock_send):
        ok = await send_password_reset_email(to="reset@example.com", token="rtok")
    assert ok is False


# ─── HTML helper'lar ────────────────────────────────────────────────────


def test_verify_email_html_includes_token_url():
    """HTML render edilirken token URL'i eksiksiz embed edilmeli."""
    html = _verify_email_html("https://kfinans.app/verify-email?token=abc")
    assert "https://kfinans.app/verify-email?token=abc" in html
    assert "Doğrula" in html or "doğrula" in html


def test_password_reset_html_includes_url_and_ttl():
    html = _password_reset_html("https://kfinans.app/reset-password?token=xyz", 1)
    assert "https://kfinans.app/reset-password?token=xyz" in html
    assert "1 saat" in html
    assert "Sıfırla" in html or "sıfırla" in html
