"""
Integration endpoint'leri — exchange API key encrypt/decrypt akışı.

Kritik: API key'ler asla plaintext dönmemeli; DB'de Fernet ile şifreli.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import make_user



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
        json={"provider": "binance", "api_key": "LEAK-CHECK-KEY", "api_secret": "LEAK-CHECK-SECRET"},
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
