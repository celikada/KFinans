"""Kıymetli maden (altın/gümüş) CRUD endpoint testleri.

Yahoo Finance ve TCMB HTTP çağrıları respx ile mock'lanır.
Mock sadece bu dosyadaki testler için geçerlidir (autouse=True, scope="module").

Beklenen fiyatlar:
  XAU=X → $3000/troy oz → gold = 3000 / 31.1034768 × 40 ≈ 3861.02 TRY/gram
  XAG=X → $35/troy oz  → silver = 35 / 31.1034768 × 40 ≈ 45.02 TRY/gram
"""

import pytest
import respx
from httpx import AsyncClient, Response

from tests.conftest import make_user

# ---------------------------------------------------------------------------
# TCMB XML yanıtı — USD/TRY = 40.0
# ---------------------------------------------------------------------------
_TCMB_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date>
  <Currency CurrencyCode="USD">
    <Unit>1</Unit>
    <ForexBuying>40.000000</ForexBuying>
    <ForexSelling>40.200000</ForexSelling>
  </Currency>
</Tarih_Date>
"""

# Yahoo Finance Chart API yanıtları
_XAU_RESP = {
    "chart": {
        "result": [{"meta": {"regularMarketPrice": 3000.0, "currency": "USD"}}],
        "error": None,
    }
}
_XAG_RESP = {
    "chart": {
        "result": [{"meta": {"regularMarketPrice": 35.0, "currency": "USD"}}],
        "error": None,
    }
}

# Beklenen değerler (yaklaşık, ondalık tolerans için float karşılaştırması)
_GOLD_TRY = 3000.0 / 31.1034768 * 40  # ≈ 3861.02
_SILVER_TRY = 35.0 / 31.1034768 * 40  # ≈ 45.01


# ---------------------------------------------------------------------------
# Fixture: tüm dış HTTP çağrılarını mock'la
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_metal_http():
    """Yahoo Finance ve TCMB çağrılarını her test için mock'lar.

    app.services.commodity içindeki _price_cache'i sıfırla ki
    önbellek kirlenmesin.
    """
    import app.services.commodity as svc

    svc._price_cache = None  # cache'i temizle

    with respx.mock(assert_all_called=False) as mock:
        # TCMB
        mock.get("https://www.tcmb.gov.tr/kurlar/today.xml").mock(return_value=Response(200, content=_TCMB_XML))
        # XAU=X
        mock.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/XAU=X.*").mock(return_value=Response(200, json=_XAU_RESP))
        # XAG=X
        mock.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/XAG=X.*").mock(return_value=Response(200, json=_XAG_RESP))
        yield mock


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _gram(metal: str, qty: float, notes: str | None = None) -> dict:
    return {"unit_type": "gram", "metal": metal, "quantity": qty, "notes": notes}


def _biga(code: str, qty: float) -> dict:
    return {"unit_type": "biga", "biga_code": code, "quantity": qty}


def _coin(coin_type: str, qty: float) -> dict:
    return {"unit_type": "coin", "coin_type": coin_type, "quantity": qty}


BASE = "/api/v1/portfolio/commodities"


# ---------------------------------------------------------------------------
# Testler
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_list(client: AsyncClient):
    """Yeni kullanıcı için boş özet dönmeli."""
    headers = await make_user(client, "com_empty@example.com")
    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["positions"] == []
    assert float(data["total_value_tl"]) == 0.0
    assert float(data["total_gold_gram"]) == 0.0
    assert float(data["total_silver_gram"]) == 0.0


@pytest.mark.asyncio
async def test_create_gram_gold(client: AsyncClient):
    """Gram altın oluşturma — 201 ve doğru alanlar."""
    headers = await make_user(client, "com_gram_gold@example.com")
    resp = await client.post(BASE, json=_gram("gold", 10.0, "Evde saklı"), headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_type"] == "gram"
    assert data["metal"] == "gold"
    assert float(data["quantity"]) == 10.0
    assert data["notes"] == "Evde saklı"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_gram_silver(client: AsyncClient):
    """Gram gümüş oluşturma — 201 ve metal=silver."""
    headers = await make_user(client, "com_gram_silver@example.com")
    resp = await client.post(BASE, json=_gram("silver", 50.0), headers=headers)
    assert resp.status_code == 201
    assert resp.json()["metal"] == "silver"


@pytest.mark.asyncio
async def test_create_biga_gold(client: AsyncClient):
    """BiGA A01 (1 gram altın) oluşturma."""
    headers = await make_user(client, "com_biga_gold@example.com")
    resp = await client.post(BASE, json=_biga("A01", 5.0), headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_type"] == "biga"
    assert data["biga_code"] == "A01"
    assert data["metal"] == "gold"


@pytest.mark.asyncio
async def test_create_biga_silver(client: AsyncClient):
    """BiGA G01 (1 gram gümüş) oluşturma."""
    headers = await make_user(client, "com_biga_silver@example.com")
    resp = await client.post(BASE, json=_biga("G01", 3.0), headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["biga_code"] == "G01"
    assert data["metal"] == "silver"


@pytest.mark.asyncio
async def test_create_coin_ceyrek(client: AsyncClient):
    """Çeyrek altın sikke oluşturma."""
    headers = await make_user(client, "com_ceyrek@example.com")
    resp = await client.post(BASE, json=_coin("ceyrek", 2.0), headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_type"] == "coin"
    assert data["coin_type"] == "ceyrek"
    assert data["metal"] == "gold"


@pytest.mark.asyncio
async def test_create_coin_tam(client: AsyncClient):
    """Tam altın sikke oluşturma."""
    headers = await make_user(client, "com_tam@example.com")
    resp = await client.post(BASE, json=_coin("tam", 1.0), headers=headers)
    assert resp.status_code == 201
    assert resp.json()["coin_type"] == "tam"


@pytest.mark.asyncio
async def test_create_coin_cumhuriyet(client: AsyncClient):
    """Cumhuriyet altını sikke oluşturma."""
    headers = await make_user(client, "com_cumhuriyet@example.com")
    resp = await client.post(BASE, json=_coin("cumhuriyet", 1.0), headers=headers)
    assert resp.status_code == 201
    assert resp.json()["coin_type"] == "cumhuriyet"


@pytest.mark.asyncio
async def test_create_coin_resat(client: AsyncClient):
    """Reşat altını sikke oluşturma."""
    headers = await make_user(client, "com_resat@example.com")
    resp = await client.post(BASE, json=_coin("resat", 1.0), headers=headers)
    assert resp.status_code == 201
    assert resp.json()["coin_type"] == "resat"


@pytest.mark.asyncio
async def test_create_coin_ata(client: AsyncClient):
    """Ata altını sikke oluşturma."""
    headers = await make_user(client, "com_ata@example.com")
    resp = await client.post(BASE, json=_coin("ata", 1.0), headers=headers)
    assert resp.status_code == 201
    assert resp.json()["coin_type"] == "ata"


@pytest.mark.asyncio
async def test_invalid_biga_code(client: AsyncClient):
    """Geçersiz BiGA kodu → 422."""
    headers = await make_user(client, "com_bad_biga@example.com")
    resp = await client.post(BASE, json={"unit_type": "biga", "biga_code": "Z99", "quantity": 1.0}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_coin_type(client: AsyncClient):
    """Geçersiz sikke türü → 422."""
    headers = await make_user(client, "com_bad_coin@example.com")
    resp = await client.post(BASE, json={"unit_type": "coin", "coin_type": "altin", "quantity": 1.0}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_zero_quantity(client: AsyncClient):
    """Sıfır miktar → 422."""
    headers = await make_user(client, "com_zero@example.com")
    resp = await client.post(BASE, json=_gram("gold", 0.0), headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_quantity(client: AsyncClient):
    """Miktar güncelleme — yeni değer dönmeli."""
    headers = await make_user(client, "com_update@example.com")
    create = await client.post(BASE, json=_gram("gold", 10.0), headers=headers)
    hid = create.json()["id"]

    resp = await client.put(f"{BASE}/{hid}", json={"quantity": 20.0}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["quantity"]) == 20.0


@pytest.mark.asyncio
async def test_delete_holding(client: AsyncClient):
    """Silme — 204 ve liste boş."""
    headers = await make_user(client, "com_delete@example.com")
    create = await client.post(BASE, json=_gram("gold", 5.0), headers=headers)
    hid = create.json()["id"]

    resp = await client.delete(f"{BASE}/{hid}", headers=headers)
    assert resp.status_code == 204

    summary = await client.get(BASE, headers=headers)
    assert summary.json()["positions"] == []


@pytest.mark.asyncio
async def test_idor_update(client: AsyncClient):
    """Başka kullanıcının varlığını güncelleyemez → 404."""
    h1 = await make_user(client, "com_idor1@example.com")
    h2 = await make_user(client, "com_idor2@example.com")

    create = await client.post(BASE, json=_gram("gold", 10.0), headers=h1)
    hid = create.json()["id"]

    resp = await client.put(f"{BASE}/{hid}", json={"quantity": 1.0}, headers=h2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_idor_delete(client: AsyncClient):
    """Başka kullanıcının varlığını silemez → 404."""
    h1 = await make_user(client, "com_idor3@example.com")
    h2 = await make_user(client, "com_idor4@example.com")

    create = await client.post(BASE, json=_gram("gold", 10.0), headers=h1)
    hid = create.json()["id"]

    resp = await client.delete(f"{BASE}/{hid}", headers=h2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated(client: AsyncClient):
    """Auth header olmadan → 401."""
    resp = await client.get(BASE)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_summary_total_value_positive(client: AsyncClient):
    """GET /portfolio/commodities total_value_tl > 0 olmalı."""
    headers = await make_user(client, "com_total@example.com")

    # 10 gram altın + 5 çeyrek sikke
    await client.post(BASE, json=_gram("gold", 10.0), headers=headers)
    await client.post(BASE, json=_coin("ceyrek", 5.0), headers=headers)

    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert float(data["total_value_tl"]) > 0
    assert float(data["gold_price_tl"]) == pytest.approx(_GOLD_TRY, rel=1e-3)
    assert float(data["silver_price_tl"]) == pytest.approx(_SILVER_TRY, rel=1e-3)
    # 10 gram altın + 5 × 1.7517 gram = 10 + 8.7585 = 18.7585 altın gramı
    assert float(data["total_gold_gram"]) == pytest.approx(18.7585, rel=1e-3)
    assert len(data["positions"]) == 2
    for pos in data["positions"]:
        assert float(pos["total_value_tl"]) > 0
