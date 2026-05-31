"""Manuel kripto (API'siz borsalar) CRUD + preview + Excel testleri.

Binance ve TCMB HTTP çağrıları respx ile mock'lanır.
"""

import io

import openpyxl
import pytest
import respx
from httpx import AsyncClient, Response

from tests.conftest import make_user

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

# CoinGecko mock — gerçek /coins/list 5MB, testlerde mocklanır.
_COINGECKO_LIST = [
    {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
    {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
]
# /simple/price?ids=...&vs_currencies=usd → testlerde sadece bilinen ID'ler
_COINGECKO_PRICES: dict = {}


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    """Register sirasinda gercek Resend HTTP cagrisini engelle.

    .env'de gercek RESEND_API_KEY var; her register ~4sn'lik gercek (basarisiz)
    network cagrisi yapiyor. Bu hem yavasliga hem batch kosumda session/DB
    race'ine (db.refresh 'Could not refresh instance') yol aciyor. Test
    ortaminda e-posta gondermek anlamsiz — no-op patch."""

    async def _noop(*_a, **_k) -> bool:
        return True

    monkeypatch.setattr("app.api.v1.auth.send_verification_email", _noop)
    monkeypatch.setattr("app.api.v1.auth.send_password_reset_email", _noop)


@pytest.fixture(autouse=True)
def mock_external_http():
    """Binance + TCMB + CoinGecko + Yahoo (commodity) mock'ları, cache temizle.

    XAU=X 3000 USD/oz → ~3861 TRY/g, XAG=X 35 USD/oz → ~45 TRY/g (USD/TRY=40).
    """
    import app.services.aggregator as agg
    import app.services.commodity as com

    agg._tcmb_cache = None
    agg._coingecko_list_cache = None
    com._price_cache = None

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://www.tcmb.gov.tr/kurlar/today.xml").mock(return_value=Response(200, content=_TCMB_XML))
        mock.get("https://api.binance.com/api/v3/ticker/price").mock(return_value=Response(200, json=_BINANCE_PRICES))
        mock.get("https://api.coingecko.com/api/v3/coins/list").mock(return_value=Response(200, json=_COINGECKO_LIST))
        mock.get(url__regex=r"https://api\.coingecko\.com/api/v3/simple/price.*").mock(return_value=Response(200, json=_COINGECKO_PRICES))
        # Yahoo Finance — altın & gümüş
        mock.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/XAU=X.*").mock(
            return_value=Response(
                200,
                json={
                    "chart": {
                        "result": [{"meta": {"regularMarketPrice": 3000.0, "currency": "USD"}}],
                        "error": None,
                    }
                },
            )
        )
        mock.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/XAG=X.*").mock(
            return_value=Response(
                200,
                json={
                    "chart": {
                        "result": [{"meta": {"regularMarketPrice": 35.0, "currency": "USD"}}],
                        "error": None,
                    }
                },
            )
        )
        yield mock


# ---------------------------------------------------------------------------
# CRUD testleri
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_list(client: AsyncClient):
    """Yeni kullanıcıda boş özet dönmeli."""
    headers = await make_user(client, "mc_empty@example.com")
    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["positions"] == []
    assert float(data["total_value_tl"]) == 0.0
    assert data["unknown_symbols"] == []


@pytest.mark.asyncio
async def test_create_minimal(client: AsyncClient):
    """Zorunlu alanlarla oluşturma — avg_cost None."""
    headers = await make_user(client, "mc_create@example.com")
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
    headers = await make_user(client, "mc_upper@example.com")
    resp = await client.post(BASE, json={"exchange": "icrypex", "symbol": "eth", "quantity": 2}, headers=headers)
    assert resp.json()["symbol"] == "ETH"


@pytest.mark.asyncio
async def test_zero_avg_cost_becomes_none(client: AsyncClient):
    """avg_cost_tl=0 → None (validator)."""
    headers = await make_user(client, "mc_zero_cost@example.com")
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
    headers = await make_user(client, "mc_list@example.com")
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
    headers = await make_user(client, "mc_unknown@example.com")
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
    headers = await make_user(client, "mc_gain@example.com")
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
    headers = await make_user(client, "mc_update@example.com")
    create = await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=headers)
    holding_id = create.json()["id"]

    resp = await client.put(f"{BASE}/{holding_id}", json={"quantity": 2.5}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["quantity"]) == 2.5


