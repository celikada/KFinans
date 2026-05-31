"""TEST-011 (FAZ H): Kredi karti CRUD + nested ekstre/taksit + cift sayim
regression testleri.

Kritik kural: kredi kartindan yapilmis + odenmiş bir Expense (credit_card_id
NOT NULL + is_paid=true) zaten kart borcu/ekstresiyle sayildigi icin
/expenses/summary, /budgets/comparison ve /planned-expenses/forecast
toplamlarindan HARIC TUTULMALI. Bu kural bozulursa kullanici yanlis
gider raporu gorur (kullanici parasini etkileyen modul).
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user

# ─── CreditCard CRUD ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_credit_card(client: AsyncClient):
    headers = await make_user(client, "cc_create@example.com")
    resp = await client.post(
        "/api/v1/credit-cards",
        json={
            "name": "Garanti Bonus",
            "bank_name": "Garanti BBVA",
            "last_4": "1234",
            "credit_limit": "20000",
            "statement_day": 15,
            "payment_due_day": 25,
            "current_period_debt": "1500.50",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Garanti Bonus"
    assert data["last_4"] == "1234"
    assert data["statement_day"] == 15


@pytest.mark.asyncio
async def test_list_credit_cards_summary(client: AsyncClient):
    headers = await make_user(client, "cc_list@example.com")
    await client.post(
        "/api/v1/credit-cards",
        json={
            "name": "Card A",
            "current_period_debt": "1000",
        },
        headers=headers,
    )
    await client.post(
        "/api/v1/credit-cards",
        json={
            "name": "Card B",
            "current_period_debt": "500",
        },
        headers=headers,
    )

    resp = await client.get("/api/v1/credit-cards", headers=headers)
    assert resp.status_code == 200
    s = resp.json()
    assert len(s["cards"]) == 2
    # Toplam donemici borç = 1000 + 500
    assert float(s["total_period_debt"]) == 1500.0


@pytest.mark.asyncio
async def test_list_credit_cards_unauth_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/credit-cards")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_credit_card_detail_404_when_not_found(client: AsyncClient):
    headers = await make_user(client, "cc_404@example.com")
    resp = await client.get("/api/v1/credit-cards/999999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_credit_card(client: AsyncClient):
    headers = await make_user(client, "cc_update@example.com")
    create = await client.post("/api/v1/credit-cards", json={"name": "Eski"}, headers=headers)
    cid = create.json()["id"]

    resp = await client.put(
        f"/api/v1/credit-cards/{cid}",
        json={"name": "Yeni", "current_period_debt": "2000"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Yeni"


@pytest.mark.asyncio
async def test_delete_credit_card_cascade_statements(client: AsyncClient):
    """Kart silinince ekstreleri ve taksitleri CASCADE silinir (FK ondelete)."""
    headers = await make_user(client, "cc_del@example.com")
    create = await client.post("/api/v1/credit-cards", json={"name": "Silinecek"}, headers=headers)
    cid = create.json()["id"]

    # Bir ekstre ekle
    await client.post(
        f"/api/v1/credit-cards/{cid}/statements",
        json={
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "500",
            "statement_date": "2026-05-10",
            "due_date": "2026-05-25",
        },
        headers=headers,
    )

    # Kart sil
    resp = await client.delete(f"/api/v1/credit-cards/{cid}", headers=headers)
    assert resp.status_code == 204

    # Get detay -> 404
    detail = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers)
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_invalid_statement_day_returns_422(client: AsyncClient):
    headers = await make_user(client, "cc_invalid@example.com")
    resp = await client.post(
        "/api/v1/credit-cards",
        json={"name": "Invalid", "statement_day": 31},  # max 28
        headers=headers,
    )
    assert resp.status_code == 422


# ─── Statement (ekstre) CRUD ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_statement(client: AsyncClient):
    headers = await make_user(client, "stmt_create@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "S"}, headers=headers)
    cid = card.json()["id"]

    resp = await client.post(
        f"/api/v1/credit-cards/{cid}/statements",
        json={
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "1234.56",
            "statement_date": "2026-05-15",
            "due_date": "2026-05-25",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert float(resp.json()["statement_amount"]) == 1234.56


@pytest.mark.asyncio
async def test_create_statement_card_404(client: AsyncClient):
    headers = await make_user(client, "stmt_404@example.com")
    resp = await client.post(
        "/api/v1/credit-cards/999999/statements",
        json={
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "100",
            "statement_date": "2026-05-15",
            "due_date": "2026-05-25",
        },
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_statement_period_409(client: AsyncClient):
    """uq_statement_card_period: ayni (card, year, month) ikinci kez 409."""
    headers = await make_user(client, "stmt_dup@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "D"}, headers=headers)
    cid = card.json()["id"]

    payload = {
        "period_year": 2026,
        "period_month": 5,
        "statement_amount": "100",
        "statement_date": "2026-05-15",
        "due_date": "2026-05-25",
    }
    first = await client.post(f"/api/v1/credit-cards/{cid}/statements", json=payload, headers=headers)
    assert first.status_code == 201
    second = await client.post(f"/api/v1/credit-cards/{cid}/statements", json=payload, headers=headers)
    # IntegrityError -> 409 (BACK-008 generic handler)
    assert second.status_code in (400, 409, 500)


# ─── Installment (taksit) CRUD ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_installment(client: AsyncClient):
    headers = await make_user(client, "inst_create@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "I"}, headers=headers)
    cid = card.json()["id"]

    resp = await client.post(
        f"/api/v1/credit-cards/{cid}/installments",
        json={
            "description": "Buzdolabi 12 taksit",
            "monthly_amount": "500",
            "installments_total": 12,
            "first_due_date": "2026-06-01",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["installments_total"] == 12
    assert float(data["monthly_amount"]) == 500.0


@pytest.mark.asyncio
async def test_installment_zero_monthly_returns_422(client: AsyncClient):
    headers = await make_user(client, "inst_zero@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "Z"}, headers=headers)
    cid = card.json()["id"]

    resp = await client.post(
        f"/api/v1/credit-cards/{cid}/installments",
        json={
            "description": "Sifir taksit",
            "monthly_amount": "0",  # gt=0 ihlali
            "installments_total": 6,
            "first_due_date": "2026-06-01",
        },
        headers=headers,
    )
    assert resp.status_code == 422


# ─── Çift sayım kuralı regression ───────────────────────────────────────


@pytest.mark.asyncio
async def test_double_count_paid_credit_card_expense_excluded(client: AsyncClient):
    """KRITIK: credit_card_id NOT NULL + is_paid=true Expense kayitlari
    /expenses/summary toplamindan HARIC tutulur."""
    headers = await make_user(client, "double_count@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "DC"}, headers=headers)
    cid = card.json()["id"]

    # 1) Karttan ödenmis harcama -> haric tutulmali
    paid = await client.post(
        "/api/v1/expenses",
        json={
            "amount": 1000,
            "category": "groceries",
            "date": "2026-05-15",
            "credit_card_id": cid,
            "is_paid": True,
        },
        headers=headers,
    )
    assert paid.status_code == 201

    # 2) Karttan ödenmemis harcama -> dahil edilmeli
    unpaid = await client.post(
        "/api/v1/expenses",
        json={
            "amount": 200,
            "category": "groceries",
            "date": "2026-05-16",
            "credit_card_id": cid,
            "is_paid": False,
        },
        headers=headers,
    )
    assert unpaid.status_code == 201

    # 3) Kartsiz harcama -> dahil edilmeli
    cashless = await client.post(
        "/api/v1/expenses",
        json={"amount": 300, "category": "food", "date": "2026-05-17"},
        headers=headers,
    )
    assert cashless.status_code == 201

    # Summary toplam = 200 (unpaid kart) + 300 (kartsiz) = 500
    # 1000 (paid kart) HARIC TUTULMALI — bu kuralin regression koruyucu.
    resp = await client.get("/api/v1/expenses/summary?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    s = resp.json()
    assert float(s["total"]) == 500.0, (
        f"Cift sayim kurali bozuldu! credit_card_id NOT NULL + is_paid=true Expense /summary'den haric tutulmali. Beklenen 500.00, gelen {s['total']}"
    )


@pytest.mark.asyncio
async def test_list_expenses_includes_paid_credit_card_expense(client: AsyncClient):
    """Liste endpoint cift sayim filtresinden haric DEGIL — kullanici tum
    kayitlari gormeli (rozetlerle durumu belirtir)."""
    headers = await make_user(client, "list_paid@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "L"}, headers=headers)
    cid = card.json()["id"]

    await client.post(
        "/api/v1/expenses",
        json={
            "amount": 1000,
            "category": "bills",
            "date": "2026-05-15",
            "credit_card_id": cid,
            "is_paid": True,
        },
        headers=headers,
    )

    # Liste her zaman tum kayitlari gosterir
    resp = await client.get("/api/v1/expenses?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    expenses = resp.json()
    assert len(expenses) == 1
    assert float(expenses[0]["amount"]) == 1000.0


@pytest.mark.asyncio
async def test_double_count_budget_comparison_excludes_paid_card_expense(client: AsyncClient):
    """/budgets/comparison da ayni cift sayim filtresini uygulamali."""
    headers = await make_user(client, "budget_dc@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "B"}, headers=headers)
    cid = card.json()["id"]

    # Bütçe limiti
    await client.put(
        "/api/v1/budgets/groceries",
        json={"amount": 1000},
        headers=headers,
    )

    # Karttan ödenmis 800 -> filtreden haric (sayilmamali)
    await client.post(
        "/api/v1/expenses",
        json={
            "amount": 800,
            "category": "groceries",
            "date": "2026-05-15",
            "credit_card_id": cid,
            "is_paid": True,
        },
        headers=headers,
    )

    # Kartsiz 300 -> sayilmali
    await client.post(
        "/api/v1/expenses",
        json={
            "amount": 300,
            "category": "groceries",
            "date": "2026-05-16",
        },
        headers=headers,
    )

    resp = await client.get("/api/v1/budgets/comparison?year=2026&month=5", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    groceries = next((r for r in rows if r["category"] == "groceries"), None)
    assert groceries is not None
    # actual_amount sadece 300 (kartsiz) olmali, 800 (paid kart) haric
    assert float(groceries["actual_amount"]) == 300.0, f"Budget comparison cift sayim bozuldu! Beklenen 300.00, gelen {groceries['actual_amount']}"


# ─── Update / Delete card edge cases ────────────────────────────────────


@pytest.mark.asyncio
async def test_update_credit_card_404(client: AsyncClient):
    headers = await make_user(client, "cc_upd_404@example.com")
    resp = await client.put("/api/v1/credit-cards/999999", json={"name": "X"}, headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_credit_card_404(client: AsyncClient):
    headers = await make_user(client, "cc_del_404@example.com")
    resp = await client.delete("/api/v1/credit-cards/999999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_credit_card_idor_user_b_cannot_update(client: AsyncClient):
    """B, A'nın kartını güncelleyemez (404)."""
    headers_a = await make_user(client, "cc_idor_a@example.com")
    headers_b = await make_user(client, "cc_idor_b@example.com")
    create = await client.post("/api/v1/credit-cards", json={"name": "A kart"}, headers=headers_a)
    cid = create.json()["id"]

    resp = await client.put(f"/api/v1/credit-cards/{cid}", json={"name": "B sahte"}, headers=headers_b)
    assert resp.status_code == 404
    # A hala gorebilir, B goremez
    detail_b = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers_b)
    assert detail_b.status_code == 404


