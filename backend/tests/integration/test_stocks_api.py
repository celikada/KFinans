"""TEST-011 (FAZ H): Stocks endpoint testleri.

Holding CRUD + replace-all PUT semantik + auth + validation. MKK Excel
import disardan dosya gerektirdigi icin (xlrd 1.2.0) bu test dosyasinda
kapsam disi; respx mock'siz gercek Yahoo cagrisi yapan preview endpoint'i
de network bagli oldugu icin lite tutuluyor.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


@pytest.mark.asyncio
async def test_get_holdings_empty(client: AsyncClient):
    headers = await make_user(client, "stock_empty@example.com")
    resp = await client.get("/api/v1/portfolio/stocks/holdings", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_holdings_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/stocks/holdings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_holdings_replace_all(client: AsyncClient):
    """PUT replace-all: eski kayitlar silinir, yeni kayitlar yazilir."""
    headers = await make_user(client, "stock_put@example.com")

    # Ilk kayit
    first = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "AAPL", "quantity": 10, "name": "Apple Inc."},
            {"ticker": "GOOGL", "quantity": 5, "name": "Alphabet"},
        ],
        headers=headers,
    )
    assert first.status_code == 200
    assert len(first.json()) == 2

    # Ikinci kayit AAPL'i siler, MSFT ekler
    second = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "MSFT", "quantity": 8, "name": "Microsoft"},
        ],
        headers=headers,
    )
    assert second.status_code == 200
    assert len(second.json()) == 1
    assert second.json()[0]["ticker"] == "MSFT"


@pytest.mark.asyncio
async def test_put_holdings_with_avg_cost(client: AsyncClient):
    """avg_cost_tl alani opsiyonel; pozitif deger korunur."""
    headers = await make_user(client, "stock_cost@example.com")
    resp = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "AAPL", "quantity": 10, "name": "Apple", "avg_cost_tl": 5500.50},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    h = resp.json()[0]
    assert float(h["avg_cost_tl"]) == 5500.50


@pytest.mark.asyncio
async def test_put_holdings_avg_cost_zero_normalized_to_none(client: AsyncClient):
    """Schema validator: avg_cost_tl <= 0 ise None'a normalize edilir
    (kullanici bilmiyorsa bos birakabilir)."""
    headers = await make_user(client, "stock_zerocost@example.com")
    resp = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "AAPL", "quantity": 10, "name": "Apple", "avg_cost_tl": 0},
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    h = resp.json()[0]
    assert h["avg_cost_tl"] is None


@pytest.mark.asyncio
async def test_put_holdings_with_distributor(client: AsyncClient):
    """distributor (aracikurum) alani — ayni ticker farklikurumda ayri kayit."""
    headers = await make_user(client, "stock_dist@example.com")
    resp = await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[
            {"ticker": "AAPL", "quantity": 10, "name": "Apple", "distributor": "Is Yatirim"},
            {
                "ticker": "AAPL",
                "quantity": 5,
                "name": "Apple",
                "distributor": "Garanti BBVA Yatirim",
            },
        ],
        headers=headers,
    )
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 2
    distributors = {h["distributor"] for h in holdings}
    assert distributors == {"Is Yatirim", "Garanti BBVA Yatirim"}


@pytest.mark.asyncio
async def test_export_holdings_empty_returns_xlsx(client: AsyncClient):
    """Export bos kayitla bile xlsx dondurmeli (header satirlari)."""
    headers = await make_user(client, "stock_export@example.com")
    resp = await client.get("/api/v1/portfolio/stocks/export", headers=headers)
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_holdings_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/stocks/export")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Ek kapsam: preview (Yahoo + TCMB mock), import (xlsx + MKK), export canlı fiyat
# ---------------------------------------------------------------------------
import io

import openpyxl
import respx
from httpx import Response

from app.services.aggregator import EXCHANGERATE_API_GBP, EXCHANGERATE_API_USD, TCMB_URL

_USD_TL = {"rates": {"TRY": 35.0}}
_GBP_USD = {"rates": {"USD": 1.25}}
_TCMB_EMPTY = b'<?xml version="1.0" encoding="utf-8"?><Tarih_Date></Tarih_Date>'


def _mock_rates(rsx):
    rsx.get(TCMB_URL).mock(return_value=Response(200, content=_TCMB_EMPTY))
    rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(200, json=_USD_TL))
    rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(200, json=_GBP_USD))


def _yf_resp(price, currency="USD", name="Apple Inc."):
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": price,
                        "currency": currency,
                        "longName": name,
                        "marketState": "REGULAR",
                    }
                }
            ],
            "error": None,
        }
    }


@pytest.mark.asyncio
async def test_preview_usd_stock(client: AsyncClient):
    """USD hisse → TL'ye çevrilir; gain/loss avg_cost ile hesaplanır."""
    headers = await make_user(client, "stock_preview_usd@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        rsx.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/AAPL.*").mock(return_value=Response(200, json=_yf_resp(100.0)))
        resp = await client.post(
            "/api/v1/portfolio/stocks/preview",
            json=[{"ticker": "AAPL", "quantity": 10, "name": "Apple", "avg_cost_tl": 3000}],
            headers=headers,
        )
    assert resp.status_code == 200
    pos = resp.json()[0]
    # 100 USD * 35 = 3500 TL birim; 10 adet = 35000 TL
    assert float(pos["unit_price_tl"]) == pytest.approx(3500.0, rel=1e-3)
    assert float(pos["total_value_tl"]) == pytest.approx(35000.0, rel=1e-3)
    # cost_basis = 10*3000 = 30000; gain = 5000
    assert float(pos["gain_loss_tl"]) == pytest.approx(5000.0, rel=1e-3)
    assert pos["gain_loss_pct"] is not None


