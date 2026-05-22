"""Maliyet bazı (avg_cost_tl) ve kâr/zarar hesaplama testleri.

Stocks preview: Yahoo Finance + TCMB + exchangerate-api HTTP çağrıları respx ile mock'lanır.
TEFAS preview: TEFAS export API mock'lanır.

Mock değerleri:
  THYAO.IS  → price=750.0 TRY
  AAPL      → price=200.0 USD,  USD/TRY=40.0  → 8000.0 TRY/adet
  USD/TRY   → 40.0  (TCMB)
  GBP/TRY   → 52.0  (TCMB) → GBP/USD = 52/40 = 1.3
  YAC       → birim_fiyat = 10_000_000 / 1_000_000 = 10.0 TRY
"""

import pytest
import respx
from httpx import AsyncClient, Response

from tests.conftest import make_user

# ---------------------------------------------------------------------------
# TCMB XML: USD/TRY=40, GBP/TRY=52
# ---------------------------------------------------------------------------
_TCMB_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date>
  <Currency CurrencyCode="USD">
    <Unit>1</Unit>
    <ForexBuying>40.000000</ForexBuying>
    <ForexSelling>40.200000</ForexSelling>
  </Currency>
  <Currency CurrencyCode="GBP">
    <Unit>1</Unit>
    <ForexBuying>52.000000</ForexBuying>
    <ForexSelling>52.400000</ForexSelling>
  </Currency>