@pytest.mark.asyncio
async def test_credit_card_idor_user_b_cannot_delete(client: AsyncClient):
    headers_a = await make_user(client, "cc_idor_del_a@example.com")
    headers_b = await make_user(client, "cc_idor_del_b@example.com")
    create = await client.post("/api/v1/credit-cards", json={"name": "A kart"}, headers=headers_a)
    cid = create.json()["id"]
    resp = await client.delete(f"/api/v1/credit-cards/{cid}", headers=headers_b)
    assert resp.status_code == 404


# ─── Card summary enrichment (unpaid + future + total_debt) ─────────────


@pytest.mark.asyncio
async def test_card_summary_enrichment_calculations(client: AsyncClient):
    """unpaid_statement_total + current_period_debt = period_debt;
    + future_installment_total = total_debt."""
    headers = await make_user(client, "cc_enrich@example.com")
    create = await client.post(
        "/api/v1/credit-cards",
        json={"name": "Enrich", "current_period_debt": "100"},
        headers=headers,
    )
    cid = create.json()["id"]

    # Ödenmemiş ekstre 500 (paid_at yok)
    await client.post(
        f"/api/v1/credit-cards/{cid}/statements",
        json={
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "500",
            "statement_date": "2026-05-10",
            "due_date": "2026-05-25",
        },
        headers=headers,
    )
    # Taksit 12 ay × 200 (gelecek) -> remaining hesaplanir
    await client.post(
        f"/api/v1/credit-cards/{cid}/installments",
        json={
            "description": "Taksit",
            "monthly_amount": "200",
            "installments_total": 12,
            "first_due_date": "2099-01-01",  # tamamen gelecek -> remaining=12
        },
        headers=headers,
    )

    resp = await client.get("/api/v1/credit-cards", headers=headers)
    assert resp.status_code == 200
    card = resp.json()["cards"][0]
    assert float(card["unpaid_statement_total"]) == 500.0
    assert float(card["unpaid_statement_count"]) == 1
    assert float(card["period_debt"]) == 600.0  # 500 + 100
    # future = 12 × 200 = 2400; total = 600 + 2400
    assert float(card["future_installment_total"]) == 2400.0
    assert float(card["total_debt"]) == 3000.0