@pytest.mark.asyncio
async def test_delete(client: AsyncClient):
    """DELETE endpoint pozisyonu siler."""
    headers = await make_user(client, "mc_delete@example.com")
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
    h1 = await make_user(client, "mc_idor1@example.com")
    h2 = await make_user(client, "mc_idor2@example.com")
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
    headers = await make_user(client, "mc_export@example.com")
    await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 0.5}, headers=headers)

    resp = await client.get(f"{BASE}/export", headers=headers)
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    assert ws.cell(1, 1).value == "Borsa"
    assert ws.cell(2, 1).value == "binancetr"
    assert ws.cell(2, 3).value == "BTC"
    assert float(ws.cell(2, 4).value) == 0.5


# ---------------------------------------------------------------------------
# price_source testleri (manual / gold_gram / silver_gram)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_manual_price_used(client: AsyncClient):
    """price_source='manual' → manual_unit_price_tl kullanılır, Binance lookup'lanmaz.
    100 adet × 50 TL = 5000 TL toplam."""
    headers = await make_user(client, "mc_manual_price@example.com")
    payload = {
        "exchange": "icrypex",
        "symbol": "XAGX",
        "quantity": 100,
        "price_source": "manual",
        "manual_unit_price_tl": 50,
    }
    create = await client.post(BASE, json=payload, headers=headers)
    assert create.status_code == 201
    assert create.json()["price_source"] == "manual"
    assert float(create.json()["manual_unit_price_tl"]) == 50.0

    resp = await client.get(BASE, headers=headers)
    pos = resp.json()["positions"][0]
    assert float(pos["unit_price_tl"]) == 50.0
    assert float(pos["total_value_tl"]) == 5000.0
    # XAGX hala "auto" sınıfında olmadığı için unknown_symbols listesinde olmamalı
    assert "XAGX" not in resp.json()["unknown_symbols"]


@pytest.mark.asyncio
async def test_linked_commodity_silver(client: AsyncClient):
    """price_source='linked', linked_source='commodity', linked_id='XAG'
    → commodity service'ten anlık gümüş gr fiyatı.
    35 USD/oz / 31.10 × 40 ≈ 45 TRY/g."""
    headers = await make_user(client, "mc_linked_xag@example.com")
    payload = {
        "exchange": "icrypex",
        "symbol": "XAGX",
        "quantity": 10,
        "price_source": "linked",
        "linked_source": "commodity",
        "linked_id": "XAG",
    }
    create = await client.post(BASE, json=payload, headers=headers)
    assert create.status_code == 201
    assert create.json()["price_source"] == "linked"
    assert create.json()["linked_source"] == "commodity"
    assert create.json()["linked_id"] == "XAG"

    resp = await client.get(BASE, headers=headers)
    pos = resp.json()["positions"][0]
    assert 44 < float(pos["unit_price_tl"]) < 46
    assert 440 < float(pos["total_value_tl"]) < 460


@pytest.mark.asyncio
async def test_linked_commodity_gold(client: AsyncClient):
    """linked=commodity:XAU → 3000/31.10×40 ≈ 3861 TRY/g."""
    headers = await make_user(client, "mc_linked_xau@example.com")
    payload = {
        "exchange": "icrypex",
        "symbol": "XAUT",
        "quantity": 1,
        "price_source": "linked",
        "linked_source": "commodity",
        "linked_id": "XAU",
    }
    await client.post(BASE, json=payload, headers=headers)
    resp = await client.get(BASE, headers=headers)
    pos = resp.json()["positions"][0]
    assert 3850 < float(pos["unit_price_tl"]) < 3870


@pytest.mark.asyncio
async def test_linked_binance_eth(client: AsyncClient):
    """linked=binance:ETH → ETHUSDT fiyatından TL hesabı.
    ETH=3000 USDT × 40 TRY/USD = 120000 TRY/birim."""
    headers = await make_user(client, "mc_linked_eth@example.com")
    # 'CUSTOM' adlı bir token, fiyatı ETH'a peg
    payload = {
        "exchange": "other",
        "symbol": "MYETHTOKEN",
        "quantity": 2,
        "price_source": "linked",
        "linked_source": "binance",
        "linked_id": "ETH",
    }
    await client.post(BASE, json=payload, headers=headers)
    resp = await client.get(BASE, headers=headers)
    pos = resp.json()["positions"][0]
    assert abs(float(pos["unit_price_tl"]) - 120000.0) < 0.01
    assert abs(float(pos["total_value_tl"]) - 240000.0) < 0.01


