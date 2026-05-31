"""
Portfolio/TEFAS holdings endpoint integration testleri.
Her test kendi kullanıcısını register edip token alır; böylece izolasyon sağlanır.
"""

import io

import pytest
import respx
from httpx import AsyncClient, Response

from app.services.tefas import _EXPORT_URL


async def _register_and_login(client: AsyncClient, email: str, password: str = "test1234") -> str:
    from tests.conftest import verify_user_email

    await client.post("/api/v1/auth/register", json={"email": email, "password": password, "age_confirmed": True})
    await verify_user_email(email)
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


TEFAS_ROWS = [
    {"fonKodu": "YAC", "sonPortfoyDegeri": 100_000_000.0, "sonPayAdedi": 80_000_000.0},
    {"fonKodu": "TTE", "sonPortfoyDegeri": 500_000_000.0, "sonPayAdedi": 200_000_000.0},
]


@pytest.mark.asyncio
async def test_holdings_empty_on_fresh_account(client: AsyncClient):
    token = await _register_and_login(client, "holdings_empty@test.com")
    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_save_and_retrieve_holdings(client: AsyncClient):
    token = await _register_and_login(client, "holdings_save@test.com")
    holdings = [
        {"code": "YAC", "quantity": 150.5, "name": "Yapı Kredi Fon"},
        {"code": "TTE", "quantity": 200.0, "name": "Türkiye Teknoloji Fon"},
    ]
    put = await client.put("/api/v1/portfolio/tefas/holdings", json=holdings, headers=_auth(token))
    assert put.status_code == 200

    get = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token))
    assert get.status_code == 200
    saved = get.json()
    assert len(saved) == 2
    codes = {h["code"] for h in saved}
    assert codes == {"YAC", "TTE"}


@pytest.mark.asyncio
async def test_put_replaces_existing_holdings(client: AsyncClient):
    token = await _register_and_login(client, "holdings_replace@test.com")

    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "YAC", "quantity": 100.0, "name": "Fon A"},
        ],
        headers=_auth(token),
    )

    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "TTE", "quantity": 50.0, "name": "Fon B"},
        ],
        headers=_auth(token),
    )

    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token))
    saved = resp.json()
    assert len(saved) == 1
    assert saved[0]["code"] == "TTE"


@pytest.mark.asyncio
async def test_put_empty_list_clears_holdings(client: AsyncClient):
    token = await _register_and_login(client, "holdings_clear@test.com")

    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "YAC", "quantity": 100.0, "name": "Fon A"},
        ],
        headers=_auth(token),
    )

    await client.put("/api/v1/portfolio/tefas/holdings", json=[], headers=_auth(token))

    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token))
    assert resp.json() == []


@pytest.mark.asyncio
async def test_holdings_isolated_between_users(client: AsyncClient):
    token_a = await _register_and_login(client, "user_a@test.com")
    token_b = await _register_and_login(client, "user_b@test.com")

    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "YAC", "quantity": 999.0, "name": "Sadece A'nın fonu"},
        ],
        headers=_auth(token_a),
    )

    resp_b = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token_b))
    assert resp_b.json() == []


@pytest.mark.asyncio
async def test_export_xlsx_returns_file(client: AsyncClient):
    token = await _register_and_login(client, "holdings_export@test.com")

    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "YAC", "quantity": 100.0, "name": "Yapı Kredi Fon"},
        ],
        headers=_auth(token),
    )

    with respx.mock:
        respx.post(_EXPORT_URL).mock(return_value=Response(200, json=TEFAS_ROWS))
        resp = await client.get("/api/v1/portfolio/tefas/export", headers=_auth(token))

    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers.get("content-type", "")
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_import_xlsx_saves_holdings(client: AsyncClient):
    import openpyxl

    token = await _register_and_login(client, "holdings_import@test.com")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Kod", "Adet", "İsim"])
    ws.append(["YAC", 150.5, "Yapı Kredi Fon"])
    ws.append(["TTE", 200.0, "Türkiye Teknoloji Fon"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = await client.post(
        "/api/v1/portfolio/tefas/import",
        files={
            "file": (
                "holdings.xlsx",
                buf,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200

    get = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token))
    saved = get.json()
    assert len(saved) == 2


@pytest.mark.asyncio
async def test_endpoints_require_auth(client: AsyncClient):
    get = await client.get("/api/v1/portfolio/tefas/holdings")
    assert get.status_code == 401

    put = await client.put("/api/v1/portfolio/tefas/holdings", json=[])
    assert put.status_code == 401

    export = await client.get("/api/v1/portfolio/tefas/export")
    assert export.status_code == 401


# ---------------------------------------------------------------------------
# Portfolio core endpoint testleri (portfolio.py kapsamı)
# ---------------------------------------------------------------------------
from decimal import Decimal

from app.services.aggregator import EXCHANGERATE_API_GBP, EXCHANGERATE_API_USD, TCMB_URL
from app.services.base import AssetData
from tests.conftest import make_user

_USD_TL_RESPONSE = {"rates": {"TRY": 35.0}}
_GBP_USD_RESPONSE = {"rates": {"USD": 1.25}}
_TCMB_EMPTY_XML = b'<?xml version="1.0" encoding="utf-8"?><Tarih_Date></Tarih_Date>'


def _mock_rates(rsx):
    """USD/TL ve GBP/USD kurlarını mock'lar (TCMB boş → exchangerate-api fallback)."""
    rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_EMPTY_XML))
    rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(200, json=_USD_TL_RESPONSE))
    rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(200, json=_GBP_USD_RESPONSE))