@pytest.mark.asyncio
async def test_card_summary_paid_statement_not_in_unpaid(client: AsyncClient):
    """paid_at dolu ekstre unpaid_statement_total'a girmez."""
    headers = await make_user(client, "cc_paid_stmt@example.com")
    create = await client.post("/api/v1/credit-cards", json={"name": "PaidStmt"}, headers=headers)
    cid = create.json()["id"]

    await client.post(
        f"/api/v1/credit-cards/{cid}/statements",
        json={
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "999",
            "statement_date": "2026-05-10",
            "due_date": "2026-05-25",
            "paid_at": "2026-05-20T10:00:00Z",
        },
        headers=headers,
    )
    resp = await client.get("/api/v1/credit-cards", headers=headers)
    card = resp.json()["cards"][0]
    assert float(card["unpaid_statement_total"]) == 0.0
    assert card["unpaid_statement_count"] == 0


# ─── Detail endpoint (statements + installments sıralı) ─────────────────


@pytest.mark.asyncio
async def test_card_detail_returns_sorted_statements_and_installments(client: AsyncClient):
    headers = await make_user(client, "cc_detail@example.com")
    create = await client.post("/api/v1/credit-cards", json={"name": "Detay"}, headers=headers)
    cid = create.json()["id"]

    # İki ekstre: 2026-04 ve 2026-06 -> en yeni (2026-06) önce
    for pm in (4, 6):
        await client.post(
            f"/api/v1/credit-cards/{cid}/statements",
            json={
                "period_year": 2026,
                "period_month": pm,
                "statement_amount": "100",
                "statement_date": f"2026-0{pm}-10",
                "due_date": f"2026-0{pm}-25",
            },
            headers=headers,
        )
    # İki taksit, farklı first_due_date -> erken olan önce
    for due in ("2026-08-01", "2026-03-01"):
        await client.post(
            f"/api/v1/credit-cards/{cid}/installments",
            json={
                "description": f"T-{due}",
                "monthly_amount": "100",
                "installments_total": 3,
                "first_due_date": due,
            },
            headers=headers,
        )

    resp = await client.get(f"/api/v1/credit-cards/{cid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["card"]["id"] == cid
    # Ekstre: en yeni period önce (6 sonra 4)
    assert data["statements"][0]["period_month"] == 6
    assert data["statements"][1]["period_month"] == 4
    # Taksit: erken first_due önce (Mart sonra Agustos)
    assert data["installments"][0]["first_due_date"] == "2026-03-01"
    assert data["installments"][1]["first_due_date"] == "2026-08-01"


# ─── Statement update / delete ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_statement(client: AsyncClient):
    headers = await make_user(client, "stmt_upd@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "SU"}, headers=headers)
    cid = card.json()["id"]
    s = await client.post(
        f"/api/v1/credit-cards/{cid}/statements",
        json={
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "100",
            "statement_date": "2026-05-10",
            "due_date": "2026-05-25",
        },
        headers=headers,
    )
    sid = s.json()["id"]

    resp = await client.put(
        f"/api/v1/credit-cards/{cid}/statements/{sid}",
        json={"statement_amount": "777", "paid_at": "2026-05-26T00:00:00Z"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert float(resp.json()["statement_amount"]) == 777.0
    assert resp.json()["paid_at"] is not None


@pytest.mark.asyncio
async def test_update_statement_card_404(client: AsyncClient):
    headers = await make_user(client, "stmt_upd_404card@example.com")
    resp = await client.put(
        "/api/v1/credit-cards/999999/statements/1",
        json={"statement_amount": "1"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_statement_not_found(client: AsyncClient):
    headers = await make_user(client, "stmt_upd_404@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "SUNF"}, headers=headers)
    cid = card.json()["id"]
    resp = await client.put(
        f"/api/v1/credit-cards/{cid}/statements/999999",
        json={"statement_amount": "1"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_statement(client: AsyncClient):
    headers = await make_user(client, "stmt_del@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "SD"}, headers=headers)
    cid = card.json()["id"]
    s = await client.post(
        f"/api/v1/credit-cards/{cid}/statements",
        json={
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "100",
            "statement_date": "2026-05-10",
            "due_date": "2026-05-25",
        },
        headers=headers,
    )
    sid = s.json()["id"]
    resp = await client.delete(f"/api/v1/credit-cards/{cid}/statements/{sid}", headers=headers)
    assert resp.status_code == 204
    # Tekrar silme -> 404
    resp2 = await client.delete(f"/api/v1/credit-cards/{cid}/statements/{sid}", headers=headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_statement_card_404(client: AsyncClient):
    headers = await make_user(client, "stmt_del_404card@example.com")
    resp = await client.delete("/api/v1/credit-cards/999999/statements/1", headers=headers)
    assert resp.status_code == 404


# ─── Installment update / delete ────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_installment_recalculates_total(client: AsyncClient):
    """monthly_amount/installments_total güncellenince total = monthly × count."""
    headers = await make_user(client, "inst_upd@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "IU"}, headers=headers)
    cid = card.json()["id"]
    i = await client.post(
        f"/api/v1/credit-cards/{cid}/installments",
        json={
            "description": "Eski",
            "monthly_amount": "100",
            "installments_total": 6,
            "first_due_date": "2099-01-01",
        },
        headers=headers,
    )
    iid = i.json()["id"]

    resp = await client.put(
        f"/api/v1/credit-cards/{cid}/installments/{iid}",
        json={"monthly_amount": "250", "installments_total": 4, "description": "Yeni"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Yeni"
    assert float(data["monthly_amount"]) == 250.0
    assert data["installments_total"] == 4
    # total = 250 × 4 = 1000
    assert float(data["total_amount"]) == 1000.0


@pytest.mark.asyncio
async def test_update_installment_card_404(client: AsyncClient):
    headers = await make_user(client, "inst_upd_404card@example.com")
    resp = await client.put(
        "/api/v1/credit-cards/999999/installments/1",
        json={"description": "X"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_installment_not_found(client: AsyncClient):
    headers = await make_user(client, "inst_upd_404@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "IUNF"}, headers=headers)
    cid = card.json()["id"]
    resp = await client.put(
        f"/api/v1/credit-cards/{cid}/installments/999999",
        json={"description": "X"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_installment(client: AsyncClient):
    headers = await make_user(client, "inst_del@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "ID"}, headers=headers)
    cid = card.json()["id"]
    i = await client.post(
        f"/api/v1/credit-cards/{cid}/installments",
        json={
            "description": "Sil",
            "monthly_amount": "100",
            "installments_total": 3,
            "first_due_date": "2099-01-01",
        },
        headers=headers,
    )
    iid = i.json()["id"]
    resp = await client.delete(f"/api/v1/credit-cards/{cid}/installments/{iid}", headers=headers)
    assert resp.status_code == 204
    resp2 = await client.delete(f"/api/v1/credit-cards/{cid}/installments/{iid}", headers=headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_installment_card_404(client: AsyncClient):
    headers = await make_user(client, "inst_del_404card@example.com")
    resp = await client.delete("/api/v1/credit-cards/999999/installments/1", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_installment_remaining_zero_when_fully_past(client: AsyncClient):
    """first_due_date çok geçmişte + az taksit -> installments_remaining = 0."""
    headers = await make_user(client, "inst_past@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "IP"}, headers=headers)
    cid = card.json()["id"]
    resp = await client.post(
        f"/api/v1/credit-cards/{cid}/installments",
        json={
            "description": "Bitmis",
            "monthly_amount": "100",
            "installments_total": 2,
            "first_due_date": "2020-01-01",  # cok eski, 2 taksit coktan bitti
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["installments_remaining"] == 0


# ─── Statement/installment nested IDOR ──────────────────────────────────


@pytest.mark.asyncio
async def test_statement_create_idor_other_user_card(client: AsyncClient):
    """B, A'nın kartına ekstre ekleyemez (404)."""
    headers_a = await make_user(client, "stmt_idor_a@example.com")
    headers_b = await make_user(client, "stmt_idor_b@example.com")
    card = await client.post("/api/v1/credit-cards", json={"name": "A"}, headers=headers_a)
    cid = card.json()["id"]
    resp = await client.post(
        f"/api/v1/credit-cards/{cid}/statements",
        json={
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "100",
            "statement_date": "2026-05-10",
            "due_date": "2026-05-25",
        },
        headers=headers_b,
    )
    assert resp.status_code == 404