@pytest.mark.asyncio
async def test_preview_try_stock_no_conversion(client: AsyncClient):
    """TRY hisse fiyatı doğrudan kullanılır (kur çevirimi yok)."""
    headers = await make_user(client, "stock_preview_try@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        rsx.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/THYAO\.IS.*").mock(
            return_value=Response(200, json=_yf_resp(250.0, currency="TRY", name="Turk Hava Yollari"))
        )
        resp = await client.post(
            "/api/v1/portfolio/stocks/preview",
            json=[{"ticker": "THYAO.IS", "quantity": 4, "name": ""}],
            headers=headers,
        )
    assert resp.status_code == 200
    pos = resp.json()[0]
    assert pos["currency"] == "TRY"
    assert float(pos["unit_price_tl"]) == pytest.approx(250.0, rel=1e-3)
    assert pos["gain_loss_tl"] is None  # avg_cost yok


@pytest.mark.asyncio
async def test_preview_gbp_pence_conversion(client: AsyncClient):
    """GBp (pence) → GBP → USD → TL zinciri."""
    headers = await make_user(client, "stock_preview_gbp@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        rsx.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/VOD\.L.*").mock(
            return_value=Response(200, json=_yf_resp(100.0, currency="GBp", name="Vodafone"))
        )
        resp = await client.post(
            "/api/v1/portfolio/stocks/preview",
            json=[{"ticker": "VOD.L", "quantity": 1, "name": ""}],
            headers=headers,
        )
    assert resp.status_code == 200
    pos = resp.json()[0]
    # 100 pence = 1 GBP * 1.25 USD/GBP = 1.25 USD * 35 = 43.75 TL
    assert float(pos["unit_price_tl"]) == pytest.approx(43.75, rel=1e-3)


@pytest.mark.asyncio
async def test_preview_unknown_ticker_422(client: AsyncClient):
    """Yahoo fiyat dönmezse 422."""
    headers = await make_user(client, "stock_preview_404@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        rsx.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/.*").mock(return_value=Response(404))
        resp = await client.post(
            "/api/v1/portfolio/stocks/preview",
            json=[{"ticker": "NOPE.IS", "quantity": 1, "name": ""}],
            headers=headers,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_preview_unauth(client: AsyncClient):
    resp = await client.post("/api/v1/portfolio/stocks/preview", json=[])
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_with_live_prices(client: AsyncClient):
    """Export canlı fiyatlarla (Yahoo mock) — toplam değer dolu döner."""
    headers = await make_user(client, "stock_export_live@example.com")
    await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[{"ticker": "AAPL", "quantity": 10, "name": "Apple", "avg_cost_tl": 3000}],
        headers=headers,
    )
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        rsx.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/AAPL.*").mock(return_value=Response(200, json=_yf_resp(100.0)))
        resp = await client.get("/api/v1/portfolio/stocks/export", headers=headers)
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    # row2 = ilk veri; col4 = birim fiyat (TL)
    assert ws.cell(row=2, column=1).value == "AAPL"
    assert ws.cell(row=2, column=4).value  # birim fiyat dolu