@pytest.mark.asyncio
async def test_manual_without_price_zero(client: AsyncClient):
    """price_source='manual' ama manual_unit_price_tl boş → 0 değer + unknown_symbols'da."""
    headers = await make_user(client, "mc_manual_empty@example.com")
    payload = {
        "exchange": "other",
        "symbol": "FAKECOIN",
        "quantity": 100,
        "price_source": "manual",  # manual_unit_price_tl gönderilmiyor
    }
    await client.post(BASE, json=payload, headers=headers)
    resp = await client.get(BASE, headers=headers)
    pos = resp.json()["positions"][0]
    assert float(pos["unit_price_tl"]) == 0.0
    assert "FAKECOIN" in resp.json()["unknown_symbols"]


@pytest.mark.asyncio
async def test_update_price_source_clears_manual(client: AsyncClient):
    """price_source 'manual'dan 'auto'ya geçince manual_unit_price_tl temizlenir."""
    headers = await make_user(client, "mc_clear_manual@example.com")
    create = await client.post(
        BASE,
        json={
            "exchange": "icrypex",
            "symbol": "XAGX",
            "quantity": 10,
            "price_source": "manual",
            "manual_unit_price_tl": 100,
        },
        headers=headers,
    )
    holding_id = create.json()["id"]

    # Auto'ya geçir
    update = await client.put(f"{BASE}/{holding_id}", json={"price_source": "auto"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["price_source"] == "auto"
    assert update.json()["manual_unit_price_tl"] is None


@pytest.mark.asyncio
async def test_update_price_source_clears_linked(client: AsyncClient):
    """linked'tan auto'ya geçince linked_source/linked_id temizlenir."""
    headers = await make_user(client, "mc_clear_linked@example.com")
    create = await client.post(
        BASE,
        json={
            "exchange": "icrypex",
            "symbol": "XAGX",
            "quantity": 10,
            "price_source": "linked",
            "linked_source": "commodity",
            "linked_id": "XAG",
        },
        headers=headers,
    )
    holding_id = create.json()["id"]
    update = await client.put(f"{BASE}/{holding_id}", json={"price_source": "auto"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["price_source"] == "auto"
    assert update.json()["linked_source"] is None
    assert update.json()["linked_id"] is None


@pytest.mark.asyncio
async def test_asset_catalog_search_commodity(client: AsyncClient):
    """asset-catalog 'silver' arar, commodity:XAG bulur."""
    headers = await make_user(client, "mc_catalog@example.com")
    resp = await client.get("/api/v1/asset-catalog?q=silver", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    silver = [r for r in data if r["source"] == "commodity" and r["id"] == "XAG"]
    assert len(silver) == 1


@pytest.mark.asyncio
async def test_asset_catalog_filter_source(client: AsyncClient):
    """source=commodity filtresi sadece commodity döner."""
    headers = await make_user(client, "mc_catalog_filter@example.com")
    resp = await client.get("/api/v1/asset-catalog?source=commodity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2  # XAU + XAG
    assert all(r["source"] == "commodity" for r in data)


@pytest.mark.asyncio
async def test_import_replaces_existing(client: AsyncClient):
    """Import replace-all: mevcut silinir, yeniler eklenir."""
    headers = await make_user(client, "mc_import@example.com")
    # Önce 1 mevcut kayıt
    await client.post(BASE, json={"exchange": "icrypex", "symbol": "ETH", "quantity": 5}, headers=headers)

    # Excel hazırla — sadece BTC içerir, ETH silinmeli
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(
        [
            "Borsa",
            "Etiket",
            "Sembol",
            "Miktar",
            "Ort. Maliyet (TL)",
            "Fiyat Kaynagi",
            "Manuel Fiyat (TL)",
            "Linked Source",
            "Linked ID",
            "Notlar",
        ]
    )
    ws.append(["binancetr", "Spot", "BTC", 0.25, "", "auto", "", "", "", "test"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = await client.post(
        f"{BASE}/import",
        headers=headers,
        files={
            "file": (
                "import.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 1

    list_resp = await client.get(BASE, headers=headers)
    positions = list_resp.json()["positions"]
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC"
    assert positions[0]["exchange"] == "binancetr"


# ---------------------------------------------------------------------------
# Ek kapsam: auth, update 404, linked coingecko/tefas dispatch, import errors
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_without_auth_returns_401(client: AsyncClient):
    resp = await client.get(BASE)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_without_auth_returns_401(client: AsyncClient):
    resp = await client.post(BASE, json={"exchange": "x", "symbol": "BTC", "quantity": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_nonexistent_returns_404(client: AsyncClient):
    headers = await make_user(client, "mc_upd404@example.com")
    resp = await client.put(f"{BASE}/999999", json={"quantity": 2}, headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(client: AsyncClient):
    headers = await make_user(client, "mc_del404@example.com")
    resp = await client.delete(f"{BASE}/999999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_idor_other_user_returns_404(client: AsyncClient):
    """Baskasinin kaydini PUT edemez (404)."""
    h1 = await make_user(client, "mc_updidor1@example.com")
    h2 = await make_user(client, "mc_updidor2@example.com")
    create = await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=h1)
    hid = create.json()["id"]
    resp = await client.put(f"{BASE}/{hid}", json={"quantity": 5}, headers=h2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_all_fields(client: AsyncClient):
    """PUT tum opsiyonel alanlari gunceller (exchange/label/symbol/avg_cost/notes)."""
    headers = await make_user(client, "mc_updall@example.com")
    create = await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=headers)
    hid = create.json()["id"]
    resp = await client.put(
        f"{BASE}/{hid}",
        json={
            "exchange": "icrypex",
            "label": "Yeni Etiket",
            "symbol": "eth",
            "avg_cost_tl": 12345,
            "notes": "guncel not",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exchange"] == "icrypex"
    assert data["label"] == "Yeni Etiket"
    assert data["symbol"] == "ETH"
    assert float(data["avg_cost_tl"]) == 12345.0
    assert data["notes"] == "guncel not"


@pytest.mark.asyncio
async def test_update_to_manual_sets_price(client: AsyncClient):
    """auto -> manual gecisinde manual_unit_price_tl set edilir."""
    headers = await make_user(client, "mc_to_manual@example.com")
    create = await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=headers)
    hid = create.json()["id"]
    resp = await client.put(
        f"{BASE}/{hid}",
        json={"price_source": "manual", "manual_unit_price_tl": 999},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["price_source"] == "manual"
    assert float(resp.json()["manual_unit_price_tl"]) == 999.0


@pytest.mark.asyncio
async def test_update_linked_fields(client: AsyncClient):
    """linked kayitta linked_source/linked_id guncellenir."""
    headers = await make_user(client, "mc_upd_linked@example.com")
    create = await client.post(
        BASE,
        json={
            "exchange": "icrypex",
            "symbol": "XAGX",
            "quantity": 1,
            "price_source": "linked",
            "linked_source": "commodity",
            "linked_id": "XAG",
        },
        headers=headers,
    )
    hid = create.json()["id"]
    resp = await client.put(
        f"{BASE}/{hid}",
        json={"linked_source": "commodity", "linked_id": "XAU"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["linked_id"] == "XAU"


@pytest.mark.asyncio
async def test_linked_coingecko_dispatch(client: AsyncClient):
    """linked=coingecko:ID — fiyat bulunamazsa 0 + unknown (dispatch dali calisir)."""
    headers = await make_user(client, "mc_linked_cg@example.com")
    payload = {
        "exchange": "other",
        "symbol": "TGOLD",
        "quantity": 5,
        "price_source": "linked",
        "linked_source": "coingecko",
        "linked_id": "tether-gold",
    }
    create = await client.post(BASE, json=payload, headers=headers)
    assert create.status_code == 201
    resp = await client.get(BASE, headers=headers)
    pos = resp.json()["positions"][0]
    # Mock simple/price bos doner -> 0 -> unknown
    assert float(pos["unit_price_tl"]) == 0.0
    assert "TGOLD" in resp.json()["unknown_symbols"]


@pytest.mark.asyncio
async def test_linked_tefas_dispatch(client: AsyncClient):
    """linked=tefas:CODE — TEFAS mock'lanmadigi icin fiyat 0 (dispatch dali calisir)."""
    headers = await make_user(client, "mc_linked_tefas@example.com")
    payload = {
        "exchange": "other",
        "symbol": "MYFUND",
        "quantity": 100,
        "price_source": "linked",
        "linked_source": "tefas",
        "linked_id": "AFA",
    }
    create = await client.post(BASE, json=payload, headers=headers)
    assert create.status_code == 201
    resp = await client.get(BASE, headers=headers)
    pos = resp.json()["positions"][0]
    assert float(pos["unit_price_tl"]) == 0.0
    assert "MYFUND" in resp.json()["unknown_symbols"]


@pytest.mark.asyncio
async def test_create_validation_quantity_zero_returns_422(client: AsyncClient):
    """quantity=0 -> gt=0 ihlali -> 422."""
    headers = await make_user(client, "mc_qty0@example.com")
    resp = await client.post(
        BASE,
        json={"exchange": "x", "symbol": "BTC", "quantity": 0},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_empty_file_returns_422(client: AsyncClient):
    """Sadece basliklar (max_row < 2) -> 422 bos dosya."""
    headers = await make_user(client, "mc_imp_empty@example.com")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Borsa", "Etiket", "Sembol", "Miktar"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        f"{BASE}/import",
        headers=headers,
        files={"file": ("e.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_corrupt_file_returns_422(client: AsyncClient):
    """Gecerli .xlsx magic ama bozuk zip -> openpyxl fail -> 422."""
    headers = await make_user(client, "mc_imp_corrupt@example.com")
    corrupt = b"PK\x03\x04" + b"\x00" * 80
    resp = await client.post(
        f"{BASE}/import",
        headers=headers,
        files={"file": ("c.xlsx", corrupt, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_all_rows_invalid_returns_422(client: AsyncClient):
    """Tum satirlar hatali (eksik zorunlu alan + negatif qty) -> 422."""
    headers = await make_user(client, "mc_imp_allbad@example.com")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Borsa", "Etiket", "Sembol", "Miktar", "Maliyet", "Kaynak", "ManFiyat", "LS", "LID", "Not"])
    ws.append(["", "", "", "", "", "", "", "", "", ""])  # bos satir -> atlanir (continue)
    ws.append(["binancetr", "", "", 1, "", "auto", "", "", "", ""])  # symbol eksik -> error
    ws.append(["binancetr", "", "BTC", -5, "", "auto", "", "", "", ""])  # negatif qty -> error
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        f"{BASE}/import",
        headers=headers,
        files={"file": ("b.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 422
    assert "islenemedi" in resp.json()["detail"].lower() or "işlenemedi" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_full_columns_with_linked_and_manual(client: AsyncClient):
    """Tum sutunlu import — manual + linked satirlar + gecersiz bir satir errors'a duser."""
    headers = await make_user(client, "mc_imp_full@example.com")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Borsa", "Etiket", "Sembol", "Miktar", "Maliyet", "Kaynak", "ManFiyat", "LS", "LID", "Not"])
    # manual satir
    ws.append(["icrypex", "Etiket1", "XAGX", 10, 5, "manual", 50, "", "", "gumus"])
    # linked commodity satir
    ws.append(["icrypex", None, "XAUT", 1, "", "linked", "", "commodity", "XAU", None])
    # avg_cost negatif -> None (avg_cost <= 0 dali)
    ws.append(["binancetr", "", "ETH", 2, -1, "auto", "", "", "", ""])
    # gecersiz satir (symbol eksik) -> errors listesine, ama digerleri gecerli
    ws.append(["binancetr", "", "", 1, "", "auto", "", "", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        f"{BASE}/import",
        headers=headers,
        files={"file": ("f.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 3
    assert len(body["errors"]) >= 1

    listing = await client.get(BASE, headers=headers)
    by_symbol = {p["symbol"]: p for p in listing.json()["positions"]}
    assert by_symbol["XAGX"]["price_source"] == "manual"
    assert float(by_symbol["XAGX"]["manual_unit_price_tl"]) == 50.0
    assert by_symbol["XAUT"]["linked_source"] == "commodity"
    assert by_symbol["ETH"]["avg_cost_tl"] is None  # negatif -> None


@pytest.mark.asyncio
async def test_list_price_fetch_failure_returns_503(client: AsyncClient, monkeypatch):
    """fetch_combined_prices patlarsa _fetch_prices_safe -> 503 (SEC-007)."""
    headers = await make_user(client, "mc_price_503@example.com")
    await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=headers)

    async def _boom(*_a, **_k):
        raise RuntimeError("binance down")

    monkeypatch.setattr("app.api.v1.manual_crypto.fetch_combined_prices", _boom)
    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 503
    # Internal hata detayi sizmamali
    assert "binance down" not in resp.text


@pytest.mark.asyncio
async def test_list_usd_tl_failure_returns_503(client: AsyncClient, monkeypatch):
    """fetch_usd_to_tl patlarsa -> 503 (ikinci try blogu)."""
    headers = await make_user(client, "mc_usdtl_503@example.com")
    await client.post(BASE, json={"exchange": "binancetr", "symbol": "BTC", "quantity": 1}, headers=headers)

    async def _usd_boom(*_a, **_k):
        raise RuntimeError("tcmb down")

    monkeypatch.setattr("app.api.v1.manual_crypto.fetch_usd_to_tl", _usd_boom)
    resp = await client.get(BASE, headers=headers)
    assert resp.status_code == 503
    assert "tcmb down" not in resp.text
