"""
Portfolio/TEFAS holdings endpoint integration testleri.
Her test kendi kullanıcısını register edip token alır; böylece izolasyon sağlanır.
"""
import io
import pytest
import respx
from decimal import Decimal
from httpx import AsyncClient, Response
from app.services.tefas import _EXPORT_URL


async def _register_and_login(client: AsyncClient, email: str, password: str = "test1234") -> str:
    from tests.conftest import verify_user_email
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
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

    await client.put("/api/v1/portfolio/tefas/holdings", json=[
        {"code": "YAC", "quantity": 100.0, "name": "Fon A"},
    ], headers=_auth(token))

    await client.put("/api/v1/portfolio/tefas/holdings", json=[
        {"code": "TTE", "quantity": 50.0, "name": "Fon B"},
    ], headers=_auth(token))

    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token))
    saved = resp.json()
    assert len(saved) == 1
    assert saved[0]["code"] == "TTE"


@pytest.mark.asyncio
async def test_put_empty_list_clears_holdings(client: AsyncClient):
    token = await _register_and_login(client, "holdings_clear@test.com")

    await client.put("/api/v1/portfolio/tefas/holdings", json=[
        {"code": "YAC", "quantity": 100.0, "name": "Fon A"},
    ], headers=_auth(token))

    await client.put("/api/v1/portfolio/tefas/holdings", json=[], headers=_auth(token))

    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token))
    assert resp.json() == []


@pytest.mark.asyncio
async def test_holdings_isolated_between_users(client: AsyncClient):
    token_a = await _register_and_login(client, "user_a@test.com")
    token_b = await _register_and_login(client, "user_b@test.com")

    await client.put("/api/v1/portfolio/tefas/holdings", json=[
        {"code": "YAC", "quantity": 999.0, "name": "Sadece A'nın fonu"},
    ], headers=_auth(token_a))

    resp_b = await client.get("/api/v1/portfolio/tefas/holdings", headers=_auth(token_b))
    assert resp_b.json() == []


@pytest.mark.asyncio
async def test_export_xlsx_returns_file(client: AsyncClient):
    token = await _register_and_login(client, "holdings_export@test.com")

    await client.put("/api/v1/portfolio/tefas/holdings", json=[
        {"code": "YAC", "quantity": 100.0, "name": "Yapı Kredi Fon"},
    ], headers=_auth(token))

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
        files={"file": ("holdings.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
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
