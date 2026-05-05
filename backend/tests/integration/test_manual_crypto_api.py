"""Manuel kripto (API'siz borsalar) CRUD + preview + Excel testleri.

Binance ve TCMB HTTP çağrıları respx ile mock'lanır.
"""
import io

import openpyxl
import pytest
import respx
from httpx import AsyncClient, Response

from tests.conftest import verify_user_email

BASE = "/api/v1/manual-crypto"

# ---------------------------------------------------------------------------
# Mock fiyatlar
# BTC = 60000 USDT, ETH = 3000 USDT, USD/TRY = 40
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

_BINANCE_PRICES = [
    {"symbol": "BTCUSDT", "price": "60000.00"},
    {"symbol": "ETHUSDT", "price": "3000.00"},
    {"symbol": "SOLUSDT", "price": "150.00"},
]


@pytest.fixture(autouse=True)
def mock_external_http():
    """Binance ticker + TCMB her test için mock'lanır.

    Aggregator'daki TCMB cache'i temizle ki her test temiz başlasın.
    """
    import app.services.aggregator as agg
    agg._tcmb_cache = None

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://www.tcmb.gov.tr/kurlar/today.xml").mock(
            return_value=Response(200, content=_TCMB_XML)
        )
        mock.get("https://api.binance.com/api/v3/ticker/price").mock(
            return_value=Response(200, json=_BINANCE_PRICES)
        )
        yield mock


async def _make_user(client: AsyncClient, email: str) -> dict:
    pwd = "Guclu-Sifre-2026!"
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd})
    await verify_user_email(email)
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": pwd}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ---------------------------------------------------------------------------
# CRUD testleri
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_list(client: AsyncClient):
    """Yeni kullanıcıda boş özet dönmeli."""
    headers = await _make_user(client, "mc_empty@example.com")
    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["positions"] == []
    assert float(data["total_value_tl"]) == 0.0
    assert data["unknown_symbols"] == []


@pytest.mark.asyncio
async def test_create_minimal(client: AsyncClient):
    """Zorunlu alanlarla oluşturma — avg_cost None."""
    headers = await _make_user(client, "mc_create@example.com")
    payload = {
        "exchange": "binancetr",
        "symbol": "BTC",
        "quantity": 0.5,
    }
    resp = await client.post(BASE, json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["exchange"] == "binancetr"
    assert data["symbol"] == "BTC"
    assert float(data["quantity"]) == 0.5
    assert data["avg_cost_tl"] is None


@pytest.mark.asyncio
async def test_symbol_uppercased(client: AsyncClient):
    """Sembol otomatik büyük harfe çevrilmeli."""
    headers = await _make_user(client, "mc_upper@example.com")
    resp = await client.post(BASE, json={"exchange": "icrypex", "symbol": "eth", "quantity": 2}, headers=headers)
    assert resp.json()["symbol"] == "ETH"


@pytest.mark.asyncio
async def test_zero_avg_cost_becomes_none(client: AsyncClient):
    """avg_cost_tl=0 → None (validator)."""
    headers = await _make_user(client, "mc_zero_cost@example.com")
    resp = await client.post(
        BASE,
        json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1, "avg_cost_tl": 0},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["avg_cost_tl"] is None


@pytest.mark.asyncio
async def test_list_with_prices(client: AsyncClient):
    """List endpoint anlık fiyatla zenginleştirir.

    BTC 0.5 @ 60000 USDT, USD/TRY 40 → 0.5 * 60000 * 40 = 1.200.000 TL
    ETH 2 @ 3000 USDT → 2 * 3000 * 40 = 240.000 TL
    Toplam = 1.440.000 TL
    """
    headers = await _make_user(client, "mc_list@example.com")
    await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 0.5}, headers=headers)
    await client.post(BASE, json={"exchange": "icrypex", "symbol": "ETH", "quantity": 2}, headers=headers)

    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["positions"]) == 2
    assert abs(float(data["total_value_tl"]) - 1_440_000.0) < 0.01

    btc_pos = next(p for p in data["positions"] if p["symbol"] == "BTC")
    assert abs(float(btc_pos["unit_price_usd"]) - 60000.0) < 0.01
    assert abs(float(btc_pos["unit_price_tl"]) - 2_400_000.0) < 0.01
    assert abs(float(btc_pos["total_value_tl"]) - 1_200_000.0) < 0.01