@pytest.mark.asyncio
async def test_import_xlsx_with_avg_cost_and_distributor(client: AsyncClient):
    headers = await make_user(client, "stock_import@example.com")
    wb = openpyxl.Workbook()
    ws = wb.active
    # Ticker, Adet, İsim, Ort.Maliyet(D), -, -, -, Kurum(H)
    ws.append(["Ticker", "Adet", "İsim", "Ort.Maliyet", "", "", "", "Kurum"])
    ws.append(["AAPL", 10, "Apple", 3000, "", "", "", "Is Yatirim"])
    ws.append(["GOOGL", 5, "Alphabet", 0, "", "", "", None])  # avg_cost 0 → None
    ws.append(["", 5, "Bos ticker", 1, "", "", "", None])  # ticker boş → atlanır
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        "/api/v1/portfolio/stocks/import",
        files={"file": ("s.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 2
    aapl = next(h for h in holdings if h["ticker"] == "AAPL")
    assert float(aapl["avg_cost_tl"]) == 3000
    assert aapl["distributor"] == "Is Yatirim"
    googl = next(h for h in holdings if h["ticker"] == "GOOGL")
    assert googl["avg_cost_tl"] is None


@pytest.mark.asyncio
async def test_import_xlsx_no_valid_rows_422(client: AsyncClient):
    headers = await make_user(client, "stock_import_empty@example.com")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Ticker", "Adet"])
    ws.append(["", 0])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = await client.post(
        "/api/v1/portfolio/stocks/import",
        files={"file": ("s.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert resp.status_code == 422


# MKK .xls binary üretimi için xlwt test ortamında yok; xlrd OLE2 binary
# bekler. Bu nedenle MKK endpoint'inin hata yollarını (magic byte + okunamayan
# dosya) test ediyoruz; mutlu yol birim testlerinde xlrd fixture ile kapsanır.
_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class _FakeSheet:
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
    """MKK HS + Ek Tanım=A satırları parse edilir; .IS suffix eklenir, distributor=Üye."""
    headers = await make_user(client, "stock_mkk_ok@example.com")
    # col0=Üye, col2=Kıymet Sınıfı, col3=Kod, col4=Ad, col5=Ek Tanım, col7=Adet, col8=Fiyat
    rows = [
        ["Üye", "Hesap", "Kıymet Sınıfı", "Menkul Kıymet Kodu", "Kıymet Adı", "Ek Tanım", "Alt", "Adet", "Fiyat"],
        ["Is Yatirim", "X", "HS", "THYAO", "Turk Hava Yollari", "A", "", 100.0, 250.5],
        ["X", "X", "HS", "GARAN", "Garanti", "B", "", 50.0, 30.0],  # Ek Tanım != A → atlanır
        ["X", "X", "Fon", "AFA", "Fon", "A", "", 10.0, 1.0],  # Fon → atlanır
        ["X", "X", "HS", "AKBNK.IS", "Akbank zaten suffix", "A", "", 5.0, 40.0],  # nokta varsa suffix eklenmez
        ["X", "X", "HS", "", "Kodsuz", "A", "", 5.0, 1.0],  # kod boş → atlanır
        ["X", "X", "HS", "BIMAS", "Bim", "A", "", 0.0, 10.0],  # qty 0 → atlanır
    ]
    _patch_xlrd(monkeypatch, rows)
    with respx.mock(assert_all_called=False) as rsx:
        rsx.get(url__regex=r"https?://.*").mock(return_value=Response(500))  # snapshot best-effort
        resp = await client.post(
            "/api/v1/portfolio/stocks/import-mkk",
            files={"file": ("mkk.xls", io.BytesIO(_XLS_MAGIC + b"\x00" * 50), "application/vnd.ms-excel")},
            headers=headers,
        )
    assert resp.status_code == 200
    parsed = resp.json()
    tickers = {h["ticker"] for h in parsed}
    assert tickers == {"THYAO.IS", "AKBNK.IS"}  # suffix eklendi / korundu
    thy = next(h for h in parsed if h["ticker"] == "THYAO.IS")
    assert thy["distributor"] == "Is Yatirim"
    assert float(thy["avg_cost_tl"]) == pytest.approx(250.5, rel=1e-3)


@pytest.mark.asyncio
async def test_import_mkk_no_valid_rows_422(client: AsyncClient, monkeypatch):
    """HS+A satırı yok → 422."""
    headers = await make_user(client, "stock_mkk_novalid@example.com")
    rows = [
        ["Üye", "Hesap", "Kıymet Sınıfı", "Menkul Kıymet Kodu", "Kıymet Adı", "Ek Tanım", "Alt", "Adet", "Fiyat"],
        ["X", "X", "Fon", "AFA", "Fon", "A", "", 10.0, 1.0],
    ]
    _patch_xlrd(monkeypatch, rows)
    resp = await client.post(
        "/api/v1/portfolio/stocks/import-mkk",
        files={"file": ("mkk.xls", io.BytesIO(_XLS_MAGIC + b"\x00" * 50), "application/vnd.ms-excel")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_mkk_no_header_422_fake(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "stock_mkk_nohdr2@example.com")
    rows = [["Yanlis", "Baslik"]]
    _patch_xlrd(monkeypatch, rows)
    resp = await client.post(
        "/api/v1/portfolio/stocks/import-mkk",
        files={"file": ("mkk.xls", io.BytesIO(_XLS_MAGIC + b"\x00" * 50), "application/vnd.ms-excel")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_mkk_unreadable_xls_422(client: AsyncClient):
    """Geçerli OLE2 magic byte ama bozuk içerik → xlrd parse fail → 422."""
    headers = await make_user(client, "stock_mkk_bad@example.com")
    fake = io.BytesIO(_XLS_MAGIC + b"\x00" * 200)
    resp = await client.post(
        "/api/v1/portfolio/stocks/import-mkk",
        files={"file": ("mkk.xls", fake, "application/vnd.ms-excel")},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_with_holdings_price_fetch_fails(client: AsyncClient):
    """Holding var ama canlı fiyat alınamazsa export yine de xlsx döner
    (price boş kolonlar). except branch'i kapsar."""
    headers = await make_user(client, "stock_export_fail@example.com")
    await client.put(
        "/api/v1/portfolio/stocks/holdings",
        json=[{"ticker": "AAPL", "quantity": 10, "name": "Apple"}],
        headers=headers,
    )
    with respx.mock(assert_all_called=False) as rsx:
        # TCMB + exchangerate fail → fetch_usd_to_tl RuntimeError → except → quotes boş
        rsx.get(TCMB_URL).mock(return_value=Response(503))
        rsx.get(EXCHANGERATE_API_USD).mock(return_value=Response(500))
        rsx.get(EXCHANGERATE_API_GBP).mock(return_value=Response(500))
        rsx.get(url__regex=r"https://query1\.finance\.yahoo\.com/.*").mock(return_value=Response(500))
        resp = await client.get("/api/v1/portfolio/stocks/export", headers=headers)
    assert resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    assert ws.cell(row=2, column=1).value == "AAPL"
    # Fiyat alınamadı → birim fiyat hücresi boş
    assert ws.cell(row=2, column=4).value in (None, "")


@pytest.mark.asyncio
async def test_preview_name_fallback_to_quote(client: AsyncClient):
    """holding.name boşsa quote.name kullanılır."""
    headers = await make_user(client, "stock_preview_namefb@example.com")
    with respx.mock(assert_all_called=False) as rsx:
        _mock_rates(rsx)
        rsx.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/AAPL.*").mock(
            return_value=Response(200, json=_yf_resp(100.0, name="Apple Inc."))
        )
        resp = await client.post(
            "/api/v1/portfolio/stocks/preview",
            json=[{"ticker": "AAPL", "quantity": 1, "name": ""}],
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Apple Inc."


@pytest.mark.asyncio
async def test_import_mkk_wrong_extension_422(client: AsyncClient):
    """.txt uzantı → validate_excel_upload reddeder (422)."""
    headers = await make_user(client, "stock_mkk_ext@example.com")
    fake = io.BytesIO(_XLS_MAGIC + b"\x00" * 50)
    resp = await client.post(
        "/api/v1/portfolio/stocks/import-mkk",
        files={"file": ("mkk.txt", fake, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422
