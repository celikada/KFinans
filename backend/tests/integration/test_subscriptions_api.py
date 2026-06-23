"""Abonelik (fatura/utility) API testleri.

Yaşam döngüsü budget → issued → paid; ödeme şekli çift sayım (kart hariç, nakit dahil);
cash_flow forecast entegrasyonu; hatırlatma; IDOR.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


# /subscriptions/reminders endpoint'i "bugün"ü Europe/Istanbul ile hesaplar
# (days_until_due). Container UTC'de koştuğu için gece yarısı civarı UTC date.today()
# ile server tarihi 1 gün kayabilir → tarih-bağımlı testlerde aynı tz kullan.
def _ist_today() -> date:
    return datetime.now(ZoneInfo("Europe/Istanbul")).date()


def _sub_payload(
    provider_code: str = "esgaz",
    subscriber_no: str = "123456",
    budget_amount: float = 500.0,
    billing_day: int | None = None,
    **extra,
) -> dict:
    payload: dict = {
        "provider_code": provider_code,
        "subscriber_no": subscriber_no,
        "budget_amount": budget_amount,
    }
    if billing_day is not None:
        payload["billing_day"] = billing_day
    payload.update(extra)
    return payload


async def _create_sub(client: AsyncClient, headers: dict, **kw) -> dict:
    resp = await client.post("/api/v1/subscriptions", json=_sub_payload(**kw), headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ─── Katalog + CRUD ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_providers_catalog(client: AsyncClient):
    headers = await make_user(client, "sub_prov@example.com")
    resp = await client.get("/api/v1/subscriptions/providers", headers=headers)
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()}
    # zorlu_enerji + osmangazi_elektrik aynı kurum → tek girişe indirildi (2026-06-23)
    assert codes == {"esgaz", "osmangazi_elektrik", "ttnet", "vodafone"}


@pytest.mark.asyncio
async def test_create_derives_category_and_status(client: AsyncClient):
    headers = await make_user(client, "sub_create@example.com")
    sub = await _create_sub(client, headers, provider_code="osmangazi_elektrik", budget_amount=750)
    assert sub["category"] == "electricity"
    assert sub["provider_name"] == "Osmangazi Elektrik (Zorlu Enerji)"
    assert sub["current_status"] == "budget"
    assert float(sub["current_amount"]) == 750.0


@pytest.mark.asyncio
async def test_unknown_provider_422(client: AsyncClient):
    headers = await make_user(client, "sub_unknown@example.com")
    resp = await client.post("/api/v1/subscriptions", json=_sub_payload(provider_code="iski"), headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_and_delete(client: AsyncClient):
    headers = await make_user(client, "sub_upd@example.com")
    sub = await _create_sub(client, headers)
    upd = await client.put(
        f"/api/v1/subscriptions/{sub['id']}",
        json={"budget_amount": 999, "label": "Ev"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert float(upd.json()["budget_amount"]) == 999.0
    assert upd.json()["label"] == "Ev"
    dele = await client.delete(f"/api/v1/subscriptions/{sub['id']}", headers=headers)
    assert dele.status_code == 204
    lst = await client.get("/api/v1/subscriptions", headers=headers)
    assert lst.json() == []


# ─── Lifecycle: budget → issued → paid ───────────────────────────────────────


def _this_month() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month


@pytest.mark.asyncio
async def test_issue_then_status_issued(client: AsyncClient):
    headers = await make_user(client, "sub_issue@example.com")
    sub = await _create_sub(client, headers, budget_amount=500)
    year, month = _this_month()
    resp = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": 620,
            "bill_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=10)).isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "issued"
    assert float(resp.json()["bill_amount"]) == 620.0
    # Liste artık issued + bill_amount göstermeli
    lst = await client.get("/api/v1/subscriptions", headers=headers)
    row = lst.json()[0]
    assert row["current_status"] == "issued"
    assert float(row["current_amount"]) == 620.0


@pytest.mark.asyncio
async def test_pay_cash_counts_in_expense_total(client: AsyncClient):
    """Nakit ödeme → gerçek Expense + gider toplamına dahil."""
    headers = await make_user(client, "sub_paycash@example.com")
    sub = await _create_sub(client, headers, budget_amount=500)
    year, month = _this_month()
    issue = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": 620,
            "bill_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=5)).isoformat(),
        },
        headers=headers,
    )
    bill_id = issue.json()["id"]
    pay = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "cash"},
        headers=headers,
    )
    assert pay.status_code == 200, pay.text
    assert pay.json()["status"] == "paid"
    # Gider özetine girmeli (nakit)
    summ = await client.get(f"/api/v1/expenses/summary?year={year}&month={month}", headers=headers)
    assert summ.status_code == 200
    assert float(summ.json()["total"]) == 620.0
    assert summ.json()["count"] == 1


@pytest.mark.asyncio
async def test_pay_credit_card_excluded_from_total(client: AsyncClient):
    """Kredi kartıyla ödeme → Expense.credit_card_id set → gider toplamından HARİÇ (çift sayım)."""
    headers = await make_user(client, "sub_paycc@example.com")
    # Önce kart oluştur
    card = await client.post(
        "/api/v1/credit-cards",
        json={"name": "Bonus", "statement_day": 1, "payment_due_day": 10},
        headers=headers,
    )
    card_id = card.json()["id"]
    sub = await _create_sub(client, headers, budget_amount=500)
    year, month = _this_month()
    issue = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": 800,
            "bill_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=5)).isoformat(),
        },
        headers=headers,
    )
    bill_id = issue.json()["id"]
    pay = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "credit_card", "credit_card_id": card_id},
        headers=headers,
    )
    assert pay.status_code == 200, pay.text
    # Gider özeti: kart+ödendi çift sayım filtresi nedeniyle HARİÇ
    summ = await client.get(f"/api/v1/expenses/summary?year={year}&month={month}", headers=headers)
    assert float(summ.json()["total"]) == 0.0


@pytest.mark.asyncio
async def test_pay_credit_card_sets_subscription_default(client: AsyncClient):
    """Kredi kartıyla ödeme → aboneliğin default_payment_method/default_credit_card_id'si
    set edilir (sonraki ödemede ön-seçili gelsin)."""
    headers = await make_user(client, "sub_default_cc@example.com")
    card = await client.post(
        "/api/v1/credit-cards",
        json={"name": "Bonus", "statement_day": 1, "payment_due_day": 10},
        headers=headers,
    )
    card_id = card.json()["id"]
    sub = await _create_sub(client, headers, budget_amount=500)
    year, month = _this_month()
    issue = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": 800,
            "bill_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=5)).isoformat(),
        },
        headers=headers,
    )
    bill_id = issue.json()["id"]
    pay = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "credit_card", "credit_card_id": card_id},
        headers=headers,
    )
    assert pay.status_code == 200, pay.text
    # Abonelik artık bu kartı varsayılan tutmalı (sonraki ödemede ön-seçili)
    lst = await client.get("/api/v1/subscriptions", headers=headers)
    row = next(s for s in lst.json() if s["id"] == sub["id"])
    assert row["default_payment_method"] == "credit_card"
    assert row["default_credit_card_id"] == card_id


@pytest.mark.asyncio
async def test_pay_credit_card_requires_card(client: AsyncClient):
    headers = await make_user(client, "sub_paynocard@example.com")
    sub = await _create_sub(client, headers)
    year, month = _this_month()
    issue = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": 100,
            "bill_date": date.today().isoformat(),
            "due_date": date.today().isoformat(),
        },
        headers=headers,
    )
    bill_id = issue.json()["id"]
    resp = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "credit_card"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unpay_removes_expense(client: AsyncClient):
    headers = await make_user(client, "sub_unpay@example.com")
    sub = await _create_sub(client, headers)
    year, month = _this_month()
    issue = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": 300,
            "bill_date": date.today().isoformat(),
            "due_date": date.today().isoformat(),
        },
        headers=headers,
    )
    bill_id = issue.json()["id"]
    await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "cash"},
        headers=headers,
    )
    unpay = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/unpay",
        headers=headers,
    )
    assert unpay.status_code == 200
    assert unpay.json()["status"] == "issued"
    # Expense silinmiş → gider toplamı 0
    summ = await client.get(f"/api/v1/expenses/summary?year={year}&month={month}", headers=headers)
    assert float(summ.json()["total"]) == 0.0


# ─── Cash flow forecast ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cash_flow_includes_subscription_forecast(client: AsyncClient):
    """Budget abonelik → cash_flow bu ay expense_forecast'ına eklenmeli."""
    headers = await make_user(client, "sub_cf@example.com")
    await _create_sub(client, headers, budget_amount=400)
    year, month = _this_month()
    cf = await client.get(f"/api/v1/cash-flow?year={year}", headers=headers)
    assert cf.status_code == 200
    this_month = next(m for m in cf.json()["months"] if m["month"] == month)
    assert float(this_month["expense_forecast"]) >= 400.0


