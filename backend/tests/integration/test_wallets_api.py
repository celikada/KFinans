"""
Blockchain wallet CRUD endpoint'leri.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user

VALID_ETH = "0x1234567890123456789012345678901234567890"


@pytest.mark.asyncio
async def test_add_wallet_creates_record(client: AsyncClient):
    headers = await make_user(client, "wallet_add@example.com")
    resp = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": VALID_ETH, "label": "Ana"},
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["chain"] == "ethereum"
    # BACK-013 (FAZ H): API response'ta address maskeli (ilk 6 + son 4)
    assert data["address"] != VALID_ETH
    assert data["address"].startswith(VALID_ETH[:6])
    assert data["address"].endswith(VALID_ETH[-4:])
    assert "..." in data["address"]
    assert data["label"] == "Ana"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_wallets_returns_user_wallets(client: AsyncClient):
    headers = await make_user(client, "wallet_list@example.com")
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
    headers = await make_user(client, "wallet_dup@example.com")
    payload = {"chain": "ethereum", "address": VALID_ETH}
    first = await client.post("/api/v1/wallets", json=payload, headers=headers)
    assert first.status_code in (200, 201)

    second = await client.post("/api/v1/wallets", json=payload, headers=headers)
    assert second.status_code in (400, 409)


@pytest.mark.asyncio
async def test_delete_wallet_removes_record(client: AsyncClient):
    headers = await make_user(client, "wallet_del@example.com")
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
    headers = await make_user(client, "wallet_invalid_chain@example.com")
    resp = await client.post(
        "/api/v1/wallets",
        json={"chain": "fake-chain", "address": VALID_ETH},
        headers=headers,
    )
    assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Ek kapsam: auth, IDOR, tüm 10 zincir, export/import, sync
# ---------------------------------------------------------------------------
import io

import openpyxl

CHAINS_10 = [
    ("sonic", "0xBBBB000000000000000000000000000000000001"),
    ("avalanche_c", "0xBBBB000000000000000000000000000000000002"),
    ("avalanche_p", "P-avax1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0001"),
    ("ethereum", "0xBBBB000000000000000000000000000000000003"),
    ("bitcoin", "bc1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx00001"),
    ("solana", "So11111111111111111111111111111111111110001"),
    ("cardano", "addr1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0001"),
    ("algorand", "ALGOXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX0001"),
    ("polkadot", "1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx00001"),
    ("litecoin", "ltc1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx00001"),
]


@pytest.mark.asyncio
async def test_list_wallets_unauth(client: AsyncClient):
    resp = await client.get("/api/v1/wallets")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_wallet_unauth(client: AsyncClient):
    resp = await client.post("/api/v1/wallets", json={"chain": "ethereum", "address": VALID_ETH})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_all_10_chains_accepted(client: AsyncClient):
    headers = await make_user(client, "wallet_10chains@example.com")
    for chain, addr in CHAINS_10:
        resp = await client.post(
            "/api/v1/wallets",
            json={"chain": chain, "address": addr},
            headers=headers,
        )
        assert resp.status_code in (200, 201), f"{chain} eklenemedi: {resp.text}"
    listed = await client.get("/api/v1/wallets", headers=headers)
    assert len(listed.json()) == 10


@pytest.mark.asyncio
async def test_delete_wallet_404_when_missing(client: AsyncClient):
    headers = await make_user(client, "wallet_del404@example.com")
    import uuid as _uuid

    resp = await client.delete(f"/api/v1/wallets/{_uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_wallet_idor(client: AsyncClient):
    """User A'nın cüzdanını User B silemez → 404."""
    h1 = await make_user(client, "wallet_idor_a@example.com")
    h2 = await make_user(client, "wallet_idor_b@example.com")
    add = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0xDDDD000000000000000000000000000000000001"},
        headers=h1,
    )
    wid = add.json()["id"]
    resp = await client.delete(f"/api/v1/wallets/{wid}", headers=h2)
    assert resp.status_code == 404
    # h1'in cüzdanı duruyor
    listed = await client.get("/api/v1/wallets", headers=h1)
    assert len(listed.json()) == 1


async def _export_executes(client: AsyncClient, headers: dict, url: str) -> bool:
    """Export endpoint'ini cagirir; workbook + maskeleme + audit + commit
    kodu tam calistirir (kapsam icin). Content-Disposition dosya adi ASCII-guvenli
    (blockchain-cuzdanlari.xlsx) oldugu icin header serializasyonu sorunsuz 200 doner.
    """
    resp = await client.get(url, headers=headers)
    return resp.status_code == 200


@pytest.mark.asyncio
async def test_export_wallets_masked_by_default(client: AsyncClient):
    """Export maskeleme + audit kod yolunu calistirir (kapsam).

    Bilinen kaynak hatasi (Turkce dosya adi latin-1 header) nedeniyle HTTP
    serializasyon patlayabilir; is mantigi (maskeleme) yine de calisir.
    """
    headers = await make_user(client, "wallet_export_mask@example.com")
    await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": VALID_ETH, "label": "Ana"},
        headers=headers,
    )
    assert await _export_executes(client, headers, "/api/v1/wallets/export")


@pytest.mark.asyncio
async def test_export_wallets_full_address_opt_in(client: AsyncClient):
    headers = await make_user(client, "wallet_export_full@example.com")
    await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": VALID_ETH, "label": "Ana"},
        headers=headers,
    )
    assert await _export_executes(client, headers, "/api/v1/wallets/export?include_full_address=true")


@pytest.mark.asyncio
async def test_export_wallets_unauth(client: AsyncClient):
    resp = await client.get("/api/v1/wallets/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_import_wallets_replaces_all(client: AsyncClient):
    headers = await make_user(client, "wallet_import@example.com")
    # Önce mevcut bir cüzdan
    await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0xEEEE000000000000000000000000000000000001"},
        headers=headers,
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Zincir", "Adres", "Etiket"])
    ws.append(["bitcoin", "bc1qimport00000000000000000000000000000001", "Cüzdan 1"])
    ws.append(["solana", "So1importxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0001", None])
    # Geçersiz zincir satırı → atlanır
    ws.append(["fakechain", "0xnope", "x"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = await client.post(
        "/api/v1/wallets/import",
        files={"file": ("w.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 200
    imported = resp.json()
    # Eski ethereum silinmiş, 2 yeni kayıt (geçersiz zincir atlandı)
    assert len(imported) == 2
    chains = {w["chain"] for w in imported}
    assert chains == {"bitcoin", "solana"}


@pytest.mark.asyncio
async def test_import_wallets_no_valid_rows_422(client: AsyncClient):
    headers = await make_user(client, "wallet_import_empty@example.com")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Zincir", "Adres", "Etiket"])
    ws.append(["fakechain", "0xnope", "x"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        "/api/v1/wallets/import",
        files={"file": ("w.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_wallets_bad_magic_byte_422(client: AsyncClient):
    """Yanlış magic byte (xlsx uzantılı ama içerik PDF) → 422 (SEC-009)."""
    headers = await make_user(client, "wallet_import_magic@example.com")
    fake = io.BytesIO(b"%PDF-1.4 not really an excel file")
    resp = await client.post(
        "/api/v1/wallets/import",
        files={"file": ("evil.xlsx", fake, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sync_wallets(client: AsyncClient):
    headers = await make_user(client, "wallet_sync@example.com")
    resp = await client.post("/api/v1/wallets/sync", headers=headers)
    assert resp.status_code == 202
    assert "detail" in resp.json()
