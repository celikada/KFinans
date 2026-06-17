"""Kişisel borç/alacak (personal_debts) endpoint testleri."""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


@pytest.mark.asyncio
async def test_empty_list(client: AsyncClient):
    headers = await make_user(client, "pd_empty@example.com")
    resp = await client.get("/api/v1/personal-debts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert float(data["net_display"]) == 0.0


@pytest.mark.asyncio
async def test_create_and_summary(client: AsyncClient):
    headers = await make_user(client, "pd_create@example.com")
    await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "Ezgi", "kind": "debt", "amount": 1500, "currency": "TRY"},
        headers=headers,
    )
    await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "İlkem", "kind": "receivable", "amount": 2000, "currency": "TRY"},
        headers=headers,
    )
    resp = await client.get("/api/v1/personal-debts", headers=headers)
    data = resp.json()
    assert len(data["items"]) == 2
    assert float(data["total_debt_display"]) == 1500.0
    assert float(data["total_receivable_display"]) == 2000.0
    assert float(data["net_display"]) == 500.0


@pytest.mark.asyncio
async def test_create_validation(client: AsyncClient):
    headers = await make_user(client, "pd_val@example.com")
    # Boş counterparty
    r1 = await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "", "kind": "debt", "amount": 100},
        headers=headers,
    )
    assert r1.status_code == 422
    # Negatif tutar
    r2 = await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "X", "kind": "debt", "amount": -5},
        headers=headers,
    )
    assert r2.status_code == 422
    # Geçersiz kind
    r3 = await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "X", "kind": "owed", "amount": 5},
        headers=headers,
    )
    assert r3.status_code == 422


@pytest.mark.asyncio
async def test_update(client: AsyncClient):
    headers = await make_user(client, "pd_update@example.com")
    created = await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "Ezgi", "kind": "debt", "amount": 1500},
        headers=headers,
    )
    did = created.json()["id"]
    resp = await client.put(f"/api/v1/personal-debts/{did}", json={"amount": 900, "note": "kısmi ödendi"}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 900.0
    assert resp.json()["note"] == "kısmi ödendi"


@pytest.mark.asyncio
async def test_settle(client: AsyncClient):
    headers = await make_user(client, "pd_settle@example.com")
    created = await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "Ezgi", "kind": "debt", "amount": 1500},
        headers=headers,
    )
    did = created.json()["id"]
    resp = await client.post(f"/api/v1/personal-debts/{did}/settle", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["settled_at"] is not None

    # Varsayılan listede (include_settled=False) görünmez + özet 0.
    listing = await client.get("/api/v1/personal-debts", headers=headers)
    assert listing.json()["items"] == []
    assert float(listing.json()["total_debt_display"]) == 0.0
    # include_settled=True ile görünür.
    with_settled = await client.get("/api/v1/personal-debts?include_settled=true", headers=headers)
    assert len(with_settled.json()["items"]) == 1


@pytest.mark.asyncio
async def test_delete(client: AsyncClient):
    headers = await make_user(client, "pd_delete@example.com")
    created = await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "Ezgi", "kind": "debt", "amount": 1500},
        headers=headers,
    )
    did = created.json()["id"]
    resp = await client.delete(f"/api/v1/personal-debts/{did}", headers=headers)
    assert resp.status_code == 204
    resp404 = await client.delete(f"/api/v1/personal-debts/{did}", headers=headers)
    assert resp404.status_code == 404


@pytest.mark.asyncio
async def test_list_kind_filter(client: AsyncClient):
    headers = await make_user(client, "pd_kind@example.com")
    await client.post("/api/v1/personal-debts", json={"counterparty": "A", "kind": "debt", "amount": 100}, headers=headers)
    await client.post("/api/v1/personal-debts", json={"counterparty": "B", "kind": "receivable", "amount": 200}, headers=headers)
    only_debt = await client.get("/api/v1/personal-debts?kind=debt", headers=headers)
    assert len(only_debt.json()["items"]) == 1
    assert only_debt.json()["items"][0]["kind"] == "debt"


@pytest.mark.asyncio
async def test_settle_idempotent(client: AsyncClient):
    headers = await make_user(client, "pd_settle2@example.com")
    created = await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "Ezgi", "kind": "debt", "amount": 1500},
        headers=headers,
    )
    did = created.json()["id"]
    first = await client.post(f"/api/v1/personal-debts/{did}/settle", headers=headers)
    settled_at = first.json()["settled_at"]
    # İkinci settle çağrısı settled_at'i değiştirmez (idempotent).
    second = await client.post(f"/api/v1/personal-debts/{did}/settle", headers=headers)
    assert second.json()["settled_at"] == settled_at


@pytest.mark.asyncio
async def test_idor(client: AsyncClient):
    h1 = await make_user(client, "pd_idor1@example.com")
    h2 = await make_user(client, "pd_idor2@example.com")
    created = await client.post(
        "/api/v1/personal-debts",
        json={"counterparty": "Ezgi", "kind": "debt", "amount": 1500},
        headers=h1,
    )
    did = created.json()["id"]
    # Başka kullanıcı göremez
    assert (await client.get("/api/v1/personal-debts", headers=h2)).json()["items"] == []
    # Güncelleyemez / silemez / settle edemez
    assert (await client.put(f"/api/v1/personal-debts/{did}", json={"amount": 1}, headers=h2)).status_code == 404
    assert (await client.post(f"/api/v1/personal-debts/{did}/settle", headers=h2)).status_code == 404
    assert (await client.delete(f"/api/v1/personal-debts/{did}", headers=h2)).status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated(client: AsyncClient):
    assert (await client.get("/api/v1/personal-debts")).status_code == 401
    assert (await client.post("/api/v1/personal-debts", json={"counterparty": "X", "kind": "debt", "amount": 1})).status_code == 401