@pytest.mark.asyncio
async def test_cash_flow_paid_not_double_counted(client: AsyncClient):
    """Nakit ödenmiş abonelik → actual'da (1×), forecast'tan düşer (çift sayım yok)."""
    headers = await make_user(client, "sub_cf_paid@example.com")
    sub = await _create_sub(client, headers, budget_amount=400)
    year, month = _this_month()
    issue = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": 400,
            "bill_date": date.today().isoformat(),
            "due_date": date.today().isoformat(),
        },
        headers=headers,
    )
    bill_id = issue.json()["id"]
    await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "cash"},
        headers=headers,
    )
    cf = await client.get(f"/api/v1/cash-flow?year={year}", headers=headers)
    this_month = next(m for m in cf.json()["months"] if m["month"] == month)
    # actual'da 400, forecast'ta 0 (paid → forecast'a girmez)
    assert float(this_month["expense_actual"]) == 400.0
    assert float(this_month["expense_forecast"]) == 0.0


# ─── Özet + hatırlatma ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_this_month_and_remaining(client: AsyncClient):
    headers = await make_user(client, "sub_summary@example.com")
    await _create_sub(client, headers, budget_amount=500)
    summ = await client.get("/api/v1/subscriptions/summary", headers=headers)
    assert summ.status_code == 200
    body = summ.json()
    assert body["active_count"] == 1
    assert float(body["this_month_estimate"]) == 500.0
    # Kalan yıl = bu ay dahil kalan aylar × 500 ≥ bu ay
    assert float(body["remaining_year_estimate"]) >= 500.0


