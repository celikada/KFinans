"""Startup secret kontrol testleri (app/core/startup_checks.py)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.config import settings
from app.core import startup_checks


def test_check_critical_secrets_all_valid(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "x" * 40)
    monkeypatch.setattr(settings, "fernet_key", "GIFo3aVen_zgPcKtJaF7ehO1nN7CucqXvZ3X5nU4mO8=")
    monkeypatch.setattr(settings, "resend_api_key", "re_validlookingkey123")
    assert startup_checks.check_critical_secrets() == []


def test_check_critical_secrets_short_secret_key(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "kisa")
    monkeypatch.setattr(settings, "fernet_key", "GIFo3aVen_zgPcKtJaF7ehO1nN7CucqXvZ3X5nU4mO8=")
    monkeypatch.setattr(settings, "resend_api_key", "")
    issues = startup_checks.check_critical_secrets()
    assert any("SECRET_KEY" in i for i in issues)


def test_check_critical_secrets_bad_fernet(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "x" * 40)
    monkeypatch.setattr(settings, "fernet_key", "gecersiz-fernet")
    monkeypatch.setattr(settings, "resend_api_key", "")
    issues = startup_checks.check_critical_secrets()
    assert any("FERNET_KEY" in i for i in issues)


def test_check_critical_secrets_bad_resend_format(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "x" * 40)
    monkeypatch.setattr(settings, "fernet_key", "GIFo3aVen_zgPcKtJaF7ehO1nN7CucqXvZ3X5nU4mO8=")
    monkeypatch.setattr(settings, "resend_api_key", "sk_yanlis_prefix")
    issues = startup_checks.check_critical_secrets()
    assert any("RESEND_API_KEY" in i for i in issues)


@pytest.mark.asyncio
async def test_verify_resend_key_none_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "")
    assert await startup_checks.verify_resend_key() is None


@pytest.mark.asyncio
@respx.mock
async def test_verify_resend_key_valid(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_valid")
    respx.get("https://api.resend.com/domains").mock(return_value=httpx.Response(200, json={"data": []}))
    assert await startup_checks.verify_resend_key() is True


@pytest.mark.asyncio
@respx.mock
async def test_verify_resend_key_invalid_401(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_invalid")
    respx.get("https://api.resend.com/domains").mock(return_value=httpx.Response(401, json={"error": "invalid"}))
    assert await startup_checks.verify_resend_key() is False


@pytest.mark.asyncio
@respx.mock
async def test_verify_resend_key_network_error_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_x")
    respx.get("https://api.resend.com/domains").mock(side_effect=httpx.ConnectError("boom"))
    assert await startup_checks.verify_resend_key() is None
