"""Snapshot servisi ve manuel /portfolio/snapshot endpoint'i icin integration testler.

Dis HTTP cagrilari (TEFAS, exchange rate API'leri) respx ile mock'lanir;
test gercek dis servislere gitmez.
"""
import pytest
import respx
from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models.portfolio import PortfolioSnapshot
from app.services.tefas import _EXPORT_URL
from tests.conftest import TestSession, verify_user_email


_USD_TL_URL = "https://api.exchangerate-api.com/v4/latest/USD"
_GBP_USD_URL = "https://api.exchangerate-api.com/v4/latest/GBP"
_USD_TL_RESPONSE = {"rates": {"TRY": 35.0}}
_GBP_USD_RESPONSE = {"rates": {"USD": 1.25}}


async def _register_login(client: AsyncClient, email: str) -> dict:
    pwd = "guclu-sifre-123"
    await client.post("/api/v1/auth/register", json={"email": email, "password": pwd})
    await verify_user_email(email)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_snapshot_empty_user_returns_zero_total(client: AsyncClient):
    headers = await _register_login(client, "snap_empty@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        rsx.get(_USD_TL_URL).mock(return_value=Response(200, json=_USD_TL_RESPONSE))
        rsx.get(_GBP_USD_URL).mock(return_value=Response(200, json=_GBP_USD_RESPONSE))

        resp = await client.post("/api/v1/portfolio/snapshot", headers=headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["total_value_tl"] in ("0", "0.00", "0.0")
    assert data["asset_positions"] == []


@pytest.mark.asyncio
async def test_snapshot_with_tefas_holdings(client: AsyncClient):
    headers = await _register_login(client, "snap_tefas@example.com")

    # Once TEFAS holding ekle
    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[{"code": "YAC", "quantity": 100.0, "name": "Yapi Kredi Fon"}],
        headers=headers,
    )

    tefas_rows = [
        {"fonKodu": "YAC", "sonPortfoyDegeri": 100_000_000.0, "sonPayAdedi": 80_000_000.0},
    ]
    with respx.mock(assert_all_called=False) as rsx:
        rsx.get(_USD_TL_URL).mock(return_value=Response(200, json=_USD_TL_RESPONSE))
        rsx.get(_GBP_USD_URL).mock(return_value=Response(200, json=_GBP_USD_RESPONSE))
        rsx.post(_EXPORT_URL).mock(return_value=Response(200, json=tefas_rows))

        resp = await client.post("/api/v1/portfolio/snapshot", headers=headers)

    assert resp.status_code == 201
    data = resp.json()
    # 100 birim x 1.25 (100M / 80M) = 125 TL
    assert float(data["total_value_tl"]) == pytest.approx(125.0, rel=1e-3)
    assert len(data["asset_positions"]) == 1
    pos = data["asset_positions"][0]
    assert pos["symbol"] == "YAC"
    assert pos["asset_type"] == "fund"
    assert pos["provider"] == "tefas"


@pytest.mark.asyncio
async def test_snapshot_persists_in_db(client: AsyncClient):
    """Manuel snapshot DB'ye yazilmali; /portfolio GET cagrisi onu donmeli."""
    headers = await _register_login(client, "snap_persist@example.com")

    with respx.mock(assert_all_called=False) as rsx:
        rsx.get(_USD_TL_URL).mock(return_value=Response(200, json=_USD_TL_RESPONSE))
        rsx.get(_GBP_USD_URL).mock(return_value=Response(200, json=_GBP_USD_RESPONSE))

        await client.post("/api/v1/portfolio/snapshot", headers=headers)

    # /portfolio GET endpoint'i son snapshot'i donmeli
    resp = await client.get("/api/v1/portfolio", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_value_tl"] in ("0", "0.00", "0.0")


@pytest.mark.asyncio
async def test_snapshot_idempotent_same_day(client: AsyncClient):
    """Ayni gunde iki kez cagrilirsa eski snapshot silinip yenisi yazilmali."""
    headers = await _register_login(client, "snap_idem@example.com")

    with respx.mock(assert_all_called=False) as rsx:
        rsx.get(_USD_TL_URL).mock(return_value=Response(200, json=_USD_TL_RESPONSE))
        rsx.get(_GBP_USD_URL).mock(return_value=Response(200, json=_GBP_USD_RESPONSE))

        first = await client.post("/api/v1/portfolio/snapshot", headers=headers)
        second = await client.post("/api/v1/portfolio/snapshot", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    # ID degismeli (yeni snapshot olusturuldu)
    assert first.json()["id"] != second.json()["id"]

    # DB'de tek snapshot olmali (eskisinin silindigini dogrula)
    user_email = "snap_idem@example.com"
    async with TestSession() as session:
        from app.models.user import User
        user_q = await session.execute(select(User).where(User.email == user_email))
        user = user_q.scalar_one()
        snaps_q = await session.execute(
            select(PortfolioSnapshot).where(PortfolioSnapshot.user_id == user.id)
        )
        snapshots = snaps_q.scalars().all()
    assert len(snapshots) == 1


@pytest.mark.asyncio
async def test_snapshot_unauthorized_returns_401(client: AsyncClient):
    resp = await client.post("/api/v1/portfolio/snapshot")
    assert resp.status_code == 401