@pytest.mark.asyncio
async def test_reminders_due_payment(client: AsyncClient):
    headers = await make_user(client, "sub_rem@example.com")
    sub = await _create_sub(client, headers)
    year, month = _this_month()
    await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": 250,
            "bill_date": _ist_today().isoformat(),
            "due_date": (_ist_today() + timedelta(days=2)).isoformat(),
        },
        headers=headers,
    )
    rem = await client.get("/api/v1/subscriptions/reminders", headers=headers)
    assert rem.status_code == 200
    assert len(rem.json()["due_payments"]) == 1
    assert rem.json()["due_payments"][0]["days_until_due"] == 2


# ─── IDOR ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_idor_other_user_404(client: AsyncClient):
    h1 = await make_user(client, "sub_owner@example.com")
    h2 = await make_user(client, "sub_attacker@example.com")
    sub = await _create_sub(client, h1)
    resp = await client.get(f"/api/v1/subscriptions/{sub['id']}/bills", headers=h2)
    assert resp.status_code == 404
    upd = await client.put(f"/api/v1/subscriptions/{sub['id']}", json={"budget_amount": 1}, headers=h2)
    assert upd.status_code == 404


# ─── Ek error-path / kapsam ──────────────────────────────────────────────────


async def _issue_current(client: AsyncClient, headers: dict, sub_id: int, amount: float = 200.0) -> int:
    year, month = _this_month()
    resp = await client.post(
        f"/api/v1/subscriptions/{sub_id}/bills/issue",
        json={
            "period_year": year,
            "period_month": month,
            "bill_amount": amount,
            "bill_date": date.today().isoformat(),
            "due_date": date.today().isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_delete_bill_issued_to_budget(client: AsyncClient):
    headers = await make_user(client, "sub_delbill@example.com")
    sub = await _create_sub(client, headers, budget_amount=300)
    bill_id = await _issue_current(client, headers, sub["id"])
    dele = await client.delete(f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}", headers=headers)
    assert dele.status_code == 204
    # Dönem implicit budget'a döner: liste current_status budget
    lst = await client.get("/api/v1/subscriptions", headers=headers)
    assert lst.json()[0]["current_status"] == "budget"


@pytest.mark.asyncio
async def test_delete_paid_bill_conflict(client: AsyncClient):
    headers = await make_user(client, "sub_delpaid@example.com")
    sub = await _create_sub(client, headers)
    bill_id = await _issue_current(client, headers, sub["id"])
    await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "cash"},
        headers=headers,
    )
    dele = await client.delete(f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}", headers=headers)
    assert dele.status_code == 409


