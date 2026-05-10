"""TEST-001 (FAZ H): services/audit.py birim testleri.

_client_ip + _user_agent helper'lari + log_audit best-effort davranisi.
DB integration testleri tests/integration/test_audit_logs.py'de — burada
saf birim seviyesinde davranis dogrulanir.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.audit import (
    AuditAction,
    _client_ip,
    _user_agent,
    log_audit,
)


# ─── _client_ip (SEC-004 dogrulama) ─────────────────────────────────────


def test_client_ip_none_when_request_none():
    assert _client_ip(None) is None


def test_client_ip_uses_request_client_host():
    """SEC-004: sadece request.client.host okunur (X-F-F header'i ham
    okumadigi dogrulanir; uvicorn --proxy-headers ile normalize edilir)."""
    req = MagicMock()
    req.client.host = "10.0.5.42"
    assert _client_ip(req) == "10.0.5.42"


def test_client_ip_returns_none_when_client_missing():
    req = MagicMock()
    req.client = None
    assert _client_ip(req) is None


# ─── _user_agent ────────────────────────────────────────────────────────


def test_user_agent_none_when_request_none():
    assert _user_agent(None) is None


def test_user_agent_extracts_from_headers():
    req = MagicMock()
    req.headers = {"user-agent": "Mozilla/5.0 KFinans"}
    assert _user_agent(req) == "Mozilla/5.0 KFinans"


def test_user_agent_truncates_to_512_chars():
    """Cok uzun UA string'i (saldirgan log overflow) 512 char'a kirpilir."""
    req = MagicMock()
    long_ua = "A" * 1000
    req.headers = {"user-agent": long_ua}
    result = _user_agent(req)
    assert result is not None
    assert len(result) == 512


def test_user_agent_empty_returns_none():
    req = MagicMock()
    req.headers = {"user-agent": ""}
    assert _user_agent(req) is None


# ─── log_audit best-effort ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_log_audit_creates_record_and_flushes():
    """log_audit AuditLog instance olusturur ve db.add + db.flush cagirir."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.headers = {"user-agent": "test-ua"}

    user_id = uuid4()
    await log_audit(
        db, req,
        action=AuditAction.LOGIN,
        user_id=user_id,
        resource="session:abc",
        extra={"ip": "127.0.0.1"},
    )

    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    log_arg = db.add.call_args.args[0]
    assert log_arg.action == "auth.login"
    assert log_arg.user_id == user_id
    assert log_arg.resource == "session:abc"
    assert log_arg.ip_address == "127.0.0.1"
    assert log_arg.user_agent == "test-ua"


@pytest.mark.asyncio
async def test_log_audit_swallows_exception(caplog):
    """Audit fail ana endpoint'i bozmamali — exception yutulur, warn log'a yazilir."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=RuntimeError("DB down"))

    with caplog.at_level("WARNING"):
        await log_audit(db, None, action=AuditAction.LOGOUT, user_id=uuid4())

    # Caller'a exception firlatmadi
    assert any("audit log yazilamadi" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_log_audit_action_string_acceptable():
    """AuditAction enum yerine raw string de kabul edilir (geriye uyumluluk)."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    await log_audit(db, None, action="custom.action.foo")

    log_arg = db.add.call_args.args[0]
    assert log_arg.action == "custom.action.foo"