def _mock_spot(rsx, binance_json=None):
    """Binance ticker + CoinGecko fallback mock'ları (gerçek ağ çağrısı önler)."""
    rsx.get("https://api.binance.com/api/v3/ticker/price").mock(return_value=Response(200, json=binance_json if binance_json is not None else []))
    rsx.get(url__regex=r"https://api\.coingecko\.com/.*").mock(return_value=Response(200, json={}))


# --- /portfolio/usd-rate ---
@pytest.mark.asyncio
async def test_usd_rate_endpoint(client: AsyncClient):
    headers = await make_user(client, "pf_usdrate@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        resp = await client.get("/api/v1/portfolio/usd-rate", headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["usd_try"]) == pytest.approx(35.0)


@pytest.mark.asyncio
async def test_usd_rate_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/usd-rate")
    assert resp.status_code == 401


# --- GET /portfolio (current) ---
@pytest.mark.asyncio
async def test_get_current_portfolio_404_when_empty(client: AsyncClient):
    headers = await make_user(client, "pf_current_empty@test.com")
    resp = await client.get("/api/v1/portfolio", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_current_portfolio_returns_latest(client: AsyncClient):
    headers = await make_user(client, "pf_current@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        await client.post("/api/v1/portfolio/snapshot", headers=headers)
    resp = await client.get("/api/v1/portfolio", headers=headers)
    assert resp.status_code == 200
    assert "snapshot_date" in resp.json()


# --- /portfolio/history ---
@pytest.mark.asyncio
async def test_history_empty_returns_empty_list(client: AsyncClient):
    headers = await make_user(client, "pf_hist_empty@test.com")
    resp = await client.get("/api/v1/portfolio/history", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_history_returns_snapshots(client: AsyncClient):
    headers = await make_user(client, "pf_hist@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        await client.post("/api/v1/portfolio/snapshot", headers=headers)
    resp = await client.get("/api/v1/portfolio/history?limit=5", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_history_year_filter(client: AsyncClient):
    headers = await make_user(client, "pf_hist_year@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        await client.post("/api/v1/portfolio/snapshot", headers=headers)
    from datetime import date

    this_year = date.today().year
    resp = await client.get(f"/api/v1/portfolio/history?year={this_year}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    # Olmayan yıl boş döner
    resp2 = await client.get("/api/v1/portfolio/history?year=1999", headers=headers)
    assert resp2.json() == []


@pytest.mark.asyncio
async def test_history_years_endpoint(client: AsyncClient):
    headers = await make_user(client, "pf_hist_years@test.com")
    # Boş
    resp = await client.get("/api/v1/portfolio/history/years", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []
    # Snapshot sonrası bu yıl döner
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        await client.post("/api/v1/portfolio/snapshot", headers=headers)
    from datetime import date

    resp2 = await client.get("/api/v1/portfolio/history/years", headers=headers)
    assert date.today().year in resp2.json()


# --- /portfolio/changes ---
@pytest.mark.asyncio
async def test_changes_404_when_empty(client: AsyncClient):
    headers = await make_user(client, "pf_changes_empty@test.com")
    resp = await client.get("/api/v1/portfolio/changes", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_changes_returns_data(client: AsyncClient):
    headers = await make_user(client, "pf_changes@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        await client.post("/api/v1/portfolio/snapshot", headers=headers)
    resp = await client.get("/api/v1/portfolio/changes", headers=headers)
    assert resp.status_code == 200
    assert "current_value_tl" in resp.json()


# --- /portfolio/breakdown ---
@pytest.mark.asyncio
async def test_breakdown_404_when_empty(client: AsyncClient):
    headers = await make_user(client, "pf_brk_empty@test.com")
    resp = await client.get("/api/v1/portfolio/breakdown", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_breakdown_returns_data(client: AsyncClient):
    headers = await make_user(client, "pf_brk@test.com")
    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[{"code": "YAC", "quantity": 100.0, "name": "Fon"}],
        headers=headers,
    )
    tefas_rows = [{"fonKodu": "YAC", "sonPortfoyDegeri": 100_000_000.0, "sonPayAdedi": 80_000_000.0}]
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        rsx.post(_EXPORT_URL).mock(return_value=Response(200, json=tefas_rows))
        await client.post("/api/v1/portfolio/snapshot", headers=headers)
    resp = await client.get("/api/v1/portfolio/breakdown", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "fund_pct" in data
    assert float(data["fund_pct"]) > 0


# --- /portfolio/staking ---
@pytest.mark.asyncio
async def test_staking_404_when_empty(client: AsyncClient):
    headers = await make_user(client, "pf_stk_empty@test.com")
    resp = await client.get("/api/v1/portfolio/staking", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_staking_returns_list(client: AsyncClient):
    headers = await make_user(client, "pf_stk@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        await client.post("/api/v1/portfolio/snapshot", headers=headers)
    resp = await client.get("/api/v1/portfolio/staking", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []  # staking pozisyonu yok


# --- /portfolio/crypto ---
@pytest.mark.asyncio
async def test_crypto_empty_no_integrations(client: AsyncClient):
    headers = await make_user(client, "pf_crypto_empty@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        resp = await client.get("/api/v1/portfolio/crypto", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["positions"] == []
    assert data["errors"] == {}


@pytest.mark.asyncio
async def test_crypto_with_integration(client: AsyncClient, monkeypatch):
    """Binance entegrasyonu varken crypto pozisyonu döner (servis mock'lu)."""
    headers = await make_user(client, "pf_crypto@test.com")
    # Integration ekle
    await client.post(
        "/api/v1/integrations",
        json={"provider": "binance", "api_key": "k", "api_secret": "s"},
        headers=headers,
    )

    class FakeBinance:
        def __init__(self, *a, **k):
            pass

        async def fetch(self):
            return [
                AssetData(
                    symbol="ETH",
                    name="Ethereum",
                    provider="binance",
                    asset_type="crypto",
                    source_type="exchange",
                    liquid_quantity=Decimal("2"),
                    staked_quantity=Decimal("1"),
                    unit_price_usd=Decimal("2000"),
                )
            ]

    monkeypatch.setattr("app.api.v1.portfolio.BinanceService", FakeBinance)

    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        resp = await client.get("/api/v1/portfolio/crypto", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["positions"]) == 1
    pos = data["positions"][0]
    assert pos["symbol"] == "ETH"
    # (2+1) * 2000 * 35 = 210000
    assert float(pos["total_value_tl"]) == pytest.approx(210000.0, rel=1e-3)


@pytest.mark.asyncio
async def test_crypto_service_error_captured(client: AsyncClient, monkeypatch):
    """Servis exception fırlatırsa errors dict'e yazılır, 200 döner."""
    headers = await make_user(client, "pf_crypto_err@test.com")
    await client.post(
        "/api/v1/integrations",
        json={"provider": "binance", "api_key": "k", "api_secret": "s"},
        headers=headers,
    )

    class FailingBinance:
        def __init__(self, *a, **k):
            pass

        async def fetch(self):
            raise RuntimeError("API anahtarı geçersiz")

    monkeypatch.setattr("app.api.v1.portfolio.BinanceService", FailingBinance)

    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        resp = await client.get("/api/v1/portfolio/crypto", headers=headers)
    assert resp.status_code == 200
    assert "binance" in resp.json()["errors"]


# --- /portfolio/wallets ---
@pytest.mark.asyncio
async def test_wallet_positions_empty(client: AsyncClient):
    headers = await make_user(client, "pf_wallets_empty@test.com")
    resp = await client.get("/api/v1/portfolio/wallets", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["positions"] == []


@pytest.mark.asyncio
async def test_wallet_positions_with_balance(client: AsyncClient, monkeypatch):
    """Ethereum cüzdanı için liquid+staked+pending toplamı doğru hesaplanır."""
    headers = await make_user(client, "pf_wallets@test.com")
    await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0xABCD000000000000000000000000000000000001", "label": "Ana"},
        headers=headers,
    )

    class FakeEth:
        def __init__(self, *a, **k):
            pass

        async def fetch(self):
            return [
                AssetData(
                    symbol="ETH",
                    name="Ethereum",
                    provider="ethereum",
                    asset_type="crypto",
                    source_type="blockchain",
                    liquid_quantity=Decimal("1"),
                    staked_quantity=Decimal("2"),
                    pending_rewards=Decimal("0.5"),
                )
            ]

    monkeypatch.setattr("app.api.v1.portfolio.EthereumService", FakeEth)

    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        # ETH spot fiyatı için Binance ticker mock + CoinGecko fallback boş
        _mock_spot(rsx, [{"symbol": "ETHUSDT", "price": "2000"}])
        resp = await client.get("/api/v1/portfolio/wallets", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["positions"]) == 1
    pos = data["positions"][0]
    # (1 + 2 + 0.5) * 2000 * 35 = 245000
    assert float(pos["total_value_tl"]) == pytest.approx(245000.0, rel=1e-3)
    assert float(pos["pending_rewards"]) == 0.5
    # Adres maskeli dönmeli (field_serializer)
    assert "..." in pos["address"]


@pytest.mark.asyncio
async def test_wallet_positions_service_error_captured(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "pf_wallets_err@test.com")
    await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0xABCD000000000000000000000000000000000099"},
        headers=headers,
    )

    class FailingEth:
        def __init__(self, *a, **k):
            pass

        async def fetch(self):
            raise RuntimeError("RPC timeout")

    monkeypatch.setattr("app.api.v1.portfolio.EthereumService", FailingEth)

    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        _mock_spot(rsx, [])
        resp = await client.get("/api/v1/portfolio/wallets", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["errors"]) == 1


# --- snapshot preview ---
@pytest.mark.asyncio
async def test_snapshot_preview_returns_health(client: AsyncClient):
    headers = await make_user(client, "pf_preview@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        resp = await client.post("/api/v1/portfolio/snapshot/preview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] is False
    assert "issues" in data
    assert data["total_value_tl"] in ("0", "0.00", "0.0")


@pytest.mark.asyncio
async def test_snapshot_preview_503_on_rate_failure(client: AsyncClient):
    headers = await make_user(client, "pf_preview_fail@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        rsx.get(TCMB_URL).mock(return_value=Response(503))
        rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(500))
        rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(200, json=_GBP_USD_RESPONSE))
        resp = await client.post("/api/v1/portfolio/snapshot/preview", headers=headers)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_snapshot_preview_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/portfolio/snapshot/preview")
    assert resp.status_code == 401


# --- snapshot delete (IDOR) ---
@pytest.mark.asyncio
async def test_delete_snapshot_404_when_missing(client: AsyncClient):
    headers = await make_user(client, "pf_delsnap_404@test.com")
    resp = await client.delete("/api/v1/portfolio/snapshot/2020-01-01", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_snapshot_success(client: AsyncClient):
    headers = await make_user(client, "pf_delsnap@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        snap = await client.post("/api/v1/portfolio/snapshot", headers=headers)
    snap_date = snap.json()["snapshot_date"]
    resp = await client.delete(f"/api/v1/portfolio/snapshot/{snap_date}", headers=headers)
    assert resp.status_code == 204
    # Artık portföy boş
    get = await client.get("/api/v1/portfolio", headers=headers)
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_delete_snapshot_idor(client: AsyncClient):
    """Başka kullanıcının snapshot tarihini silmeye çalışmak 404 döner."""
    h1 = await make_user(client, "pf_snap_idor1@test.com")
    h2 = await make_user(client, "pf_snap_idor2@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        snap = await client.post("/api/v1/portfolio/snapshot", headers=h1)
    snap_date = snap.json()["snapshot_date"]
    # h2, h1'in snapshot'ını silemez
    resp = await client.delete(f"/api/v1/portfolio/snapshot/{snap_date}", headers=h2)
    assert resp.status_code == 404
    # h1'in snapshot'ı hala mevcut
    get = await client.get("/api/v1/portfolio", headers=h1)
    assert get.status_code == 200


@pytest.mark.asyncio
async def test_delete_snapshot_invalid_date_422(client: AsyncClient):
    headers = await make_user(client, "pf_delsnap_bad@test.com")
    resp = await client.delete("/api/v1/portfolio/snapshot/not-a-date", headers=headers)
    assert resp.status_code == 422


# --- snapshot report indirme (xlsx + pdf) ---
@pytest.mark.asyncio
async def test_snapshot_report_xlsx(client: AsyncClient):
    headers = await make_user(client, "pf_report_xlsx@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        snap = await client.post("/api/v1/portfolio/snapshot", headers=headers)
    snap_date = snap.json()["snapshot_date"]
    resp = await client.get(f"/api/v1/portfolio/snapshot/{snap_date}/report.xlsx", headers=headers)
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_snapshot_report_pdf(client: AsyncClient):
    headers = await make_user(client, "pf_report_pdf@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        snap = await client.post("/api/v1/portfolio/snapshot", headers=headers)
    snap_date = snap.json()["snapshot_date"]
    resp = await client.get(f"/api/v1/portfolio/snapshot/{snap_date}/report.pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_snapshot_report_xlsx_404_missing(client: AsyncClient):
    headers = await make_user(client, "pf_report_404@test.com")
    resp = await client.get("/api/v1/portfolio/snapshot/2020-01-01/report.xlsx", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_snapshot_report_idor(client: AsyncClient):
    """Başka kullanıcının snapshot raporu indirilemez (user_id filtresi → 404)."""
    h1 = await make_user(client, "pf_report_idor1@test.com")
    h2 = await make_user(client, "pf_report_idor2@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        snap = await client.post("/api/v1/portfolio/snapshot", headers=h1)
    snap_date = snap.json()["snapshot_date"]
    resp = await client.get(f"/api/v1/portfolio/snapshot/{snap_date}/report.pdf", headers=h2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_snapshot_force_create(client: AsyncClient):
    """force=true ile snapshot oluşturma (kullanıcı uyarıları onayladıktan sonra)."""
    headers = await make_user(client, "pf_force@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        resp = await client.post("/api/v1/portfolio/snapshot?force=true", headers=headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_crypto_icrypex_provider(client: AsyncClient, monkeypatch):
    """iCrypex provider dalı (else → ICrypexService) kapsanır."""
    headers = await make_user(client, "pf_crypto_icx@test.com")
    await client.post(
        "/api/v1/integrations",
        json={"provider": "icrypex", "api_key": "k", "api_secret": "s"},
        headers=headers,
    )

    class FakeIcx:
        def __init__(self, *a, **k):
            pass

        async def fetch(self):
            return [
                AssetData(
                    symbol="USDT",
                    name="Tether",
                    provider="icrypex",
                    asset_type="crypto",
                    source_type="exchange",
                    liquid_quantity=Decimal("100"),
                    unit_price_usd=Decimal("1"),
                )
            ]

    monkeypatch.setattr("app.api.v1.portfolio.ICrypexService", FakeIcx)
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        resp = await client.get("/api/v1/portfolio/crypto", headers=headers)
    assert resp.status_code == 200
    positions = resp.json()["positions"]
    assert len(positions) == 1
    assert positions[0]["symbol"] == "USDT"


@pytest.mark.asyncio
async def test_wallet_positions_bitcoin_chain(client: AsyncClient, monkeypatch):
    """bitcoin chain dispatch dalı (BitcoinService) kapsanır + BTC fiyatlama."""
    headers = await make_user(client, "pf_wallet_btc@test.com")
    await client.post(
        "/api/v1/wallets",
        json={"chain": "bitcoin", "address": "bc1qbtcaddressxxxxxxxxxxxxxxxxxxxxxxxx0001"},
        headers=headers,
    )

    class FakeBtc:
        def __init__(self, *a, **k):
            pass

        async def fetch(self):
            return [
                AssetData(
                    symbol="BTC",
                    name="Bitcoin",
                    provider="bitcoin",
                    asset_type="crypto",
                    source_type="blockchain",
                    liquid_quantity=Decimal("0.5"),
                )
            ]

    monkeypatch.setattr("app.api.v1.portfolio.BitcoinService", FakeBtc)
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        _mock_spot(rsx, [{"symbol": "BTCUSDT", "price": "60000"}])
        resp = await client.get("/api/v1/portfolio/wallets", headers=headers)
    assert resp.status_code == 200
    positions = resp.json()["positions"]
    assert len(positions) == 1
    # 0.5 * 60000 * 35 = 1,050,000
    assert float(positions[0]["total_value_tl"]) == pytest.approx(1_050_000.0, rel=1e-3)


@pytest.mark.asyncio
async def test_snapshot_create_503_on_rate_failure(client: AsyncClient):
    """create_snapshot (force) USD/TL fail → 503 (RuntimeError except branch)."""
    headers = await make_user(client, "pf_snap_503@test.com")
    with respx.mock(assert_all_called=False) as rsx:
        rsx.get(TCMB_URL).mock(return_value=Response(503))
        rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(500))
        rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(200, json=_GBP_USD_RESPONSE))
        resp = await client.post("/api/v1/portfolio/snapshot?force=true", headers=headers)
    assert resp.status_code == 503