@pytest.mark.asyncio
async def test_pay_already_paid_conflict(client: AsyncClient):
    headers = await make_user(client, "sub_doublepay@example.com")
    sub = await _create_sub(client, headers)
    bill_id = await _issue_current(client, headers, sub["id"])
    await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "cash"},
        headers=headers,
    )
    again = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "cash"},
        headers=headers,
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_pay_with_other_users_card_404(client: AsyncClient):
    h1 = await make_user(client, "sub_cardowner@example.com")
    h2 = await make_user(client, "sub_cardthief@example.com")
    # h2'nin kartı
    card = await client.post(
        "/api/v1/credit-cards",
        json={"name": "Other", "statement_day": 1, "payment_due_day": 10},
        headers=h2,
    )
    other_card_id = card.json()["id"]
    sub = await _create_sub(client, h1)
    bill_id = await _issue_current(client, h1, sub["id"])
    resp = await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/{bill_id}/pay",
        json={"payment_method": "credit_card", "credit_card_id": other_card_id},
        headers=h1,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_bills_periods(client: AsyncClient):
    headers = await make_user(client, "sub_periods@example.com")
    sub = await _create_sub(client, headers, budget_amount=150)
    # Geçmiş dönem issued
    await client.post(
        f"/api/v1/subscriptions/{sub['id']}/bills/issue",
        json={
            "period_year": 2025,
            "period_month": 3,
            "bill_amount": 180,
            "bill_date": "2025-03-10",
            "due_date": "2025-03-20",
        },
        headers=headers,
    )
    bills = await client.get(f"/api/v1/subscriptions/{sub['id']}/bills", headers=headers)
    assert bills.status_code == 200
    statuses = {b["status"] for b in bills.json()}
    # Sentezlenmiş bu-ay budget + geçmiş issued
    assert "budget" in statuses
    assert "issued" in statuses


@pytest.mark.asyncio
async def test_update_provider_rederives_category(client: AsyncClient):
    headers = await make_user(client, "sub_provchange@example.com")
    sub = await _create_sub(client, headers, provider_code="esgaz")  # gas
    upd = await client.put(
        f"/api/v1/subscriptions/{sub['id']}",
        json={"provider_code": "ttnet"},  # internet
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["category"] == "internet"
    assert upd.json()["provider_name"] == "TTNET"


@pytest.mark.asyncio
async def test_update_unknown_provider_422(client: AsyncClient):
    headers = await make_user(client, "sub_updbad@example.com")
    sub = await _create_sub(client, headers)
    upd = await client.put(
        f"/api/v1/subscriptions/{sub['id']}",
        json={"provider_code": "bogusco"},
        headers=headers,
    )
    assert upd.status_code == 422


@pytest.mark.asyncio
async def test_summary_display_currency(client: AsyncClient):
    headers = await make_user(client, "sub_dispccy@example.com")
    await _create_sub(client, headers, budget_amount=600, currency="TRY")
    resp = await client.get("/api/v1/subscriptions/summary?display=USD", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["display_currency"] == "USD"


@pytest.mark.asyncio
async def test_reminders_pending_bill(client: AsyncClient):
    headers = await make_user(client, "sub_pending@example.com")
    # billing_day=1 → bugün >= 1, bu ay fatura yok → pending_bills'e düşer
    await _create_sub(client, headers, billing_day=1)
    rem = await client.get("/api/v1/subscriptions/reminders", headers=headers)
    assert rem.status_code == 200
    assert len(rem.json()["pending_bills"]) == 1


@pytest.mark.asyncio
async def test_start_date_create_and_out(client: AsyncClient):
    headers = await make_user(client, "sub_start@example.com")
    sub = await _create_sub(client, headers, start_date="2026-03-01")
    assert sub["start_date"] == "2026-03-01"


@pytest.mark.asyncio
async def test_start_date_future_excludes_from_cashflow(client: AsyncClient):
    """Başlangıcı gelecekte olan abonelik bütçesi bu ay forecast'a girmez."""
    headers = await make_user(client, "sub_startfut@example.com")
    year, month = _this_month()
    # Başlangıç = gelecek yıl → bu yılın hiçbir ayında forecast yok
    await _create_sub(client, headers, budget_amount=400, start_date=f"{year + 1}-01-01")
    cf = await client.get(f"/api/v1/cash-flow?year={year}", headers=headers)
    this_month = next(m for m in cf.json()["months"] if m["month"] == month)
    # Abonelik forecast'a katkı yok (başlangıçtan önce)
    assert float(this_month["expense_forecast"]) == 0.0


@pytest.mark.asyncio
async def test_delete_subscription_cascades_bills(client: AsyncClient):
    headers = await make_user(client, "sub_cascade@example.com")
    sub = await _create_sub(client, headers)
    await _issue_current(client, headers, sub["id"])
    dele = await client.delete(f"/api/v1/subscriptions/{sub['id']}", headers=headers)
    assert dele.status_code == 204
    # Bills de gitmiş olmalı (404 abonelik)
    bills = await client.get(f"/api/v1/subscriptions/{sub['id']}/bills", headers=headers)
    assert bills.status_code == 404
