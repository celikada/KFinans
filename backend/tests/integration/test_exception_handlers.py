"""
BACK-008 + ARC-006 (FAZ H): Generic exception handler regresyon testleri.

Beklenmedik hatalarda 500 information disclosure'i engellendigi ve
{detail, code, request_id} format ile dondugu dogrulanir.

DIKKAT: ASGITransport default'ta `raise_app_exceptions=True` — yani test
client raw Python exception'i yakalayip pytest'e firlatir, FastAPI'nin
exception_handler'lari calismaz. Bu testler icin `raise_app_exceptions=False`
ile ayri AsyncClient kullaniriz.
"""

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.main import app


@pytest.fixture
async def handler_client():
    """ASGITransport(raise_app_exceptions=False) — exception_handler'lari devreye sokar."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Generic 500 handler ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generic_exception_returns_sanitized_500(handler_client: AsyncClient):
    """Beklenmedik Python exception 500 sanitized + request_id ile doner."""

    @app.get("/_test_boom")
    async def _boom():
        raise RuntimeError("ic detay sizmamali — bu mesaj responsa cikmamali")

    try:
        resp = await handler_client.get("/_test_boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"] == "Beklenmedik bir hata olustu"
        assert body["code"] == "internal_error"
        assert "request_id" in body and len(body["request_id"]) == 32
        # Ic detay sizmasin
        assert "ic detay sizmamali" not in body["detail"]
        assert "RuntimeError" not in body["detail"]
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", "") != "/_test_boom"
        ]


# ─── IntegrityError -> 409 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_integrity_error_returns_409(handler_client: AsyncClient):
    """SQLAlchemy IntegrityError 409 Conflict ile sanitized doner."""

    @app.get("/_test_integrity")
    async def _integrity():
        raise IntegrityError("INSERT", {}, Exception("UNIQUE violation"))

    try:
        resp = await handler_client.get("/_test_integrity")
        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "integrity_error"
        assert "request_id" in body
        # SQL detayi sizmasin
        assert "INSERT" not in body["detail"]
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", "") != "/_test_integrity"
        ]


# ─── SQLAlchemy generic -> 500 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sqlalchemy_error_returns_500_db_error(handler_client: AsyncClient):
    """OperationalError 500 'db_error' code ile doner."""

    @app.get("/_test_dberr")
    async def _dberr():
        raise OperationalError("connection failed", {}, Exception("conn"))

    try:
        resp = await handler_client.get("/_test_dberr")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "db_error"
        assert "request_id" in body
        assert "connection failed" not in body["detail"]
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", "") != "/_test_dberr"
        ]


# ─── HTTPException butun handler tarafindan yutulmaz (FastAPI default) ────


@pytest.mark.asyncio
async def test_http_exception_passes_through(handler_client: AsyncClient):
    """HTTPException FastAPI default handler tarafindan islenir, generic'e
    dusmemeli (custom code/request_id eklenmemeli)."""

    @app.get("/_test_http_exc")
    async def _exc():
        raise HTTPException(status_code=404, detail="Bulunamadi")

    try:
        resp = await handler_client.get("/_test_http_exc")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"] == "Bulunamadi"
        # Generic handler'in eklediği code/request_id alanlari OLMAMALI
        assert "code" not in body
        assert "request_id" not in body
    finally:
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", "") != "/_test_http_exc"
        ]