</Tarih_Date>
"""

# Yahoo Finance yanıtları
_THYAO_RESP = {
    "chart": {
        "result": [
            {
                "meta": {
                    "regularMarketPrice": 750.0,
                    "currency": "TRY",
                    "longName": "Turk Hava Yollari",
                }
            }
        ],
        "error": None,
    }
}
_AAPL_RESP = {
    "chart": {
        "result": [{"meta": {"regularMarketPrice": 200.0, "currency": "USD", "longName": "Apple Inc."}}],
        "error": None,
    }
}

# TEFAS export yanıtı: YAC fonu — portfoy=10_000_000, pay=1_000_000 → birim=10.0 TRY
_TEFAS_RESP = [
    {
        "fonKodu": "YAC",
        "fonUnvan": "Yapı Kredi Portföy A.Ş.",
        "sonPortfoyDegeri": 10_000_000,
        "sonPayAdedi": 1_000_000,
    }
]

# ---------------------------------------------------------------------------
# Fixtures: HTTP mock'ları her test için aktif
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_http():
    """Tüm dış HTTP çağrılarını mock'lar.

    TCMB cache'i sıfırlanır, böylece testler arası kirlenme olmaz.
    """
    import app.services.aggregator as agg

    agg._tcmb_cache = None  # TCMB cache sıfırla

    with respx.mock(assert_all_called=False) as mock:
        # TCMB
        mock.get("https://www.tcmb.gov.tr/kurlar/today.xml").mock(return_value=Response(200, content=_TCMB_XML))
        # Yahoo Finance — THYAO.IS
        mock.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/THYAO\.IS.*").mock(return_value=Response(200, json=_THYAO_RESP))
        # Yahoo Finance — AAPL
        mock.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/AAPL.*").mock(return_value=Response(200, json=_AAPL_RESP))
        # TEFAS export API
        mock.post("https://www.tefas.gov.tr/api/fund-returns/export").mock(return_value=Response(200, json=_TEFAS_RESP))
        yield mock


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
_PWD = "Guclu-Sifre-2026!"
_STOCKS_BASE = "/api/v1/portfolio/stocks"
_TEFAS_BASE = "/api/v1/portfolio/tefas"


# ---------------------------------------------------------------------------
# Test 1: Hisse holding kaydederken avg_cost_tl içerir, GET'te geri döner
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stock_put_and_get_avg_cost(client: AsyncClient):
    headers = await make_user(client, "cb_stock_put@example.com")
    payload = [{"ticker": "THYAO.IS", "quantity": 10.0, "name": "THY", "avg_cost_tl": 700.0}]
    resp = await client.put(f"{_STOCKS_BASE}/holdings", json=payload, headers=headers)
    assert resp.status_code == 200

    get_resp = await client.get(f"{_STOCKS_BASE}/holdings", headers=headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert len(data) == 1
    assert float(data[0]["avg_cost_tl"]) == pytest.approx(700.0)


# ---------------------------------------------------------------------------
# Test 2: Preview — avg_cost_tl yoksa gain_loss_tl None döner
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stock_preview_no_cost_returns_none(client: AsyncClient):
    headers = await make_user(client, "cb_stock_no_cost@example.com")
    payload = [{"ticker": "THYAO.IS", "quantity": 10.0, "name": "THY"}]
    resp = await client.post(f"{_STOCKS_BASE}/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["gain_loss_tl"] is None
    assert item["cost_basis_tl"] is None
    assert item["gain_loss_pct"] is None


# ---------------------------------------------------------------------------
# Test 3: Preview — avg_cost_tl varsa gain_loss_tl pozitif (kâr) doğru hesaplanır
#   THYAO.IS: price=750 TRY, qty=10, avg_cost=700
#   cost_basis = 7000, total = 7500, gain_loss = +500
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stock_preview_gain_positive(client: AsyncClient):
    headers = await make_user(client, "cb_stock_gain@example.com")
    payload = [{"ticker": "THYAO.IS", "quantity": 10.0, "name": "THY", "avg_cost_tl": 700.0}]
    resp = await client.post(f"{_STOCKS_BASE}/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    item = resp.json()[0]
    assert float(item["total_value_tl"]) == pytest.approx(7500.0, rel=1e-3)
    assert float(item["cost_basis_tl"]) == pytest.approx(7000.0, rel=1e-3)
    assert float(item["gain_loss_tl"]) == pytest.approx(500.0, rel=1e-3)
    assert float(item["gain_loss_pct"]) == pytest.approx(500.0 / 7000.0 * 100, rel=1e-3)


# ---------------------------------------------------------------------------
# Test 4: Preview — avg_cost_tl varsa gain_loss_tl negatif (zarar) doğru hesaplanır
#   THYAO.IS: price=750 TRY, qty=10, avg_cost=800
#   cost_basis = 8000, total = 7500, gain_loss = -500
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stock_preview_gain_negative(client: AsyncClient):
    headers = await make_user(client, "cb_stock_loss@example.com")
    payload = [{"ticker": "THYAO.IS", "quantity": 10.0, "name": "THY", "avg_cost_tl": 800.0}]
    resp = await client.post(f"{_STOCKS_BASE}/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    item = resp.json()[0]
    assert float(item["gain_loss_tl"]) == pytest.approx(-500.0, rel=1e-3)
    assert float(item["gain_loss_pct"]) == pytest.approx(-500.0 / 8000.0 * 100, rel=1e-3)


# ---------------------------------------------------------------------------
# Test 5: Preview — gain_loss_pct doğru % hesaplanır (USD hisse)
#   AAPL: price=200 USD → 200*40=8000 TRY, qty=5, avg_cost=7000
#   total=40000, cost=35000, gain_loss=+5000, pct≈14.286%
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stock_preview_gain_loss_pct_usd(client: AsyncClient):
    headers = await make_user(client, "cb_stock_pct@example.com")
    payload = [{"ticker": "AAPL", "quantity": 5.0, "name": "Apple", "avg_cost_tl": 7000.0}]
    resp = await client.post(f"{_STOCKS_BASE}/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    item = resp.json()[0]
    total = float(item["total_value_tl"])
    cost = float(item["cost_basis_tl"])
    gain = float(item["gain_loss_tl"])
    pct = float(item["gain_loss_pct"])
    assert cost == pytest.approx(35000.0, rel=1e-3)
    assert gain == pytest.approx(total - cost, rel=1e-3)
    assert pct == pytest.approx(gain / cost * 100, rel=1e-3)


# ---------------------------------------------------------------------------
# Test 6: TEFAS holding kaydederken avg_cost_tl içerir, GET'te geri döner
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tefas_put_and_get_avg_cost(client: AsyncClient):
    headers = await make_user(client, "cb_tefas_put@example.com")
    payload = [{"code": "YAC", "quantity": 100.0, "name": "Yapı Kredi", "avg_cost_tl": 9.5}]
    resp = await client.put(f"{_TEFAS_BASE}/holdings", json=payload, headers=headers)
    assert resp.status_code == 200

    get_resp = await client.get(f"{_TEFAS_BASE}/holdings", headers=headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert len(data) == 1
    assert float(data[0]["avg_cost_tl"]) == pytest.approx(9.5)


# ---------------------------------------------------------------------------
# Test 7: TEFAS preview — avg_cost_tl yoksa None döner
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tefas_preview_no_cost_returns_none(client: AsyncClient):
    headers = await make_user(client, "cb_tefas_no_cost@example.com")
    payload = [{"code": "YAC", "quantity": 100.0, "name": "Yapı Kredi"}]
    resp = await client.post(f"{_TEFAS_BASE}/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["gain_loss_tl"] is None
    assert item["cost_basis_tl"] is None
    assert item["gain_loss_pct"] is None


# ---------------------------------------------------------------------------
# Test 8: TEFAS preview — kâr/zarar doğru hesaplanır
#   YAC: birim=10.0 TRY, qty=100, avg_cost=9.0
#   cost_basis=900, total=1000, gain_loss=+100, pct≈11.11%
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tefas_preview_gain_positive(client: AsyncClient):
    headers = await make_user(client, "cb_tefas_gain@example.com")
    payload = [{"code": "YAC", "quantity": 100.0, "name": "Yapı Kredi", "avg_cost_tl": 9.0}]
    resp = await client.post(f"{_TEFAS_BASE}/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    item = resp.json()[0]
    assert float(item["total_value_tl"]) == pytest.approx(1000.0, rel=1e-3)
    assert float(item["cost_basis_tl"]) == pytest.approx(900.0, rel=1e-3)
    assert float(item["gain_loss_tl"]) == pytest.approx(100.0, rel=1e-3)
    assert float(item["gain_loss_pct"]) == pytest.approx(100.0 / 900.0 * 100, rel=1e-3)


# ---------------------------------------------------------------------------
# Test 9: TEFAS preview — zarar senaryosu
#   YAC: birim=10.0 TRY, qty=100, avg_cost=11.0
#   cost_basis=1100, total=1000, gain_loss=-100
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tefas_preview_gain_negative(client: AsyncClient):
    headers = await make_user(client, "cb_tefas_loss@example.com")
    payload = [{"code": "YAC", "quantity": 100.0, "name": "Yapı Kredi", "avg_cost_tl": 11.0}]
    resp = await client.post(f"{_TEFAS_BASE}/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    item = resp.json()[0]
    assert float(item["gain_loss_tl"]) == pytest.approx(-100.0, rel=1e-3)
    assert float(item["gain_loss_pct"]) == pytest.approx(-100.0 / 1100.0 * 100, rel=1e-3)


# ---------------------------------------------------------------------------
# Test 10: avg_cost_tl=0 schema tarafindan None'a normalize edilir
# (CLAUDE.md "Maliyet bazi" bolumu — kullanici bilmiyorsa bos birakabilir)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stock_avg_cost_zero_normalizes_to_none(client: AsyncClient):
    headers = await make_user(client, "cb_stock_zero@example.com")
    payload = [{"ticker": "THYAO.IS", "quantity": 10.0, "avg_cost_tl": 0.0}]
    resp = await client.put(f"{_STOCKS_BASE}/holdings", json=payload, headers=headers)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body[0]["avg_cost_tl"] is None


# ---------------------------------------------------------------------------
# Test 11: Negatif avg_cost_tl schema tarafindan None'a normalize edilir
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stock_avg_cost_negative_normalizes_to_none(client: AsyncClient):
    headers = await make_user(client, "cb_stock_neg@example.com")
    payload = [{"ticker": "THYAO.IS", "quantity": 10.0, "avg_cost_tl": -100.0}]
    resp = await client.put(f"{_STOCKS_BASE}/holdings", json=payload, headers=headers)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body[0]["avg_cost_tl"] is None


# ---------------------------------------------------------------------------
# Test 12: TEFAS negatif avg_cost_tl schema tarafindan None'a normalize edilir
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tefas_avg_cost_negative_normalizes_to_none(client: AsyncClient):
    headers = await make_user(client, "cb_tefas_neg@example.com")
    payload = [{"code": "YAC", "quantity": 100.0, "avg_cost_tl": -5.0}]
    resp = await client.put(f"{_TEFAS_BASE}/holdings", json=payload, headers=headers)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body[0]["avg_cost_tl"] is None


# ---------------------------------------------------------------------------
# Test 13: IDOR — başka kullanıcının holdinglerini göremez
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_idor_stock_holdings(client: AsyncClient):
    h1 = await make_user(client, "cb_idor1@example.com")
    h2 = await make_user(client, "cb_idor2@example.com")

    # h1 holding kaydeder
    await client.put(
        f"{_STOCKS_BASE}/holdings",
        json=[{"ticker": "THYAO.IS", "quantity": 10.0, "avg_cost_tl": 700.0}],
        headers=h1,
    )

    # h2 kendi listesini çeker — h1'in verisi görünmemeli
    resp = await client.get(f"{_STOCKS_BASE}/holdings", headers=h2)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Test 14: Yetkisiz erişim 401
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthenticated_stocks(client: AsyncClient):
    resp = await client.get(f"{_STOCKS_BASE}/holdings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_tefas(client: AsyncClient):
    resp = await client.get(f"{_TEFAS_BASE}/holdings")
    assert resp.status_code == 401