@pytest.mark.asyncio
async def test_unknown_symbol_listed(client: AsyncClient):
    """Binance'te bulunmayan sembol unknown_symbols listesine girer + value 0."""
    headers = await _make_user(client, "mc_unknown@example.com")
    await client.post(BASE, json={"exchange": "other", "symbol": "FAKECOIN", "quantity": 100}, headers=headers)

    resp = await client.get(BASE, headers=headers)
    data = resp.json()
    assert "FAKECOIN" in data["unknown_symbols"]
    fake = next(p for p in data["positions"] if p["symbol"] == "FAKECOIN")
    assert float(fake["total_value_tl"]) == 0.0


@pytest.mark.asyncio
async def test_gain_loss_calculated(client: AsyncClient):
    """avg_cost_tl varsa kâr/zarar hesaplanır.

    BTC 1 adet, avg_cost = 1.000.000 TL/adet → cost_basis = 1.000.000
    Anlık değer = 1 * 60000 * 40 = 2.400.000
    Kâr = 1.400.000 (+140%)
    """
    headers = await _make_user(client, "mc_gain@example.com")
    await client.post(
        BASE,
        json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1, "avg_cost_tl": 1_000_000},
        headers=headers,
    )
    resp = await client.get(BASE, headers=headers)
    pos = resp.json()["positions"][0]
    assert abs(float(pos["cost_basis_tl"]) - 1_000_000.0) < 0.01
    assert abs(float(pos["gain_loss_tl"]) - 1_400_000.0) < 0.01
    assert pos["gain_loss_pct"] is not None
    assert abs(pos["gain_loss_pct"] - 140.0) < 0.1


@pytest.mark.asyncio
async def test_update(client: AsyncClient):
    """PUT endpoint quantity değiştirir."""
    headers = await _make_user(client, "mc_update@example.com")
    create = await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=headers)
    holding_id = create.json()["id"]

    resp = await client.put(f"{BASE}/{holding_id}", json={"quantity": 2.5}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["quantity"]) == 2.5


@pytest.mark.asyncio
async def test_delete(client: AsyncClient):
    """DELETE endpoint pozisyonu siler."""
    headers = await _make_user(client, "mc_delete@example.com")
    create = await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=headers)
    holding_id = create.json()["id"]

    resp = await client.delete(f"{BASE}/{holding_id}", headers=headers)
    assert resp.status_code == 204

    # Tekrar liste
    list_resp = await client.get(BASE, headers=headers)
    assert list_resp.json()["positions"] == []


@pytest.mark.asyncio
async def test_idor_protection(client: AsyncClient):
    """Başkasının kaydını silemez/güncelleyemez."""
    h1 = await _make_user(client, "mc_idor1@example.com")
    h2 = await _make_user(client, "mc_idor2@example.com")
    create = await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=h1)
    holding_id = create.json()["id"]

    resp = await client.delete(f"{BASE}/{holding_id}", headers=h2)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Excel testleri
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_excel(client: AsyncClient):
    """Excel export başlık + 1 satır içerir."""
    headers = await _make_user(client, "mc_export@example.com")
    await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 0.5}, headers=headers)

    resp = await client.get(f"{BASE}/export", headers=headers)
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    assert ws.cell(1, 1).value == "Borsa"
    assert ws.cell(2, 1).value == "binancetr"
    assert ws.cell(2, 3).value == "BTC"
    assert float(ws.cell(2, 4).value) == 0.5


@pytest.mark.asyncio
async def test_import_replaces_existing(client: AsyncClient):
    """Import replace-all: mevcut silinir, yeniler eklenir."""
    headers = await _make_user(client, "mc_import@example.com")
    # Önce 1 mevcut kayıt
    await client.post(BASE, json={"exchange": "icrypex", "symbol": "ETH", "quantity": 5}, headers=headers)

    # Excel hazırla — sadece BTC içerir, ETH silinmeli
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Borsa", "Etiket", "Sembol", "Miktar", "Ort. Maliyet (TL)", "Notlar"])
    ws.append(["binancetr", "Spot", "BTC", 0.25, "", "test"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = await client.post(
        f"{BASE}/import",
        headers=headers,
        files={"file": ("import.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 1

    list_resp = await client.get(BASE, headers=headers)
    positions = list_resp.json()["positions"]
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC"
    assert positions[0]["exchange"] == "binancetr"
