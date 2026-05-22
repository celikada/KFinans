"""
Audit log altyapisi testleri (FAZ C6).

Hook'lanmis kritik eylemlerin audit_logs tablosuna kayit yazdigini ve
GET /audit-logs endpoint'inin sadece kullanicinin kendi log'larini
dondurdugunu (IDOR korumasi) dogrular.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.conftest import TestSession, verify_user_email


async def _make_user(client: AsyncClient, email: str) -> dict:
    pwd = "guclu-sifre-123"
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd, "age_confirmed": True})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd, "age_confirmed": True})
    return {
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        "user_email": email,
    }


# ─── Hook regression testleri ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_creates_audit_log(client: AsyncClient):
    await _make_user(client, "audit_login@example.com")

    async with TestSession() as db:
        logs = (await db.execute(select(AuditLog).where(AuditLog.action == "auth.login"))).scalars().all()
        # Bu user icin login.action olmali
        emails_in_logs = []
        for log in logs:
            if log.user_id is not None:
                emails_in_logs.append(log.user_id)
        assert len(logs) > 0, "auth.login audit log olusmadi"


@pytest.mark.asyncio
async def test_failed_login_creates_audit_log(client: AsyncClient):
    """Yanlis sifre ile login -> auth.login_failed kaydi."""
    # Once user yarat (ama login etme)
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "audit_fail@example.com",
            "password": "guclu-sifre-123",
            "age_confirmed": True,
        },
    )
    # Yanlis sifre dene
    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "audit_fail@example.com", "password": "yanlissifre"},
    )
    assert bad.status_code == 401

    async with TestSession() as db:
        logs = (await db.execute(select(AuditLog).where(AuditLog.action == "auth.login_failed"))).scalars().all()
        assert len(logs) >= 1
        # extra alani maskeli email tasimali (SEC-010 PII filter)
        from app.core.masking import mask_email

        emails_logged = [log.extra.get("email") for log in logs if log.extra]
        assert mask_email("audit_fail@example.com") in emails_logged


@pytest.mark.asyncio
async def test_wallet_add_creates_audit_log(client: AsyncClient):
    session = await _make_user(client, "audit_wallet@example.com")
    resp = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0x1234567890123456789012345678901234567890"},
        headers=session["headers"],
    )
    assert resp.status_code in (200, 201)

    async with TestSession() as db:
        logs = (await db.execute(select(AuditLog).where(AuditLog.action == "wallet.add"))).scalars().all()
        assert any(log.extra and log.extra.get("chain") == "ethereum" for log in logs)


@pytest.mark.asyncio
async def test_wallet_delete_creates_audit_log(client: AsyncClient):
    session = await _make_user(client, "audit_wallet_del@example.com")
    add = await client.post(
        "/api/v1/wallets",
        json={"chain": "bitcoin", "address": "bc1qexampleaddressrealexampleaddressxyz"},
        headers=session["headers"],
    )
    wallet_id = add.json()["id"]

    delete = await client.delete(f"/api/v1/wallets/{wallet_id}", headers=session["headers"])
    assert delete.status_code == 204

    async with TestSession() as db:
        logs = (await db.execute(select(AuditLog).where(AuditLog.action == "wallet.delete"))).scalars().all()
        assert any(log.resource == f"wallet:{wallet_id}" for log in logs)


@pytest.mark.asyncio
async def test_password_change_creates_audit_log(client: AsyncClient):
    session = await _make_user(client, "audit_pwd@example.com")
    resp = await client.put(
        "/api/v1/user/password",
        json={"current_password": "guclu-sifre-123", "new_password": "yeni-sifre-456"},
        headers=session["headers"],
    )
    assert resp.status_code == 200

    async with TestSession() as db:
        logs = (await db.execute(select(AuditLog).where(AuditLog.action == "auth.password_change"))).scalars().all()
        assert len(logs) >= 1


# ─── GET /audit-logs endpoint testleri ──────────────────────────────────────


@pytest.mark.asyncio
async def test_list_audit_logs_returns_user_own_logs(client: AsyncClient):
    """Kullanici kendi audit log'larini gorebilmeli."""
    session = await _make_user(client, "audit_list@example.com")

    # En az 1 log olusturduk (login)
    resp = await client.get("/api/v1/audit-logs", headers=session["headers"])
    assert resp.status_code == 200
    body = resp.json()
    # PERF-001: PaginatedResponse[T] format
    assert "items" in body and "total_count" in body
    logs = body["items"]
    assert len(logs) >= 1
    assert body["total_count"] >= 1
    # En azindan auth.login olmali
    actions = {log["action"] for log in logs}
    assert "auth.login" in actions


