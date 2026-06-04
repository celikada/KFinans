"""Çoklu para birimi (v0.3.0) endpoint entegrasyon testleri (kf-test DB).

Hibrit kur doğrulaması:
- income/expense create/update → işlem-anı kuruyla `amount_tl` SABİTLENİR
  (currency + exchange_rate saklanır).
- summary/dashboard → `amount_tl` (sabit TL) toplanır.
- realize → currency taşınır + o anki kurla amount_tl sabitlenir.
- cash_flow → geçmiş ay actual + gelecek ay forecast.
- geriye uyumluluk → currency vermeden TRY default, amount_tl=amount.

Gerçek dış çağrı (TCMB) YOK. `currency.fetch_rates` monkeypatch ile mock'lanır.
income.py + expenses.py + income realize hepsi `currency_svc.fetch_rates()`
çağırır (modül attribute erişimi); `app.services.currency.fetch_rates` patch'i
üçünü birden kapsar.

Doğrulanan gerçek alanlar/endpoint'ler (kaynak koddan okundu):
- Income/Expense modeli: amount, currency, amount_tl, exchange_rate (Numeric)
- IncomeOut/ExpenseOut: currency + amount_tl alanları döner
- POST /income, POST /expenses, GET /income/summary, /income/dashboard,
  GET /expenses/summary, POST /income/recurring + /realize, GET /cash-flow
- _resolve_amount_tl: TRY → (amount, 1); diğer → convert_to_tl + rate
"""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from tests.conftest import make_user

# Sabit mock kur haritası — patch'lenen fetch_rates bunu döner.
_MOCK_RATES = {
    "TRY": Decimal("1"),
    "USD": Decimal("35"),
    "EUR": Decimal("38"),
    "GBP": Decimal("44"),
    "CHF": Decimal("40"),
    "JPY": Decimal("0.23"),
}


@pytest.fixture(autouse=True)
def _mock_currency_rates(monkeypatch):
    """Tüm currency-aware endpoint'lerin kur kaynağını mock'la (TCMB çağrısı yok).

    income.py, expenses.py ve income realize akışı `currency_svc.fetch_rates()`
    çağırır — hepsi `app.services.currency` modül attribute'unu kullanır, bu
    yüzden tek patch üçünü de kapsar.
    """
    monkeypatch.setattr(
        "app.services.currency.fetch_rates",
        AsyncMock(return_value=dict(_MOCK_RATES)),
    )
    yield


