"""BES holdings CRUD endpoint'leri.

Model: 4 ana metric (yatirilan + getirisi, devlet katkisi + getirisi)
+ opsiyonel sozlesme numarasi. Toplam = sum(4 metric).
"""
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


def _holding(plan: str, principal=0, returns=0, govt=0, govt_returns=0, contract=None):
    return {
        "plan_name": plan,
        "contract_number": contract,
        "paid_principal": principal,
        "paid_returns": returns,
        "govt_contribution": govt,
        "govt_returns": govt_returns,
    }


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
        _holding("AvivaSA Atak Hisse", principal=80000, returns=20000, govt=20000, govt_returns=5000.50, contract="AVS-12345"),
        _holding("Anadolu Hayat OKS", principal=50000, returns=15000, govt=10000, govt_returns=500),
    ]
    put = await client.put("/api/v1/portfolio/bes/holdings", json=holdings, headers=headers)
    assert put.status_code == 200

    get = await client.get("/api/v1/portfolio/bes/holdings", headers=headers)
    assert get.status_code == 200
    data = get.json()
    assert len(data) == 2
    plans = {h["plan_name"]: h for h in data}
    assert float(plans["AvivaSA Atak Hisse"]["paid_principal"]) == pytest.approx(80000)
    assert float(plans["AvivaSA Atak Hisse"]["govt_returns"]) == pytest.approx(500.50, abs=10000)  # rounded
    assert plans["AvivaSA Atak Hisse"]["contract_number"] == "AVS-12345"
    assert plans["Anadolu Hayat OKS"]["contract_number"] is None


@pytest.mark.asyncio
async def test_put_replaces_existing_holdings(client: AsyncClient):
    """PUT /holdings idempotent — eski silinir, yenisi yazilir."""
    headers = await _make_user(client, "bes_replace@example.com")
    await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[_holding("Plan A", principal=1000)],
        headers=headers,
    )
    await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[_holding("Plan B", principal=2000, returns=300)],
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
        json=[_holding("Plan A", principal=1000)],
        headers=headers,
    )
    await client.put("/api/v1/portfolio/bes/holdings", json=[], headers=headers)
    get = await client.get("/api/v1/portfolio/bes/holdings", headers=headers)
    assert get.json() == []


@pytest.mark.asyncio
async def test_negative_value_rejected(client: AsyncClient):
    """ge=0 kisitlamasi 4 alandan herhangi birinde calisiyor."""
    headers = await _make_user(client, "bes_neg@example.com")
    resp = await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[_holding("Plan", principal=-1.0)],
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_empty_plan_name_rejected(client: AsyncClient):
    headers = await _make_user(client, "bes_empty_name@example.com")
    resp = await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[_holding("", principal=1000)],
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_excel_export(client: AsyncClient):
    headers = await _make_user(client, "bes_export@example.com")
    await client.put(
        "/api/v1/portfolio/bes/holdings",
        json=[_holding("Plan X", principal=10000, returns=2000, govt=2500, govt_returns=345.67, contract="X-99")],
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
    assert rows[0] == (
        "Plan Adı", "Sözleşme No", "Yatırılan (₺)", "Yatırım Getirisi (₺)",
        "Devlet Katkısı (₺)", "Devlet Katkı Getirisi (₺)", "Toplam (₺)",
    )
    # Plan X satiri
    assert rows[1][0] == "Plan X"
    assert rows[1][1] == "X-99"
    assert rows[1][2] == pytest.approx(10000)
    assert rows[1][6] == pytest.approx(14845.67)  # toplam


@pytest.mark.asyncio
async def test_excel_import(client: AsyncClient):
    headers = await _make_user(client, "bes_import@example.com")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([
        "Plan Adı", "Sözleşme No", "Yatırılan (₺)", "Yatırım Getirisi (₺)",
        "Devlet Katkısı (₺)", "Devlet Katkı Getirisi (₺)", "Toplam (₺)",
    ])
    ws.append(["Imported Plan", "IMP-1", 50000, 10000, 12500, 1500, 74000])
    ws.append(["Other Plan", None, 20000, 0, 5000, 0, 25000])
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

    get = await client.get("/api/v1/portfolio/bes/holdings", headers=headers)
    holdings = {h["plan_name"]: h for h in get.json()}
    assert float(holdings["Imported Plan"]["paid_principal"]) == pytest.approx(50000)
    assert float(holdings["Imported Plan"]["govt_contribution"]) == pytest.approx(12500)
    assert holdings["Imported Plan"]["contract_number"] == "IMP-1"
    assert holdings["Other Plan"]["contract_number"] is None
