"""
Cash (nakit/banka hesabı) CRUD endpoint testleri.

Endpoint'ler:
  GET    /cash             — kullanıcının nakit holding'leri (TL toplam ile)
  POST   /cash             — yeni holding ekle
  PUT    /cash/{id}        — güncelle (partial)
  DELETE /cash/{id}        — sil

USD/EUR/GBP holding'leri için _amount_to_tl TCMB API çağırır → respx ile mock.
"""

from decimal import Decimal

import pytest
import respx
from httpx import AsyncClient, Response

from tests.conftest import make_user


def _mock_tcmb(usd_to_tl: float = 40.0, eur_to_tl: float = 44.0, gbp_to_tl: float = 50.0):
    """TCMB XML mock (services/aggregator için).

    FIN-007 (FAZ H): EUR/GBP ayri kurlar test edilebilsin diye parametreli.
    Aggregator 5 dk in-memory cache'lidir; her test fonksiyonu icin yeni respx
    context'i mock'i sifirlamaz ama _tcmb_cache test sirasinda ozdes kalir
    (process icinde her TCMB cagrisi idempotent).
    """
    xml = f"""<?xml version="1.0" encoding="ISO-8859-9"?>
<Tarih_Date Tarih="07.05.2026">
  <Currency CrossOrder="0" Kod="USD" CurrencyCode="USD">
    <Unit>1</Unit>
    <Isim>ABD DOLARI</Isim>
    <CurrencyName>US DOLLAR</CurrencyName>
    <ForexBuying>{usd_to_tl}</ForexBuying>
    <ForexSelling>{usd_to_tl + 0.01}</ForexSelling>
    <BanknoteBuying>{usd_to_tl - 0.01}</BanknoteBuying>
    <BanknoteSelling>{usd_to_tl + 0.02}</BanknoteSelling>
  </Currency>
  <Currency CrossOrder="0" Kod="EUR" CurrencyCode="EUR">
    <Unit>1</Unit>
    <Isim>EURO</Isim>
    <CurrencyName>EURO</CurrencyName>
    <ForexBuying>{eur_to_tl}</ForexBuying>
    <ForexSelling>{eur_to_tl + 0.01}</ForexSelling>
  </Currency>
  <Currency CrossOrder="0" Kod="GBP" CurrencyCode="GBP">
    <Unit>1</Unit>
    <Isim>INGILIZ STERLINI</Isim>
    <CurrencyName>POUND STERLING</CurrencyName>
    <ForexBuying>{gbp_to_tl}</ForexBuying>
    <ForexSelling>{gbp_to_tl + 0.01}</ForexSelling>
  </Currency>
</Tarih_Date>"""
    respx.get("https://www.tcmb.gov.tr/kurlar/today.xml").mock(
        return_value=Response(200, content=xml, headers={"Content-Type": "application/xml"})
    )


# ─── Auth ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/cash")
    assert resp.status_code == 401
    resp = await client.post("/api/v1/cash", json={"label": "x", "amount": "100"})
    assert resp.status_code == 401


