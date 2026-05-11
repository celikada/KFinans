"""SEC-007 (FAZ H): Exception leak sanitization regresyon testleri.

6 leak site (manual_crypto, portfolio, tefas) ham exception mesajini client'a
sizdirmamali. Full trace ops log'a; client'a generic kullanici dostu mesaj.

Pattern: try/except + raise HTTPException(detail=f"...{e}") -> ham exception
class adi veya stack trace ipucu mesaja dahil olursa SEC-007 regression.
"""
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


# ─── manual_crypto._fetch_prices_safe ─────────────────────────────────────


@pytest.mark.asyncio
async def test_manual_crypto_price_fetch_failure_sanitized(client: AsyncClient):
    """fetch_combined_prices Exception fırlatırsa 503 generic mesaj dönmeli,
    exception class veya internal mesaj client'a sizmamali.
    """
    headers = await make_user(client)
    # Bir manuel kripto kaydi ekle ki list endpoint price fetch tetiklesin
    payload = {
        "exchange": "binancetr",
        "symbol": "BTC",
        "quantity": "0.5",
        "price_source": "auto",
    }
    await client.post("/api/v1/manual-crypto", json=payload, headers=headers)

    # fetch_combined_prices'i mock'la — sirri sizdiran exception firlat
    with patch(
        "app.api.v1.manual_crypto.fetch_combined_prices",
        side_effect=RuntimeError("DATABASE_URL=postgresql://kfinans:secret123@host"),
    ):
        resp = await client.get("/api/v1/manual-crypto", headers=headers)

    assert resp.status_code == 503
    body = resp.json()
    detail = body.get("detail", "")
    # Internal mesaj sizmamali
    assert "DATABASE_URL" not in detail
    assert "secret123" not in detail
    assert "RuntimeError" not in detail
    # Generic Turkish message
    assert "Fiyat" in detail or "alınamıyor" in detail


@pytest.mark.asyncio
async def test_manual_crypto_usd_tl_failure_sanitized(client: AsyncClient):
    """fetch_usd_to_tl Exception sanitize edilir."""
    headers = await make_user(client)
    payload = {
        "exchange": "binancetr",
        "symbol": "BTC",
        "quantity": "0.5",
        "price_source": "auto",
    }
    await client.post("/api/v1/manual-crypto", json=payload, headers=headers)

    # fetch_combined_prices ok, ama fetch_usd_to_tl fail
    with patch(
        "app.api.v1.manual_crypto.fetch_combined_prices",
        return_value={"BTC": 100000},
    ), patch(
        "app.api.v1.manual_crypto.fetch_usd_to_tl",
        side_effect=ConnectionError("TCMB internal endpoint xyz unreachable"),
    ):
        resp = await client.get("/api/v1/manual-crypto", headers=headers)

    assert resp.status_code == 503
    body = resp.json()
    detail = body.get("detail", "")
    assert "TCMB internal endpoint" not in detail
    assert "ConnectionError" not in detail
    assert "Döviz" in detail or "kuru" in detail


# ─── portfolio.create_snapshot ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_runtime_error_sanitized(client: AsyncClient):
    """compute_and_save_snapshot RuntimeError fırlatırsa 503 generic mesaj."""
    headers = await make_user(client)

    with patch(
        "app.api.v1.portfolio.compute_and_save_snapshot",
        side_effect=RuntimeError("internal: SELECT * FROM users WHERE password='x'"),
    ):
        resp = await client.post("/api/v1/portfolio/snapshot", headers=headers)

    assert resp.status_code == 503
    body = resp.json()
    detail = body.get("detail", "")
    # SQL veya internal mesaj sizmamali
    assert "SELECT" not in detail
    assert "password" not in detail
    assert "RuntimeError" not in detail
    # Generic Turkish message
    assert "Snapshot" in detail


@pytest.mark.asyncio
async def test_snapshot_preview_runtime_error_sanitized(client: AsyncClient):
    """preview endpoint'i (dry_run) icin de sanitize."""
    headers = await make_user(client)

    with patch(
        "app.api.v1.portfolio.compute_and_save_snapshot",
        side_effect=RuntimeError("Anthropic API key sk-ant-INTERNAL leaked"),
    ):
        resp = await client.post(
            "/api/v1/portfolio/snapshot/preview", headers=headers
        )

    assert resp.status_code == 503
    body = resp.json()
    detail = body.get("detail", "")
    assert "sk-ant" not in detail
    assert "Anthropic" not in detail
    assert "INTERNAL" not in detail
    assert "Snapshot" in detail or "ön kontrol" in detail
