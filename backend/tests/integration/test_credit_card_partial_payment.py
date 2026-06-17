"""Kredi kartı ekstresi kısmi ödeme + taksit reconciliation testleri."""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user


async def _make_card(client: AsyncClient, headers: dict, name: str = "VakifBank") -> int:
    resp = await client.post("/api/v1/credit-cards", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _make_statement(client, headers, cid, *, year, month, amount, due) -> int:
    resp = await client.post(
        f"/api/v1/credit-cards/{cid}/statements",
        json={
            "period_year": year,
            "period_month": month,
            "statement_amount": str(amount),
            "statement_date": due,
            "due_date": due,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ─── Kısmi ödeme ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_partial_payment_carries_remainder(client: AsyncClient):
    headers = await make_user(client, "cc_partial@example.com")
    cid = await _make_card(client, headers)
    sid = await _make_statement(client, headers, cid, year=2026, month=5, amount=1000, due="2026-05-25")

    pay = await client.post(
        f"/api/v1/credit-cards/{cid}/statements/{sid}/pay",
        json={"paid_amount": "300"},
        headers=headers,
    )
    assert pay.status_code == 200, pay.text
    assert pay.json()["paid_at"] is not None
    assert float(pay.json()["paid_amount"]) == 300.0
    # Kalan 700 → kartın dönem-içi borcuna taşınmalı
    card = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers)
    assert float(card.json()["card"]["current_period_debt"]) == 700.0


@pytest.mark.asyncio
async def test_full_payment_no_carry(client: AsyncClient):
    headers = await make_user(client, "cc_full@example.com")
    cid = await _make_card(client, headers)
    sid = await _make_statement(client, headers, cid, year=2026, month=5, amount=1000, due="2026-05-25")
    pay = await client.post(
        f"/api/v1/credit-cards/{cid}/statements/{sid}/pay",
        json={"paid_amount": "1000"},
        headers=headers,
    )
    assert pay.status_code == 200
    card = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers)
    assert float(card.json()["card"]["current_period_debt"]) == 0.0


@pytest.mark.asyncio
async def test_double_pay_no_double_carry(client: AsyncClient):
    headers = await make_user(client, "cc_double@example.com")
    cid = await _make_card(client, headers)
    sid = await _make_statement(client, headers, cid, year=2026, month=5, amount=1000, due="2026-05-25")
    body = {"paid_amount": "400"}
    await client.post(f"/api/v1/credit-cards/{cid}/statements/{sid}/pay", json=body, headers=headers)
    await client.post(f"/api/v1/credit-cards/{cid}/statements/{sid}/pay", json=body, headers=headers)
    card = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers)
    assert float(card.json()["card"]["current_period_debt"]) == 600.0  # 600 değil 1200


@pytest.mark.asyncio
async def test_overpay_422(client: AsyncClient):
    headers = await make_user(client, "cc_over@example.com")
    cid = await _make_card(client, headers)
    sid = await _make_statement(client, headers, cid, year=2026, month=5, amount=1000, due="2026-05-25")
    resp = await client.post(
        f"/api/v1/credit-cards/{cid}/statements/{sid}/pay",
        json={"paid_amount": "1500"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_partial_cashflow_counts_only_paid(client: AsyncClient):
    """Kısmi ödenen ekstre nakit-akışında o ay yalnız ödeneni sayar."""
    headers = await make_user(client, "cc_cf@example.com")
    cid = await _make_card(client, headers)
    sid = await _make_statement(client, headers, cid, year=2026, month=5, amount=1000, due="2026-05-25")
    await client.post(
        f"/api/v1/credit-cards/{cid}/statements/{sid}/pay",
        json={"paid_amount": "300"},
        headers=headers,
    )
    detail = await client.get("/api/v1/cash-flow/2026/5/detail", headers=headers)
    assert detail.status_code == 200
    stmt_items = [i for i in detail.json()["expense_items"] if i["category"] == "statement"]
    assert len(stmt_items) == 1
    assert float(stmt_items[0]["amount_tl"]) == 300.0  # 1000 değil


# ─── Taksit reconciliation ───────────────────────────────────────────────────


async def _make_installment(client, headers, cid, *, desc, monthly, total, first_due) -> dict:
    resp = await client.post(
        f"/api/v1/credit-cards/{cid}/installments",
        json={
            "description": desc,
            "monthly_amount": str(monthly),
            "installments_total": total,
            "first_due_date": first_due,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_reconcile_advances_installment(client: AsyncClient):
    """Ekstre dönemine kadarki dilimler kapsanır → taksit ilerletilir."""
    headers = await make_user(client, "cc_recon@example.com")
    cid = await _make_card(client, headers)
    # Gelecek başlangıçlı taksit (remaining = total)
    await _make_installment(client, headers, cid, desc="Buzdolabi", monthly=1000, total=6, first_due="2027-01-01")
    # Mart 2027 ekstresi → 3 dilim kapsanır (Oca/Şub/Mar)
    await _make_statement(client, headers, cid, year=2027, month=3, amount=5000, due="2027-03-25")
    detail = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers)
    insts = detail.json()["installments"]
    assert len(insts) == 1
    assert insts[0]["installments_remaining"] == 3
    assert insts[0]["first_due_date"] == "2027-04-01"


@pytest.mark.asyncio
async def test_reconcile_deletes_completed_installment(client: AsyncClient):
    """Tüm dilimleri ekstreye düşen (stale) taksit silinir — '439' senaryosu."""
    headers = await make_user(client, "cc_recon_del@example.com")
    cid = await _make_card(client, headers)
    await _make_installment(client, headers, cid, desc="HEPSIPAY", monthly=439, total=3, first_due="2027-01-01")
    # Mart 2027 ekstresi → 3 dilim de kapsanır → silinmeli
    await _make_statement(client, headers, cid, year=2027, month=3, amount=2000, due="2027-03-25")
    detail = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers)
    assert detail.json()["installments"] == []


@pytest.mark.asyncio
async def test_reconcile_leaves_future_installment(client: AsyncClient):
    """Tüm dilimleri ekstre döneminden SONRA olan taksite dokunulmaz."""
    headers = await make_user(client, "cc_recon_fut@example.com")
    cid = await _make_card(client, headers)
    await _make_installment(client, headers, cid, desc="Gelecek", monthly=500, total=4, first_due="2027-06-01")
    # Mart 2027 ekstresi → Haziran'dan önce → dokunma
    await _make_statement(client, headers, cid, year=2027, month=3, amount=1000, due="2027-03-25")
    detail = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers)
    insts = detail.json()["installments"]
    assert len(insts) == 1
    assert insts[0]["installments_remaining"] == 4
    assert insts[0]["first_due_date"] == "2027-06-01"
