"""send_payment_reminder_email (app/services/email.py) saf birim testleri (DB'siz).

resend.Emails.send gerçek ağ çağrısı yapmasın diye mock'lanır.
RESEND_API_KEY yoksa no-op + False döner; items boşsa no-op + False döner.
"""

import pytest

from app.services import email as email_service


@pytest.mark.asyncio
async def test_send_payment_reminder_no_api_key_returns_false(monkeypatch):
    """RESEND_API_KEY tanımlı değilse mail gönderilmez, False döner."""
    monkeypatch.setattr(email_service.settings, "resend_api_key", None, raising=False)
    items = [{"card_name": "Bonus", "amount": "1.500,00", "currency": "TRY", "due_date": "2026-06-10", "days_until_due": 3}]
    result = await email_service.send_payment_reminder_email(to="u@example.com", items=items)
    assert result is False


@pytest.mark.asyncio
async def test_send_payment_reminder_empty_items_noop(monkeypatch):
    """items boşsa configure edilmiş olsa bile no-op + False (gereksiz mail yok)."""
    monkeypatch.setattr(email_service.settings, "resend_api_key", "re_test", raising=False)
    called = {"n": 0}

    def _fake_send(payload):
        called["n"] += 1
        return {"id": "x"}

    monkeypatch.setattr(email_service.resend.Emails, "send", _fake_send)
    result = await email_service.send_payment_reminder_email(to="u@example.com", items=[])
    assert result is False
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_send_payment_reminder_sends_and_returns_true(monkeypatch):
    """Geçerli key + items: resend çağrılır, True döner, payload Türkçe tablo içerir."""
    monkeypatch.setattr(email_service.settings, "resend_api_key", "re_test", raising=False)
    monkeypatch.setattr(email_service.settings, "email_from", "KFinans <no-reply@kfinans.app>", raising=False)
    captured = {}

    def _fake_send(payload):
        captured.update(payload)
        return {"id": "msg_1"}

    monkeypatch.setattr(email_service.resend.Emails, "send", _fake_send)
    items = [
        {"card_name": "Bonus", "amount": "1.500,00", "currency": "TRY", "due_date": "2026-06-10", "days_until_due": 3},
        {"card_name": "Axess", "amount": "900,00", "currency": "USD", "due_date": "2026-06-01", "days_until_due": -2},
    ]
    result = await email_service.send_payment_reminder_email(to="u@example.com", items=items)

    assert result is True
    assert captured["to"] == ["u@example.com"]
    assert "ödeme" in captured["subject"].lower()
    html = captured["html"]
    assert "Bonus" in html and "Axess" in html
    assert "1.500,00" in html and "TRY" in html
    assert "gecikti" in html  # days_until_due < 0 satırı
    assert "gün kaldı" in html  # days_until_due > 0 satırı


@pytest.mark.asyncio
async def test_send_payment_reminder_resend_exception_returns_false(monkeypatch):
    """resend exception fırlatırsa False döner (best-effort, exception sızmaz)."""
    monkeypatch.setattr(email_service.settings, "resend_api_key", "re_test", raising=False)

    def _boom(payload):
        raise RuntimeError("resend down")

    monkeypatch.setattr(email_service.resend.Emails, "send", _boom)
    items = [{"card_name": "Bonus", "amount": "1.500,00", "currency": "TRY", "due_date": "2026-06-10", "days_until_due": 3}]
    result = await email_service.send_payment_reminder_email(to="u@example.com", items=items)
    assert result is False
