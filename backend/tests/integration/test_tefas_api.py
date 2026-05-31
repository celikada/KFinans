"""TEST-011 (FAZ H): TEFAS holding endpoint testleri.

PUT replace-all + distributor + avg_cost_tl validation + auth. preview ve
import-mkk endpoint'leri network/file bagimli oldugu icin kapsam disi.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


@pytest.mark.asyncio
async def test_get_holdings_empty(client: AsyncClient):
    headers = await make_user(client, "tefas_empty@example.com")
    resp = await client.get("/api/v1/portfolio/tefas/holdings", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_holdings_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/tefas/holdings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_holdings_replace_all(client: AsyncClient):
    """PUT replace-all: eski kayitlar silinir, yeni kayitlar yazilir."""
    headers = await make_user(client, "tefas_put@example.com")

    first = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "AFA", "quantity": 100, "name": "Ak Portföy"},
            {"code": "ZJI", "quantity": 50, "name": "Ziraat Portföy"},
        ],
        headers=headers,
    )
    assert first.status_code == 200
    assert len(first.json()) == 2

    second = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "FYD", "quantity": 200, "name": "Finans Yatırım"},
        ],
        headers=headers,
    )
    assert second.status_code == 200
    assert len(second.json()) == 1
    assert second.json()[0]["code"] == "FYD"


@pytest.mark.asyncio
async def test_put_holdings_with_avg_cost(client: AsyncClient):
    headers = await make_user(client, "tefas_cost@example.com")
    resp = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "AFA", "quantity": 100, "name": "Ak Portföy", "avg_cost_tl": 1.2345},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    h = resp.json()[0]
    assert float(h["avg_cost_tl"]) == 1.2345


@pytest.mark.asyncio
async def test_put_holdings_avg_cost_zero_normalized_to_none(client: AsyncClient):
    """avg_cost_tl <= 0 -> None (cost basis bilinmiyor)."""
    headers = await make_user(client, "tefas_zerocost@example.com")
    resp = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "AFA", "quantity": 100, "name": "Ak Portföy", "avg_cost_tl": 0},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["avg_cost_tl"] is None


@pytest.mark.asyncio
async def test_put_holdings_with_distributor(client: AsyncClient):
    """ZJI fonu hem Foneria hem Ziraat'tan ayri satir."""
    headers = await make_user(client, "tefas_dist@example.com")
    resp = await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[
            {"code": "ZJI", "quantity": 50, "name": "Ziraat", "distributor": "Foneria"},
            {"code": "ZJI", "quantity": 30, "name": "Ziraat", "distributor": "Ziraat Yatırım"},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 2


@pytest.mark.asyncio
async def test_export_holdings_returns_xlsx(client: AsyncClient):
    headers = await make_user(client, "tefas_export@example.com")
    resp = await client.get("/api/v1/portfolio/tefas/export", headers=headers)
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_holdings_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/tefas/export")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Ek kapsam: preview (TEFAS export mock), import (xlsx + MKK hata yolları),
# export canlı fiyat
# ---------------------------------------------------------------------------
import io

import openpyxl
import respx
from httpx import Response

from app.services.tefas import _EXPORT_URL

_TEFAS_ROWS = [
    {"fonKodu": "AFA", "sonPortfoyDegeri": 100_000_000.0, "sonPayAdedi": 80_000_000.0},
    {"fonKodu": "ZJI", "sonPortfoyDegeri": 200_000_000.0, "sonPayAdedi": 100_000_000.0},
]
_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


@pytest.mark.asyncio
async def test_preview_returns_positions(client: AsyncClient):
    """TEFAS preview: birim fiyat + kâr/zarar hesaplanır."""
    headers = await make_user(client, "tefas_preview@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        rsx.post(_EXPORT_URL).mock(return_value=Response(200, json=_TEFAS_ROWS))
        resp = await client.post(
            "/api/v1/portfolio/tefas/preview",
            json=[{"code": "AFA", "quantity": 100, "name": "Ak Portföy", "avg_cost_tl": 1.0}],
            headers=headers,
        )
    assert resp.status_code == 200
    pos = resp.json()[0]
    # birim fiyat = 100M / 80M = 1.25; 100 adet = 125 TL
    assert float(pos["unit_price_tl"]) == pytest.approx(1.25, rel=1e-3)
    assert float(pos["total_value_tl"]) == pytest.approx(125.0, rel=1e-3)
    # cost_basis = 100 * 1.0 = 100; gain = 25
    assert float(pos["gain_loss_tl"]) == pytest.approx(25.0, rel=1e-3)


@pytest.mark.asyncio
async def test_preview_no_avg_cost(client: AsyncClient):
    headers = await make_user(client, "tefas_preview_nocost@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        rsx.post(_EXPORT_URL).mock(return_value=Response(200, json=_TEFAS_ROWS))
        resp = await client.post(
            "/api/v1/portfolio/tefas/preview",
            json=[{"code": "AFA", "quantity": 100, "name": "Ak"}],
            headers=headers,
        )
    assert resp.status_code == 200
    pos = resp.json()[0]
    assert pos["gain_loss_tl"] is None


@pytest.mark.asyncio
async def test_preview_unknown_fund_422(client: AsyncClient):
    """Bulunmayan fon kodu → TefasService ValueError → 422."""
    headers = await make_user(client, "tefas_preview_404@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        rsx.post(_EXPORT_URL).mock(return_value=Response(200, json=_TEFAS_ROWS))
        resp = await client.post(
            "/api/v1/portfolio/tefas/preview",
            json=[{"code": "ZZZ", "quantity": 10, "name": "Yok"}],
            headers=headers,
        )
    assert resp.status_code == 422
    assert "ZZZ" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_preview_unauth(client: AsyncClient):
    resp = await client.post("/api/v1/portfolio/tefas/preview", json=[])
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_with_live_prices(client: AsyncClient):
    headers = await make_user(client, "tefas_export_live@example.com")
    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[{"code": "AFA", "quantity": 100, "name": "Ak", "avg_cost_tl": 1.0}],
        headers=headers,
    )
    with respx.mock(assert_all_called=False) as rsx:
        rsx.post(_EXPORT_URL).mock(return_value=Response(200, json=_TEFAS_ROWS))
        resp = await client.get("/api/v1/portfolio/tefas/export", headers=headers)
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    assert ws.cell(row=2, column=1).value == "AFA"
    assert ws.cell(row=2, column=4).value  # birim fiyat dolu


@pytest.mark.asyncio
async def test_import_xlsx_with_avg_cost_and_distributor(client: AsyncClient):
    headers = await make_user(client, "tefas_import@example.com")
    wb = openpyxl.Workbook()
    ws = wb.active
    # Kod, Adet, İsim, Ort.Maliyet(D), -, -, -, Kurum(H)
    ws.append(["Kod", "Adet", "İsim", "Ort.Maliyet", "", "", "", "Kurum"])
    ws.append(["AFA", 100, "Ak", 1.5, "", "", "", "Foneria"])
    ws.append(["ZJI", 50, "Ziraat", 0, "", "", "", None])  # avg_cost 0 → None
    ws.append(["", 5, "Bos", 1, "", "", "", None])  # boş kod → atlanır
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        "/api/v1/portfolio/tefas/import",
        files={"file": ("t.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 2
    afa = next(h for h in holdings if h["code"] == "AFA")
    assert float(afa["avg_cost_tl"]) == 1.5
    assert afa["distributor"] == "Foneria"
    zji = next(h for h in holdings if h["code"] == "ZJI")
    assert zji["avg_cost_tl"] is None


@pytest.mark.asyncio
async def test_import_xlsx_no_valid_rows_422(client: AsyncClient):
    headers = await make_user(client, "tefas_import_empty@example.com")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Kod", "Adet"])
    ws.append(["", 0])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        "/api/v1/portfolio/tefas/import",
        files={"file": ("t.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_xlsx_bad_magic_422(client: AsyncClient):
    headers = await make_user(client, "tefas_import_magic@example.com")
    fake = io.BytesIO(b"%PDF-1.4 fake")
    resp = await client.post(
        "/api/v1/portfolio/tefas/import",
        files={"file": ("t.xlsx", fake, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 422


class _FakeSheet:
    """xlrd Sheet taklidi — MKK parse loop (cell_value + nrows) için."""

    def __init__(self, rows):
        self._rows = rows
        self.nrows = len(rows)

    def cell_value(self, r, c):
        row = self._rows[r]
        return row[c] if c < len(row) else ""


class _FakeWorkbook:
    def __init__(self, sheet):
        self._sheet = sheet

    def sheet_by_index(self, i):
        return self._sheet


def _patch_xlrd(monkeypatch, rows):
    import xlrd

    sheet = _FakeSheet(rows)
    monkeypatch.setattr(xlrd, "open_workbook", lambda **kw: _FakeWorkbook(sheet))


@pytest.mark.asyncio
async def test_import_mkk_happy_path(client: AsyncClient, monkeypatch):
    """MKK 'Fon' satırları parse edilir, .IS suffix yok (TEFAS kodu), distributor=Üye."""
    headers = await make_user(client, "tefas_mkk_ok@example.com")
    # Header: col0=Üye, col2=Kıymet Sınıfı, col3=Kod, col4=Ad, col7=Adet, col8=Fiyat
    rows = [
        ["Üye", "Hesap", "Kıymet Sınıfı", "Menkul Kıymet Kodu", "Kıymet Adı", "Ek Tanım", "Alt", "Adet", "Fiyat"],
        ["Ziraat Yatırım", "X", "Fon", "AFA", "Ak Portföy Fonu", "", "", 100.0, 1.5],
        ["X", "X", "HS", "THYAO", "Hisse", "", "", 50.0, 30.0],  # HS → atlanır
        ["X", "X", "Fon", "", "Kodsuz", "", "", 10.0, 1.0],  # kod boş → atlanır
        ["X", "X", "Fon", "ZJI", "Ziraat", "", "", 0.0, 1.0],  # qty 0 → atlanır
    ]
    _patch_xlrd(monkeypatch, rows)
    with respx.mock(assert_all_called=False) as rsx:
        rsx.post(_EXPORT_URL).mock(return_value=Response(500))  # snapshot best-effort fail OK
        rsx.get(url__regex=r"https?://.*").mock(return_value=Response(500))
        resp = await client.post(
            "/api/v1/portfolio/tefas/import-mkk",
            files={"file": ("mkk.xls", io.BytesIO(_XLS_MAGIC + b"\x00" * 50), "application/vnd.ms-excel")},
            headers=headers,
        )
    assert resp.status_code == 200
    parsed = resp.json()
    assert len(parsed) == 1
    assert parsed[0]["code"] == "AFA"
    assert float(parsed[0]["avg_cost_tl"]) == pytest.approx(1.5, rel=1e-3)
    assert parsed[0]["distributor"] == "Ziraat Yatırım"


@pytest.mark.asyncio
async def test_import_mkk_no_fon_rows_422(client: AsyncClient, monkeypatch):
    """Header var ama hiç 'Fon' satırı yok → 422."""
    headers = await make_user(client, "tefas_mkk_nofon@example.com")
    rows = [
        ["Üye", "Hesap", "Kıymet Sınıfı", "Menkul Kıymet Kodu", "Kıymet Adı", "Ek Tanım", "Alt", "Adet", "Fiyat"],
        ["X", "X", "HS", "THYAO", "Hisse", "A", "", 50.0, 30.0],
    ]
    _patch_xlrd(monkeypatch, rows)
    resp = await client.post(
        "/api/v1/portfolio/tefas/import-mkk",
        files={"file": ("mkk.xls", io.BytesIO(_XLS_MAGIC + b"\x00" * 50), "application/vnd.ms-excel")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_mkk_no_header_422(client: AsyncClient, monkeypatch):
    """'Üye' başlık satırı yoksa → 422."""
    headers = await make_user(client, "tefas_mkk_nohdr@example.com")
    rows = [["Yanlis", "Baslik", "Satiri"]]
    _patch_xlrd(monkeypatch, rows)
    resp = await client.post(
        "/api/v1/portfolio/tefas/import-mkk",
        files={"file": ("mkk.xls", io.BytesIO(_XLS_MAGIC + b"\x00" * 50), "application/vnd.ms-excel")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_mkk_unreadable_xls_422(client: AsyncClient):
    """OLE2 magic ama bozuk içerik → xlrd parse fail → 422."""
    headers = await make_user(client, "tefas_mkk_bad@example.com")
    fake = io.BytesIO(_XLS_MAGIC + b"\x00" * 200)
    resp = await client.post(
        "/api/v1/portfolio/tefas/import-mkk",
        files={"file": ("mkk.xls", fake, "application/vnd.ms-excel")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_mkk_wrong_extension_422(client: AsyncClient):
    headers = await make_user(client, "tefas_mkk_ext@example.com")
    fake = io.BytesIO(_XLS_MAGIC + b"\x00" * 50)
    resp = await client.post(
        "/api/v1/portfolio/tefas/import-mkk",
        files={"file": ("mkk.csv", fake, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_unauth(client: AsyncClient):
    resp = await client.post("/api/v1/portfolio/tefas/import")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_with_holdings_price_fetch_fails(client: AsyncClient):
    """Holding var ama TEFAS fiyat alınamazsa export yine de xlsx döner
    (price=0 kolonlar boş). except branch kapsanır."""
    headers = await make_user(client, "tefas_export_fail@example.com")
    await client.put(
        "/api/v1/portfolio/tefas/holdings",
        json=[{"code": "AFA", "quantity": 100, "name": "Ak"}],
        headers=headers,
    )
    with respx.mock(assert_all_called=False) as rsx:
        rsx.post(_EXPORT_URL).mock(return_value=Response(500))
        resp = await client.get("/api/v1/portfolio/tefas/export", headers=headers)
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    assert ws.cell(row=2, column=1).value == "AFA"
    # Fiyat alınamadı → birim fiyat hücresi boş
    assert ws.cell(row=2, column=4).value in (None, "")