@pytest.mark.asyncio
async def test_list_audit_logs_idor_protection(client: AsyncClient):
    """User A'nin log'lari User B'ye gorunmemeli."""
    session_a = await _make_user(client, "audit_idor_a@example.com")
    session_b = await _make_user(client, "audit_idor_b@example.com")

    # A wallet ekle
    await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0xAAAA000000000000000000000000000000000077"},
        headers=session_a["headers"],
    )

    # B kendi log'larini cek — A'nin wallet.add'i gorunmemeli
    resp_b = await client.get("/api/v1/audit-logs", headers=session_b["headers"])
    assert resp_b.status_code == 200
    actions_b = [log["action"] for log in resp_b.json()["items"]]
    # B sadece kendi auth.login + auth.register'ini gorur, wallet.add yok
    assert "wallet.add" not in actions_b


@pytest.mark.asyncio
async def test_list_audit_logs_action_prefix_filter(client: AsyncClient):
    """action_prefix=wallet. filtresi sadece wallet eylemlerini dondurur."""
    session = await _make_user(client, "audit_filter@example.com")
    await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0xCCCC000000000000000000000000000000000088"},
        headers=session["headers"],
    )

    resp = await client.get(
        "/api/v1/audit-logs?action_prefix=wallet.",
        headers=session["headers"],
    )
    assert resp.status_code == 200
    logs = resp.json()["items"]
    assert len(logs) >= 1
    for log in logs:
        assert log["action"].startswith("wallet.")


@pytest.mark.asyncio
async def test_list_audit_logs_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/audit-logs")
    assert resp.status_code == 401


# ─── PERF-001 (FAZ H): Pagination ──────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_logs_pagination_offset_limit(client: AsyncClient):
    """offset+limit ile sayfalanir; has_next + total_count dogru."""
    session = await _make_user(client, "audit_paginate@example.com")
    # 5 wallet ekle -> 5 wallet.add log + auth.login + auth.register = 7 log
    for i in range(5):
        await client.post(
            "/api/v1/wallets",
            json={"chain": "ethereum", "address": f"0xPAGINATE{i:030x}"},
            headers=session["headers"],
        )

    # Sayfa 1: ilk 3 log
    page1 = await client.get(
        "/api/v1/audit-logs?limit=3&offset=0",
        headers=session["headers"],
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 3
    assert body1["limit"] == 3
    assert body1["offset"] == 0
    assert body1["total_count"] >= 7
    assert body1["has_next"] is True

    # Sayfa 2: offset=3, sonraki 3
    page2 = await client.get(
        "/api/v1/audit-logs?limit=3&offset=3",
        headers=session["headers"],
    )
    body2 = page2.json()
    assert len(body2["items"]) == 3
    assert body2["offset"] == 3
    # Page 1 ve 2'nin item'lari farkli (id'ler farkli)
    page1_ids = {i["id"] for i in body1["items"]}
    page2_ids = {i["id"] for i in body2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_audit_logs_pagination_invalid_limit_returns_422(client: AsyncClient):
    """limit > 500 veya < 1 -> 422."""
    session = await _make_user(client, "audit_pag_invalid@example.com")
    resp = await client.get(
        "/api/v1/audit-logs?limit=1000",
        headers=session["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_audit_logs_pagination_offset_negative_returns_422(client: AsyncClient):
    session = await _make_user(client, "audit_pag_neg@example.com")
    resp = await client.get(
        "/api/v1/audit-logs?offset=-1",
        headers=session["headers"],
    )
    assert resp.status_code == 422