# ─── List (GET) ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_list_cash_empty(client: AsyncClient):
    headers = await make_user(client, "cash_empty@example.com")
    resp = await client.get("/api/v1/cash", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["holdings"] == []
    assert Decimal(data["total_tl"]) == 0


# ─── Create (POST) ────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_create_cash_try(client: AsyncClient):
    headers = await make_user(client, "cash_create_try@example.com")
    resp = await client.post(
        "/api/v1/cash",
        json={"label": "Garanti TL", "amount": "5000.00", "currency": "TRY"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Garanti TL"
    assert Decimal(data["amount"]) == Decimal("5000.00")
    assert data["currency"] == "TRY"
    assert Decimal(data["amount_tl"]) == Decimal("5000.00")  # TRY → 1:1
    assert "id" in data


@pytest.mark.asyncio
@respx.mock
async def test_create_cash_usd_converts_to_tl(client: AsyncClient):
    """USD holding amount_tl = amount × USD/TRY kuru."""
    _mock_tcmb(usd_to_tl=40.0)
    headers = await make_user(client, "cash_usd@example.com")
    resp = await client.post(
        "/api/v1/cash",
        json={"label": "Wise USD", "amount": "100", "currency": "USD"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["currency"] == "USD"
    assert Decimal(data["amount_tl"]) == Decimal("4000.00")  # 100 × 40


@pytest.mark.asyncio
@respx.mock
async def test_create_cash_eur_uses_tcmb_eur_rate_not_usd(client: AsyncClient):
    """FIN-007 (FAZ H): EUR holding TCMB EUR/TRY ile cevrilir, USD/TRY ile DEGIL.

    Eski bug: 100 EUR × 40 USD/TL = 4000 TL (yanlis)
    Dogru:    100 EUR × 44 EUR/TL = 4400 TL
    """
    _mock_tcmb(usd_to_tl=40.0, eur_to_tl=44.0)
    headers = await make_user(client, "cash_eur@example.com")
    resp = await client.post(
        "/api/v1/cash",
        json={"label": "Wise EUR", "amount": "100", "currency": "EUR"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["currency"] == "EUR"
    assert Decimal(data["amount_tl"]) == Decimal("4400.00")
    # USD/TRY ile cevrilseydi 4000.00 olurdu — degil
    assert Decimal(data["amount_tl"]) != Decimal("4000.00")


@pytest.mark.asyncio
@respx.mock
async def test_create_cash_gbp_uses_tcmb_gbp_rate(client: AsyncClient):
    """FIN-007: GBP holding TCMB GBP/TRY ile cevrilir."""
    _mock_tcmb(usd_to_tl=40.0, gbp_to_tl=50.0)
    headers = await make_user(client, "cash_gbp@example.com")
    resp = await client.post(
        "/api/v1/cash",
        json={"label": "Revolut GBP", "amount": "200", "currency": "GBP"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert Decimal(resp.json()["amount_tl"]) == Decimal("10000.00")  # 200 × 50


@pytest.mark.asyncio
@respx.mock
async def test_create_cash_label_required(client: AsyncClient):
    headers = await make_user(client, "cash_no_label@example.com")
    resp = await client.post(
        "/api/v1/cash",
        json={"amount": "100", "currency": "TRY"},  # label yok
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
@respx.mock
async def test_create_cash_negative_amount_returns_422(client: AsyncClient):
    headers = await make_user(client, "cash_negative@example.com")
    resp = await client.post(
        "/api/v1/cash",
        json={"label": "Eksi", "amount": "-100", "currency": "TRY"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
@respx.mock
async def test_create_cash_invalid_currency_returns_422(client: AsyncClient):
    headers = await make_user(client, "cash_bad_curr@example.com")
    resp = await client.post(
        "/api/v1/cash",
        json={"label": "x", "amount": "100", "currency": "JPY"},  # desteklenmiyor
        headers=headers,
    )
    assert resp.status_code == 422


# ─── Update (PUT) ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_update_cash_partial_label_only(client: AsyncClient):
    headers = await make_user(client, "cash_update@example.com")
    create = await client.post(
        "/api/v1/cash",
        json={"label": "Eski", "amount": "100", "currency": "TRY"},
        headers=headers,
    )
    cash_id = create.json()["id"]

    resp = await client.put(
        f"/api/v1/cash/{cash_id}",
        json={"label": "Yeni"},  # sadece label
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "Yeni"
    assert Decimal(data["amount"]) == Decimal("100")  # değişmedi


@pytest.mark.asyncio
@respx.mock
async def test_update_cash_not_found_returns_404(client: AsyncClient):
    headers = await make_user(client, "cash_404@example.com")
    resp = await client.put(
        "/api/v1/cash/99999",
        json={"label": "x"},
        headers=headers,
    )
    assert resp.status_code == 404


# ─── Delete ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_delete_cash_succeeds(client: AsyncClient):
    headers = await make_user(client, "cash_delete@example.com")
    create = await client.post(
        "/api/v1/cash",
        json={"label": "Silinecek", "amount": "50", "currency": "TRY"},
        headers=headers,
    )
    cash_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/cash/{cash_id}", headers=headers)
    assert resp.status_code == 204

    # Listede artık görünmemeli
    list_resp = await client.get("/api/v1/cash", headers=headers)
    ids = [h["id"] for h in list_resp.json()["holdings"]]
    assert cash_id not in ids


@pytest.mark.asyncio
@respx.mock
async def test_delete_cash_not_found(client: AsyncClient):
    headers = await make_user(client, "cash_del_404@example.com")
    resp = await client.delete("/api/v1/cash/99999", headers=headers)
    assert resp.status_code == 404


# ─── IDOR ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_user_b_cannot_see_user_a_cash(client: AsyncClient):
    headers_a = await make_user(client, "cash_idor_a@example.com")
    headers_b = await make_user(client, "cash_idor_b@example.com")

    await client.post(
        "/api/v1/cash",
        json={"label": "A'nin parasi", "amount": "1000", "currency": "TRY"},
        headers=headers_a,
    )

    list_b = await client.get("/api/v1/cash", headers=headers_b)
    assert list_b.json()["holdings"] == []


@pytest.mark.asyncio
@respx.mock
async def test_user_b_cannot_update_user_a_cash(client: AsyncClient):
    """B, A'nın cash_id'sini biliyor olsa bile update edemez (404)."""
    headers_a = await make_user(client, "cash_idor_upd_a@example.com")
    headers_b = await make_user(client, "cash_idor_upd_b@example.com")

    create = await client.post(
        "/api/v1/cash",
        json={"label": "A'nin", "amount": "100", "currency": "TRY"},
        headers=headers_a,
    )
    a_cash_id = create.json()["id"]

    resp = await client.put(
        f"/api/v1/cash/{a_cash_id}",
        json={"label": "B'nin sahteciliği"},
        headers=headers_b,
    )
    assert resp.status_code == 404
