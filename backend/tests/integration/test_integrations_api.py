"""
Integration endpoint'leri — exchange API key encrypt/decrypt akışı.

Kritik: API key'ler asla plaintext dönmemeli; DB'de Fernet ile şifreli.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    """.env'de gercek RESEND_API_KEY var; her register ~3sn gercek (basarisiz)
    network cagrisi yapiyor — testleri yavaslatip flaky yapiyor. No-op patch."""

    async def _noop(*_a, **_k) -> bool:
        return True

    monkeypatch.setattr("app.api.v1.auth.send_verification_email", _noop)
    monkeypatch.setattr("app.api.v1.auth.send_password_reset_email", _noop)


@pytest.mark.asyncio
async def test_create_integration_returns_metadata_only(client: AsyncClient):
    headers = await make_user(client, "intg_create@example.com")
    resp = await client.post(
        "/api/v1/integrations",
        json={
            "provider": "binance",
            "api_key": "TEST-KEY-VISIBLE-ONLY-IN-REQUEST",
            "api_secret": "TEST-SECRET-VISIBLE-ONLY-IN-REQUEST",
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["provider"] == "binance"
    # KRİTİK: API key/secret response'ta DÖNMEMELİ
    text = resp.text
    assert "TEST-KEY-VISIBLE-ONLY-IN-REQUEST" not in text
    assert "TEST-SECRET-VISIBLE-ONLY-IN-REQUEST" not in text


@pytest.mark.asyncio
async def test_list_integrations_does_not_leak_keys(client: AsyncClient):
    headers = await make_user(client, "intg_list@example.com")
    await client.post(
        "/api/v1/integrations",
        json={
            "provider": "binance",
            "api_key": "LEAK-CHECK-KEY",
            "api_secret": "LEAK-CHECK-SECRET",
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/integrations", headers=headers)
    assert resp.status_code == 200
    text = resp.text
    assert "LEAK-CHECK-KEY" not in text
    assert "LEAK-CHECK-SECRET" not in text


@pytest.mark.asyncio
async def test_create_duplicate_provider_handled(client: AsyncClient):
    """Ayni kullanici + provider icin tekrar ekleme: 409 veya update."""
    headers = await make_user(client, "intg_dup@example.com")
    payload = {"provider": "binance", "api_key": "k1", "api_secret": "s1"}
    first = await client.post("/api/v1/integrations", json=payload, headers=headers)
    assert first.status_code in (200, 201)

    second_payload = {**payload, "api_key": "k2", "api_secret": "s2"}
    second = await client.post("/api/v1/integrations", json=second_payload, headers=headers)
    # Ya 409 ya da 200/201 (update davranışı). 500 ASLA olmamalı.
    assert second.status_code in (200, 201, 409)


@pytest.mark.asyncio
async def test_delete_integration_removes_record(client: AsyncClient):
    headers = await make_user(client, "intg_del@example.com")
    await client.post(
        "/api/v1/integrations",
        json={"provider": "icrypex", "api_key": "delk", "api_secret": "dels"},
        headers=headers,
    )
    resp = await client.delete("/api/v1/integrations/icrypex", headers=headers)
    assert resp.status_code in (200, 204)

    list_resp = await client.get("/api/v1/integrations", headers=headers)
    providers = [i["provider"] for i in list_resp.json() if i.get("is_active", True)]
    assert "icrypex" not in providers


@pytest.mark.asyncio
async def test_invalid_provider_rejected(client: AsyncClient):
    headers = await make_user(client, "intg_invalid@example.com")
    resp = await client.post(
        "/api/v1/integrations",
        json={"provider": "fake-exchange-xyz", "api_key": "k", "api_secret": "s"},
        headers=headers,
    )
    assert resp.status_code in (400, 422)


# ─── Ek kapsam: 401, update-existing, sync, delete-404, IDOR ─────────────────


@pytest.mark.asyncio
async def test_list_without_auth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/integrations")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_without_auth_returns_401(client: AsyncClient):
    resp = await client.post(
        "/api/v1/integrations",
        json={"provider": "binance", "api_key": "k", "api_secret": "s"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_then_list_returns_metadata(client: AsyncClient):
    """Eklenen integration list'te is_active + provider ile gorunur."""
    headers = await make_user(client, "intg_meta@example.com")
    create = await client.post(
        "/api/v1/integrations",
        json={"provider": "binance", "api_key": "k1", "api_secret": "s1"},
        headers=headers,
    )
    assert create.json()["is_active"] is True
    assert "id" in create.json()
    listing = await client.get("/api/v1/integrations", headers=headers)
    providers = [i["provider"] for i in listing.json()]
    assert "binance" in providers


@pytest.mark.asyncio
async def test_create_duplicate_updates_existing_record(client: AsyncClient):
    """Ayni provider tekrar POST -> mevcut kayit guncellenir (yeni satir acilmaz)."""
    headers = await make_user(client, "intg_update@example.com")
    first = await client.post(
        "/api/v1/integrations",
        json={"provider": "binance", "api_key": "k1", "api_secret": "s1"},
        headers=headers,
    )
    first_id = first.json()["id"]

    second = await client.post(
        "/api/v1/integrations",
        json={"provider": "binance", "api_key": "k2-new", "api_secret": "s2-new"},
        headers=headers,
    )
    assert second.status_code in (200, 201)
    # Ayni kayit (id degismemis) — update dali
    assert second.json()["id"] == first_id
    assert second.json()["is_active"] is True

    # Sadece 1 binance kaydi olmali
    listing = await client.get("/api/v1/integrations", headers=headers)
    binance_count = sum(1 for i in listing.json() if i["provider"] == "binance")
    assert binance_count == 1


@pytest.mark.asyncio
async def test_create_without_secret(client: AsyncClient):
    """api_secret None — encrypted_secret None kalir, 201."""
    headers = await make_user(client, "intg_nosecret@example.com")
    resp = await client.post(
        "/api/v1/integrations",
        json={"provider": "icrypex", "api_key": "only-key"},
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    assert "only-key" not in resp.text


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(client: AsyncClient):
    headers = await make_user(client, "intg_del404@example.com")
    resp = await client.delete("/api/v1/integrations/binance", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_idor_other_user_returns_404(client: AsyncClient):
    """User B, User A'nin integration'ini silemez (404 — kendi kaydinda yok)."""
    h1 = await make_user(client, "intg_idor_a@example.com")
    h2 = await make_user(client, "intg_idor_b@example.com")
    await client.post(
        "/api/v1/integrations",
        json={"provider": "binance", "api_key": "k", "api_secret": "s"},
        headers=h1,
    )
    resp = await client.delete("/api/v1/integrations/binance", headers=h2)
    assert resp.status_code == 404
    # A'nin kaydi hala duruyor
    listing = await client.get("/api/v1/integrations", headers=h1)
    assert any(i["provider"] == "binance" for i in listing.json())


@pytest.mark.asyncio
async def test_sync_returns_202(client: AsyncClient):
    headers = await make_user(client, "intg_sync@example.com")
    resp = await client.post("/api/v1/integrations/sync", headers=headers)
    assert resp.status_code == 202
    assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_sync_without_auth_returns_401(client: AsyncClient):
    resp = await client.post("/api/v1/integrations/sync")
    assert resp.status_code == 401