# ===========================================================================
# income — amount_tl sabitleme (create)
# ===========================================================================
@pytest.mark.asyncio
async def test_create_income_usd_fixes_amount_tl(client):
    """USD gelir → amount_tl = amount*35, currency=USD, exchange_rate=35."""
    headers = await make_user(client)
    resp = await client.post(
        "/api/v1/income",
        headers=headers,
        json={
            "amount": "100",
            "category": "salary",
            "date": "2026-01-15",
            "currency": "USD",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["currency"] == "USD"
    assert Decimal(str(data["amount"])) == Decimal("100")
    assert Decimal(str(data["amount_tl"])) == Decimal("3500.00")


@pytest.mark.asyncio
async def test_create_income_try_amount_tl_equals_amount(client):
    """TRY gelir → amount_tl = amount, exchange_rate=1 (kur sorgusu yok)."""
    headers = await make_user(client)
    resp = await client.post(
        "/api/v1/income",
        headers=headers,
        json={
            "amount": "1500",
            "category": "salary",
            "date": "2026-01-10",
            "currency": "TRY",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["currency"] == "TRY"
    assert Decimal(str(data["amount_tl"])) == Decimal("1500.00")


@pytest.mark.asyncio
async def test_create_income_no_currency_defaults_try(client):
    """Geriye uyumluluk: currency vermeden → TRY default, amount_tl=amount."""
    headers = await make_user(client)
    resp = await client.post(
        "/api/v1/income",
        headers=headers,
        json={"amount": "2000", "category": "rental", "date": "2026-02-01"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["currency"] == "TRY"
    assert Decimal(str(data["amount_tl"])) == Decimal("2000.00")


@pytest.mark.asyncio
async def test_update_income_currency_refixes_amount_tl(client):
    """Para birimi güncellenince amount_tl yeniden sabitlenir (güncel kur)."""
    headers = await make_user(client)
    created = await client.post(
        "/api/v1/income",
        headers=headers,
        json={"amount": "100", "category": "salary", "date": "2026-01-15", "currency": "TRY"},
    )
    inc_id = created.json()["id"]
    resp = await client.put(
        f"/api/v1/income/{inc_id}",
        headers=headers,
        json={"currency": "EUR"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["currency"] == "EUR"
    # 100 EUR * 38 = 3800
    assert Decimal(str(data["amount_tl"])) == Decimal("3800.00")


# ===========================================================================
# income summary / dashboard — amount_tl toplamı (multi-currency)
# ===========================================================================
@pytest.mark.asyncio
async def test_income_summary_sums_amount_tl_multi_currency(client):
    """USD + EUR + TRY income → summary.total = amount_tl toplamı (TL)."""
    headers = await make_user(client)
    # USD 100 -> 3500 TL
    await client.post(
        "/api/v1/income",
        headers=headers,
        json={"amount": "100", "category": "salary", "date": "2026-03-05", "currency": "USD"},
    )
    # EUR 100 -> 3800 TL
    await client.post(
        "/api/v1/income",
        headers=headers,
        json={"amount": "100", "category": "rental", "date": "2026-03-10", "currency": "EUR"},
    )
    # TRY 1000 -> 1000 TL
    await client.post(
        "/api/v1/income",
        headers=headers,
        json={"amount": "1000", "category": "bonus", "date": "2026-03-20", "currency": "TRY"},
    )
    resp = await client.get("/api/v1/income/summary?year=2026&month=3", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 3
    # 3500 + 3800 + 1000 = 8300
    assert Decimal(str(data["total"])) == Decimal("8300.00")


@pytest.mark.asyncio
async def test_income_dashboard_actual_uses_amount_tl(client):
    """Dashboard this_month_actual/ytd_actual amount_tl toplamı (TL)."""
    headers = await make_user(client)
    await client.post(
        "/api/v1/income",
        headers=headers,
        json={"amount": "200", "category": "salary", "date": "2026-04-05", "currency": "USD"},
    )
    await client.post(
        "/api/v1/income",
        headers=headers,
        json={"amount": "500", "category": "bonus", "date": "2026-04-12", "currency": "TRY"},
    )
    resp = await client.get("/api/v1/income/dashboard?year=2026&month=4", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 200 USD * 35 = 7000 ; + 500 TRY = 7500
    assert Decimal(str(data["this_month_actual"])) == Decimal("7500.00")
    assert Decimal(str(data["ytd_actual"])) == Decimal("7500.00")


@pytest.mark.asyncio
async def test_income_dashboard_recurring_uses_current_rate(client):
    """Periyodik (tahmin) gelir GÜNCEL kurla TL'ye çevrilir (hibrit kur)."""
    headers = await make_user(client)
    # USD aylık recurring — dashboard'da güncel kurla (35) çevrilmeli
    await client.post(
        "/api/v1/income/recurring",
        headers=headers,
        json={
            "title": "USD maaş",
            "amount": "100",
            "category": "salary",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "currency": "USD",
        },
    )
    resp = await client.get("/api/v1/income/dashboard?year=2026&month=6", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # this_month_recurring: 100 USD * 35 = 3500 TL
    assert Decimal(str(data["this_month_recurring"])) == Decimal("3500.00")


# ===========================================================================
# expense — amount_tl sabitleme + summary (çift sayım filtresi korunur)
# ===========================================================================
@pytest.mark.asyncio
async def test_create_expense_usd_fixes_amount_tl(client):
    """USD harcama → amount_tl = amount*35, currency=USD."""
    headers = await make_user(client)
    resp = await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={"amount": "50", "category": "food", "date": "2026-05-05", "currency": "USD"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["currency"] == "USD"
    assert Decimal(str(data["amount_tl"])) == Decimal("1750.00")


@pytest.mark.asyncio
async def test_create_expense_no_currency_defaults_try(client):
    """Geriye uyumluluk: currency yok → TRY default, amount_tl=amount."""
    headers = await make_user(client)
    resp = await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={"amount": "300", "category": "bills", "date": "2026-05-08"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["currency"] == "TRY"
    assert Decimal(str(data["amount_tl"])) == Decimal("300.00")


@pytest.mark.asyncio
async def test_expense_summary_sums_amount_tl_multi_currency(client):
    """USD + TRY harcama → summary.total = amount_tl toplamı (TL)."""
    headers = await make_user(client)
    await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={"amount": "100", "category": "food", "date": "2026-06-03", "currency": "USD"},
    )
    await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={"amount": "600", "category": "bills", "date": "2026-06-09", "currency": "TRY"},
    )
    resp = await client.get("/api/v1/expenses/summary?year=2026&month=6", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 2
    # 100 USD * 35 = 3500 ; + 600 TRY = 4100
    assert Decimal(str(data["total"])) == Decimal("4100.00")


@pytest.mark.asyncio
async def test_expense_summary_double_count_filter_with_currency(client):
    """Çift sayım filtresi currency ile birlikte korunur.

    credit_card_id + is_paid=true USD harcama summary'den HARİÇ kalır;
    nakit USD harcama amount_tl ile sayılır.
    """
    headers = await make_user(client)
    # Kart oluştur (çift sayım için credit_card_id gerekiyor)
    card = await client.post(
        "/api/v1/credit-cards",
        headers=headers,
        json={
            "name": "Test Kart",
            "bank_name": "Test Bank",
            "statement_day": 1,
            "payment_due_day": 10,
        },
    )
    assert card.status_code in (200, 201), card.text
    card_id = card.json()["id"]
    # Kart + ödendi USD harcama → HARİÇ
    await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": "100",
            "category": "food",
            "date": "2026-07-02",
            "currency": "USD",
            "credit_card_id": card_id,
            "is_paid": True,
        },
    )
    # Nakit USD harcama → DAHİL (100 USD * 35 = 3500)
    await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={"amount": "100", "category": "bills", "date": "2026-07-05", "currency": "USD"},
    )
    resp = await client.get("/api/v1/expenses/summary?year=2026&month=7", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 1  # sadece nakit olan sayıldı
    assert Decimal(str(data["total"])) == Decimal("3500.00")


# ===========================================================================
# realize — kur taşıma + amount_tl sabitleme
# ===========================================================================
@pytest.mark.asyncio
async def test_realize_carries_currency_and_fixes_amount_tl(client):
    """recurring (USD) realize → oluşan income currency=USD + amount_tl sabit."""
    headers = await make_user(client)
    rec = await client.post(
        "/api/v1/income/recurring",
        headers=headers,
        json={
            "title": "USD kira",
            "amount": "200",
            "category": "rental",
            "recurrence": "monthly",
            "start_date": "2026-01-01",
            "day_of_month": 1,
            "currency": "USD",
        },
    )
    assert rec.status_code == 201, rec.text
    rid = rec.json()["id"]
    # Geçmiş bir dönemi realize et (ödeme günü geçmiş olmalı)
    resp = await client.post(
        f"/api/v1/income/recurring/{rid}/realize",
        headers=headers,
        json={"year": 2026, "month": 1},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["realized"] == 1
    new_id = body["income_ids"][0]
    # Oluşan income'ı çek, currency + amount_tl doğrula
    listing = await client.get("/api/v1/income?year=2026&month=1", headers=headers)
    assert listing.status_code == 200, listing.text
    rows = [r for r in listing.json() if r["id"] == new_id]
    assert len(rows) == 1
    realized = rows[0]
    assert realized["currency"] == "USD"
    # 200 USD * 35 = 7000 TL (realize anı kuruyla sabit)
    assert Decimal(str(realized["amount_tl"])) == Decimal("7000.00")


# ===========================================================================
# cash_flow — geçmiş ay actual + gelecek ay forecast (TRY tutarlar)
# ===========================================================================
@pytest.mark.asyncio
async def test_cash_flow_actual_and_forecast_months(client):
    """Geçmiş ay income/expense (actual) + gelecek ay recurring/planned (forecast).

    cash_flow ham `amount` üzerinden çalışır; TRY kayıtlarda amount==amount_tl
    olduğundan TL toplamları doğru doğrulanır.
    """
    headers = await make_user(client)
    # Geçmiş bir yıl seç (tüm aylar is_past) — actual değerler.
    await client.post(
        "/api/v1/income",
        headers=headers,
        json={"amount": "5000", "category": "salary", "date": "2022-03-15", "currency": "TRY"},
    )
    await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={"amount": "1200", "category": "bills", "date": "2022-03-20", "currency": "TRY"},
    )
    resp = await client.get("/api/v1/cash-flow?year=2022", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    mar = next(m for m in data["months"] if m["month"] == 3)
    assert mar["is_past"] is True
    assert Decimal(str(mar["income_actual"])) == Decimal("5000")
    assert Decimal(str(mar["expense_actual"])) == Decimal("1200")
    # Geçmiş ay forecast 0 (yanıltıcı olmasın)
    assert Decimal(str(mar["income_forecast"])) == Decimal("0")
    # Yıl toplamı en az bu ay tutarlarını içerir
    assert Decimal(str(data["total_income"])) >= Decimal("5000")
    assert Decimal(str(data["total_expense"])) >= Decimal("1200")


@pytest.mark.asyncio
async def test_cash_flow_future_forecast_from_recurring(client):
    """Gelecek yıl → recurring income forecast olarak income_forecast'a girer."""
    headers = await make_user(client)
    await client.post(
        "/api/v1/income/recurring",
        headers=headers,
        json={
            "title": "Maaş",
            "amount": "8000",
            "category": "salary",
            "recurrence": "monthly",
            "start_date": "2030-01-01",
            "currency": "TRY",
        },
    )
    resp = await client.get("/api/v1/cash-flow?year=2030", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    jan = next(m for m in data["months"] if m["month"] == 1)
    assert jan["is_past"] is False
    assert Decimal(str(jan["income_forecast"])) == Decimal("8000")


# ===========================================================================
# auth koruması
# ===========================================================================
@pytest.mark.asyncio
async def test_income_summary_requires_auth(client):
    """Auth header olmadan → 401."""
    resp = await client.get("/api/v1/income/summary?year=2026&month=1")
    assert resp.status_code == 401
