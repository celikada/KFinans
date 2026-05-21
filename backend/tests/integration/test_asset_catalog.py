"""
Asset Catalog API integration testleri.

GET /asset-catalog?q=...&source=...&limit=20 — manuel kripto autocomplete.
4 kaynak: commodity (statik), binance (5 dk cache), coingecko (24h cache), tefas (1h cache).

Bu test'ler ağırlıklı olarak commodity (statik data) ve auth/validation
katmanını doğrular. Dış servis bağımlı kaynaklar (binance/coingecko/tefas)
mock'lanmıştır.
"""

import pytest
import respx
from httpx import AsyncClient, Response

from tests.conftest import make_user

# ─── Auth + validation ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_asset_catalog_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/asset-catalog?q=BTC")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_asset_catalog_limit_validation(client: AsyncClient):
    """limit < 1 veya > 100 → 422."""
    headers = await make_user(client, "ac_limit@example.com")
    bad = await client.get("/api/v1/asset-catalog?limit=0", headers=headers)
    assert bad.status_code == 422
    bad2 = await client.get("/api/v1/asset-catalog?limit=200", headers=headers)
    assert bad2.status_code == 422


@pytest.mark.asyncio
async def test_asset_catalog_q_max_length(client: AsyncClient):
    """q > 100 char → 422."""
    headers = await make_user(client, "ac_q_long@example.com")
    long_q = "x" * 101
    resp = await client.get(f"/api/v1/asset-catalog?q={long_q}", headers=headers)
    assert resp.status_code == 422


# ─── Commodity (statik data, dış servis yok) ───────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_asset_catalog_commodity_xau_search(client: AsyncClient):
    """source=commodity + q=XAU → altın bulunur."""
    headers = await make_user(client, "ac_xau@example.com")
    resp = await client.get("/api/v1/asset-catalog?q=XAU&source=commodity", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    xau = next((it for it in items if it["id"] == "XAU"), None)
    assert xau is not None
    assert xau["source"] == "commodity"
    assert xau["symbol"] == "XAU"
    assert "Altın" in xau["name"] or "Gold" in xau["name"]


@pytest.mark.asyncio
@respx.mock
async def test_asset_catalog_commodity_silver_tr_search(client: AsyncClient):
    """Türkçe arama: 'Gümüş' → XAG bulunur (case-insensitive)."""
    headers = await make_user(client, "ac_silver@example.com")
    resp = await client.get("/api/v1/asset-catalog?q=gümüş&source=commodity", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    xag = next((it for it in items if it["id"] == "XAG"), None)
    assert xag is not None


@pytest.mark.asyncio
@respx.mock
async def test_asset_catalog_commodity_no_match(client: AsyncClient):
    """source=commodity + q='hiç_eşleşmeyen' → boş liste."""
    headers = await make_user(client, "ac_nomatch@example.com")
    resp = await client.get(
        "/api/v1/asset-catalog?q=zzznonexistentzzz&source=commodity", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
@respx.mock
async def test_asset_catalog_commodity_empty_q_returns_all(client: AsyncClient):
    """source=commodity + q='' → 2 commodity (XAU + XAG)."""
    headers = await make_user(client, "ac_all_commodity@example.com")
    resp = await client.get("/api/v1/asset-catalog?q=&source=commodity", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    ids = {it["id"] for it in items}
    assert ids == {"XAU", "XAG"}


# ─── limit parametresi ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_asset_catalog_limit_one(client: AsyncClient):
    """limit=1 → en fazla 1 sonuç."""
    headers = await make_user(client, "ac_limit_1@example.com")
    resp = await client.get("/api/v1/asset-catalog?source=commodity&limit=1", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


# ─── Binance — mock'lu ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_asset_catalog_binance_filter(client: AsyncClient):
    """source=binance — Binance API mock'lanır, BTCUSDT ve ETHUSDT döner."""
    # Binance ticker/price endpoint'i mock'la
    respx.get("https://api.binance.com/api/v3/ticker/price").mock(
        return_value=Response(
            200,
            json=[
                {"symbol": "BTCUSDT", "price": "50000"},
                {"symbol": "ETHUSDT", "price": "3000"},
                {"symbol": "BNBUSDT", "price": "400"},
                {"symbol": "BTCBUSD", "price": "50000"},  # USDT pariteli değil
            ],
        )
    )
    headers = await make_user(client, "ac_binance@example.com")
    resp = await client.get("/api/v1/asset-catalog?q=BTC&source=binance", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    btc = next((it for it in items if it["symbol"] == "BTC"), None)
    assert btc is not None
    assert btc["source"] == "binance"


@pytest.mark.asyncio
@respx.mock
async def test_asset_catalog_invalid_source_returns_empty(client: AsyncClient):
    """source=geçersiz_değer → boş liste (validation hatası değil, silent)."""
    headers = await make_user(client, "ac_bad_source@example.com")
    resp = await client.get("/api/v1/asset-catalog?q=BTC&source=nonexistent", headers=headers)
    assert resp.status_code == 200
    # Geçersiz source: hiçbir _search_* çalışmaz, [] döner
    assert resp.json() == []
