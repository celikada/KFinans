"""BES holdings CRUD endpoint'leri."""
import io

import openpyxl
import pytest
from httpx import AsyncClient

from tests.conftest import verify_user_email


async def _make_user(client: AsyncClient, email: str) -> dict:
    pwd = "guclu-sifre-123"
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_empty_user_returns_no_holdings(client: AsyncClient):
    headers = await _make_user(client, "bes_empty@example.com")
    resp = await client.get("/api/v1/portfolio/bes/holdings", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_save_and_retrieve_bes_holdings(client: AsyncClient):
    headers = await _make_user(client, "bes_save@example.com")
    holdings = [
        {"plan_name": "AvivaSA Atak Hisse", "total_value_tl": 125000.50},
        {"plan_name": "Anadolu Hayat OKS", "total_value_tl": 75500.00},
    ]
    put = await client.put("/api/v1/portfolio/bes/holdings", json=holdings, headers=headers)
    assert put.status_code == 200

    get = await client.get("/api/v1/portfolio/bes/holdings", headers=headers)
    assert get.status_code == 200
    data = get.json()
    assert len(data) == 2
    plans = {h["plan_name"]: float(h["total_value_tl"]) for h in data}
    assert plans["AvivaSA Atak Hisse"] == pytest.approx(125000.50)
    assert plans["Anadolu Hayat OKS"] == pytest.approx(75500.00)


@pytest.mark.asyncio
async def test_put_replaces_existing_holdings(client: AsyncClient):
    """PUT /holdings idempotent — eski silinir, yenisi yazilir."""
    headers = await _make_user(client, "bes_replace@example.com")
    await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[{"plan_name": "Plan A", "total_value_tl": 1000}],
        headers=headers,
    )
    await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[{"plan_name": "Plan B", "total_value_tl": 2000}],
        headers=headers,
    )
    get = await client.get("/api/v1/portfolio/bes/holdings", headers=headers)
    assert len(get.json()) == 1
    assert get.json()[0]["plan_name"] == "Plan B"


@pytest.mark.asyncio
async def test_empty_put_clears_holdings(client: AsyncClient):
    headers = await _make_user(client, "bes_clear@example.com")
    await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[{"plan_name": "Plan A", "total_value_tl": 1000}],
        headers=headers,
    )
    await client.put("/api/v1/portfolio/bes/holdings", json=[], headers=headers)
    get = await client.get("/api/v1/portfolio/bes/holdings", headers=headers)
    assert get.json() == []


@pytest.mark.asyncio
async def test_negative_total_value_rejected(client: AsyncClient):
    """ge=0 kisitlamasi calisiyor."""
    headers = await _make_user(client, "bes_neg@example.com")
    resp = await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[{"plan_name": "Plan", "total_value_tl": -1.0}],
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_empty_plan_name_rejected(client: AsyncClient):
    headers = await _make_user(client, "bes_empty_name@example.com")
    resp = await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[{"plan_name": "", "total_value_tl": 1000}],
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_excel_export(client: AsyncClient):
    headers = await _make_user(client, "bes_export@example.com")
    await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[{"plan_name": "Plan X", "total_value_tl": 12345.67}],
        headers=headers,
    )

    resp = await client.get("/api/v1/portfolio/bes/export", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("Plan Adı", "Toplam Değer (₺)")
    assert rows[1] == ("Plan X", 12345.67)


@pytest.mark.asyncio
async def test_excel_import(client: AsyncClient):
    headers = await _make_user(client, "bes_import@example.com")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Plan Adı", "Toplam Değer (₺)"])
    ws.append(["İmported Plan", 99999.99])
    ws.append(["Diğer Plan", 5000.00])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = await client.post(
        "/api/v1/portfolio/bes/import",
        files={"file": ("test.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    # Idempotent: import mevcut kayitlari degistirir
    get = await client.get("/api/v1/portfolio/bes/holdings", headers=headers)
    assert len(get.json()) == 2
