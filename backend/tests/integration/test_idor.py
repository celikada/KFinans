"""
Cross-user erişim testleri (IDOR — Insecure Direct Object Reference).

Her user-owned endpoint için: User A'nın token'ıyla User B'nin kaynağına
erişme denemesi yapılır. Beklenen: 404 veya boş sonuç (erişim yok).

Bu testler regresyon koruması — herhangi bir endpoint user_id filtresini
unutursa bu testler patlar.
"""
import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str) -> dict:
    """Yeni kullanıcı oluştur, token ile birlikte döndür."""
    payload = {"email": email, "password": "guclu-sifre-123"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/login", json=payload)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_tefas_holdings(client: AsyncClient):
    user_a = await _register_and_login(client, "user_a_tefas@example.com")
    user_b = await _register_and_login(client, "user_b_tefas@example.com")

    # User B kendi holdinglerini ekler
    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[{"code": "GO3", "quantity": 100, "name": "B'nin fonu"}],
        headers=user_b,
    )

    # User A kendi listesini çektiğinde B'nin holding'i GÖRÜNMEMELİ
    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=user_a)
    assert resp.status_code == 200
    assert resp.json() == []  # User A'nın holding'i yok


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_stocks(client: AsyncClient):
    user_a = await _register_and_login(client, "user_a_stocks@example.com")
    user_b = await _register_and_login(client, "user_b_stocks@example.com")

    await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[{"ticker": "AAPL", "quantity": 5, "name": "Apple"}],
        headers=user_b,
    )

    resp = await client.get("/api/v1/portfolio/stocks/holdings", headers=user_a)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_wallets(client: AsyncClient):
    user_a = await _register_and_login(client, "user_a_wallets@example.com")
    user_b = await _register_and_login(client, "user_b_wallets@example.com")

    # User B cüzdan ekler
    await client.post(
        "/api/v1/wallets",
        json={
            "chain": "ethereum",
            "address": "0xAAAA000000000000000000000000000000000001",
            "label": "B'nin cüzdani",
        },
        headers=user_b,
    )

    resp = await client.get("/api/v1/wallets", headers=user_a)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_user_a_cannot_delete_user_b_wallet(client: AsyncClient):
    user_a = await _register_and_login(client, "user_a_del@example.com")
    user_b = await _register_and_login(client, "user_b_del@example.com")

    # User B cüzdan ekler ve ID'sini öğrenir
    add_resp = await client.post(
        "/api/v1/wallets",
        json={
            "chain": "ethereum",
            "address": "0xBBBB000000000000000000000000000000000002",
            "label": "B-del",
        },
        headers=user_b,
    )
    wallet_id = add_resp.json()["id"]

    # User A bu wallet_id ile DELETE çağrısı yapar — başarılı olmamalı
    resp = await client.delete(f"/api/v1/wallets/{wallet_id}", headers=user_a)
    # Beklenen: 404 (yok gibi davranılır) — 200/204 ASLA olmamalı
    assert resp.status_code in (404, 403)

    # User B wallet'ı hala görmeli (silinmemiş olmalı)
    list_b = await client.get("/api/v1/wallets", headers=user_b)
    assert any(w["id"] == wallet_id for w in list_b.json())


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_integrations(client: AsyncClient):
    user_a = await _register_and_login(client, "user_a_intg@example.com")
    user_b = await _register_and_login(client, "user_b_intg@example.com")

    # User B Binance entegrasyonu ekler
    await client.post(
        "/api/v1/integrations",
        json={
            "provider": "binance",
            "api_key": "Bnin-API-key",
            "api_secret": "Bnin-API-secret",
        },
        headers=user_b,
    )

    resp = await client.get("/api/v1/integrations", headers=user_a)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_no_token_returns_401(client: AsyncClient):
    """Auth gerektiren endpoint'te token olmadan 401."""
    endpoints = [
        ("GET", "/api/v1/portfolio/tefas/holdings"),
        ("GET", "/api/v1/portfolio/stocks/holdings"),
        ("GET", "/api/v1/wallets"),
        ("GET", "/api/v1/integrations"),
        ("GET", "/api/v1/portfolio"),
        ("GET", "/api/v1/portfolio/changes"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} → {resp.status_code} (401 bekleniyordu)"


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient):
    headers = {"Authorization": "Bearer not.a.valid.jwt.token"}
    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=headers)
    assert resp.status_code == 401
