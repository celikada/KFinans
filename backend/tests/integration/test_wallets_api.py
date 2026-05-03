"""
Blockchain wallet CRUD endpoint'leri.
"""
import pytest
from httpx import AsyncClient


async def _make_user(client: AsyncClient, email: str) -> dict:
    from tests.conftest import verify_user_email
    pwd = "guclu-sifre-123"
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


VALID_ETH = "0x1234567890123456789012345678901234567890"


@pytest.mark.asyncio
async def test_add_wallet_creates_record(client: AsyncClient):
    headers = await _make_user(client, "wallet_add@example.com")
    resp = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": VALID_ETH, "label": "Ana"},
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["chain"] == "ethereum"
    assert data["address"] == VALID_ETH
    assert data["label"] == "Ana"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_wallets_returns_user_wallets(client: AsyncClient):
    headers = await _make_user(client, "wallet_list@example.com")
    chains = [
        ("ethereum", "0xAAAA000000000000000000000000000000000001"),
        ("sonic", "0xAAAA000000000000000000000000000000000002"),
        ("avalanche_c", "0xAAAA000000000000000000000000000000000003"),
    ]
    for chain, addr in chains:
        await client.post(
            "/api/v1/wallets",
            json={"chain": chain, "address": addr},
            headers=headers,
        )

    resp = await client.get("/api/v1/wallets", headers=headers)
    assert resp.status_code == 200
    wallets = resp.json()
    assert len(wallets) == 3
    returned_chains = {w["chain"] for w in wallets}
    assert returned_chains == {"ethereum", "sonic", "avalanche_c"}


@pytest.mark.asyncio
async def test_duplicate_wallet_address_rejected(client: AsyncClient):
    headers = await _make_user(client, "wallet_dup@example.com")
    payload = {"chain": "ethereum", "address": VALID_ETH}
    first = await client.post("/api/v1/wallets", json=payload, headers=headers)
    assert first.status_code in (200, 201)

    second = await client.post("/api/v1/wallets", json=payload, headers=headers)
    assert second.status_code in (400, 409)


@pytest.mark.asyncio
async def test_delete_wallet_removes_record(client: AsyncClient):
    headers = await _make_user(client, "wallet_del@example.com")
    add = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0xCCCC000000000000000000000000000000000001"},
        headers=headers,
    )
    wallet_id = add.json()["id"]

    resp = await client.delete(f"/api/v1/wallets/{wallet_id}", headers=headers)
    assert resp.status_code in (200, 204)

    list_resp = await client.get("/api/v1/wallets", headers=headers)
    ids = [w["id"] for w in list_resp.json()]
    assert wallet_id not in ids


@pytest.mark.asyncio
async def test_invalid_chain_rejected(client: AsyncClient):
    headers = await _make_user(client, "wallet_invalid_chain@example.com")
    resp = await client.post(
        "/api/v1/wallets",
        json={"chain": "fake-chain", "address": VALID_ETH},
        headers=headers,
    )
    assert resp.status_code in (400, 422)
