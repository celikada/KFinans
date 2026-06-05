"""Kredi kartı ekstresi (PDF) import endpoint testleri.

preview + commit akışı + fail-safe (tanınmayan/değişmiş format) + IDOR +
idempotency (tekrar commit'te duplike yok).

PDF→metin dönüşümü (pdfplumber, 3. parti) `extract_text` monkeypatch'i ile
izole edilir; gerçek `%PDF-` byte'ları validate_pdf_upload'tan geçer ama metin
deterministiktir. Böylece endpoint mantığı (parse + eşleştirme + persist) test
edilir, font/PDF render kırılganlığı testi etkilemez.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_user

# pdfplumber'ın üreteceğine yakın Ziraat ekstresi metni (header'da banka adı).
SAMPLE_TEXT = """Ziraat Bankası bankkart
5309-####-####-7316 Kart Limiti : 500.000,00 TL
Hesap Kesim Tarihi : 26.05.2026 Sonraki Hesap Kesim Tarihi : 26.06.2026
Son Ödeme Tarihi : 05.06.2026 Sonraki Son Ödeme Tarihi : 06.07.2026
Dönem Borcu TL : 83.558,33 TL
27.04.2026 Sonradan Taksit S/ANADOLU HAY 4. Taksit (100000.00 TL İşlemin 4/4 Taksidi) 25.000,00
09.05.2026 09/03 IYZICO/SHOP.HUAWEİ 03.Tak İSTANBUL (15499.00 TL İşlemin 3/3 Taksidi) 5.166,33
"""

_PDF_BYTES = b"%PDF-1.4\n%fake minimal pdf for upload validation\n"


def _patch_extract(monkeypatch, text: str):
    monkeypatch.setattr("app.api.v1.credit_cards.extract_text", lambda _b: text)


def _pdf_files(name: str = "ekstre.pdf"):
    return {"file": (name, _PDF_BYTES, "application/pdf")}


# ─── preview ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_preview_happy_path(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "si_preview@example.com")
    _patch_extract(monkeypatch, SAMPLE_TEXT)

    resp = await client.post("/api/v1/credit-cards/import-statement/preview", files=_pdf_files(), headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["bank_name"] == "Ziraat Bankası"
    assert data["last_4"] == "7316"
    assert data["statement_amount"] == "83558.33"
    assert data["due_date"] == "2026-06-05"
    assert data["matched_card_id"] is None  # henüz kart yok
    assert len(data["installments"]) == 2
    assert data["warnings"]  # çoklu taksit uyarısı


@pytest.mark.asyncio
async def test_preview_unknown_bank_rejected(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "si_unknown@example.com")
    _patch_extract(monkeypatch, "Bu bir banka ekstresi değil, rastgele metin.")

    resp = await client.post("/api/v1/credit-cards/import-statement/preview", files=_pdf_files(), headers=headers)
    assert resp.status_code == 422
    assert "tanınmadı" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_preview_changed_format_rejected(client: AsyncClient, monkeypatch):
    """Banka tanındı ama beklenen alanlar yok → format değişmiş, 422 (kayıt yok)."""
    headers = await make_user(client, "si_changed@example.com")
    _patch_extract(monkeypatch, "Ziraat Bankası Bankkart ekstresi ama tarih/tutar alanları farklı.")

    resp = await client.post("/api/v1/credit-cards/import-statement/preview", files=_pdf_files(), headers=headers)
    assert resp.status_code == 422
    assert "format" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_matches_existing_card(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "si_match@example.com")
    create = await client.post(
        "/api/v1/credit-cards",
        json={"name": "Ziraat", "bank_name": "Ziraat Bankası", "last_4": "7316"},
        headers=headers,
    )
    card_id = create.json()["id"]

    _patch_extract(monkeypatch, SAMPLE_TEXT)
    resp = await client.post("/api/v1/credit-cards/import-statement/preview", files=_pdf_files(), headers=headers)
    assert resp.status_code == 200
    assert resp.json()["matched_card_id"] == card_id


@pytest.mark.asyncio
async def test_preview_rejects_non_pdf(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "si_nonpdf@example.com")
    _patch_extract(monkeypatch, SAMPLE_TEXT)
    files = {"file": ("ekstre.pdf", b"PK\x03\x04 not a pdf", "application/pdf")}
    resp = await client.post("/api/v1/credit-cards/import-statement/preview", files=files, headers=headers)
    assert resp.status_code == 422  # magic byte %PDF- değil


# ─── commit ──────────────────────────────────────────────────────────────────


def _commit_payload(target_card_id=None):
    return {
        "target_card_id": target_card_id,
        "name": "Ziraat Bankası",
        "bank_name": "Ziraat Bankası",
        "last_4": "7316",
        "credit_limit": "500000.00",
        "statement_day": 26,
        "payment_due_day": 5,
        "statement": {
            "period_year": 2026,
            "period_month": 5,
            "statement_amount": "83558.33",
            "statement_date": "2026-05-26",
            "due_date": "2026-06-05",
        },
        "installments": [
            {
                "description": "S/ANADOLU HAY (1/4)",
                "monthly_amount": "25000.00",
                "installments_total": 4,
                "installments_paid": 1,
                "first_due_date": "2026-02-01",
            },
            {
                "description": "IYZICO/SHOP.HUAWEİ (1/3)",
                "monthly_amount": "5166.33",
                "installments_total": 3,
                "installments_paid": 1,
                "first_due_date": "2026-03-01",
            },
        ],
    }


@pytest.mark.asyncio
async def test_commit_creates_new_card(client: AsyncClient):
    headers = await make_user(client, "si_commit_new@example.com")
    resp = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_commit_payload(),
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["card"]["last_4"] == "7316"
    assert data["card"]["bank_name"] == "Ziraat Bankası"
    assert len(data["statements"]) == 1
    assert data["statements"][0]["statement_amount"] == "83558.33"
    assert len(data["installments"]) == 2


@pytest.mark.asyncio
async def test_commit_idempotent_no_duplicates(client: AsyncClient):
    """Aynı commit iki kez → ekstre upsert (1 tane), taksit duplike olmaz."""
    headers = await make_user(client, "si_commit_idem@example.com")
    first = await client.post("/api/v1/credit-cards/import-statement/commit", json=_commit_payload(), headers=headers)
    card_id = first.json()["card"]["id"]

    second = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_commit_payload(target_card_id=card_id),
        headers=headers,
    )
    assert second.status_code == 201
    data = second.json()
    assert len(data["statements"]) == 1  # period unique → upsert
    assert len(data["installments"]) == 2  # duplike eklenmedi


@pytest.mark.asyncio
async def test_commit_idor_other_users_card(client: AsyncClient):
    owner = await make_user(client, "si_owner@example.com")
    create = await client.post("/api/v1/credit-cards", json={"name": "Owner Card"}, headers=owner)
    other_card_id = create.json()["id"]

    attacker = await make_user(client, "si_attacker@example.com")
    resp = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_commit_payload(target_card_id=other_card_id),
        headers=attacker,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_commit_appends_to_existing_card(client: AsyncClient):
    headers = await make_user(client, "si_commit_existing@example.com")
    create = await client.post(
        "/api/v1/credit-cards",
        json={"name": "Ziraat", "bank_name": "Ziraat Bankası", "last_4": "7316"},
        headers=headers,
    )
    card_id = create.json()["id"]

    resp = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_commit_payload(target_card_id=card_id),
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["card"]["id"] == card_id
    assert len(resp.json()["statements"]) == 1


# ─── Taksit çift-sayım fix (v0.3.7) ────────────────────────────────────────


def _stmt_commit(*, target_card_id, period_month, due_date, desc, paid, total, monthly="25000.00", amount="100000.00"):
    """Tek taksitli ekstre commit payload'ı (çift-sayım testleri için)."""
    return {
        "target_card_id": target_card_id,
        "name": "Test Kart",
        "bank_name": "Test",
        "last_4": "0001",
        "statement_day": 26,
        "payment_due_day": 5,
        "statement": {
            "period_year": 2026,
            "period_month": period_month,
            "statement_amount": amount,
            "statement_date": f"2026-{period_month:02d}-26",
            "due_date": due_date,
        },
        "installments": [
            {
                "description": f"{desc} ({paid}/{total})",
                "monthly_amount": monthly,
                "installments_total": total,
                "installments_paid": paid,
                "first_due_date": "2026-02-01",
            }
        ],
    }


@pytest.mark.asyncio
async def test_installment_only_future_projected(client: AsyncClient):
    """(1/4) ekstresi → kayıt: remaining=3 (gelecek), first_due = due_ay + 1."""
    headers = await make_user(client, "si_inst_future@example.com")
    r = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_stmt_commit(target_card_id=None, period_month=6, due_date="2026-06-05", desc="IYZICO HOYA", paid=1, total=4),
        headers=headers,
    )
    assert r.status_code == 201
    insts = r.json()["installments"]
    assert len(insts) == 1
    assert insts[0]["installments_remaining"] == 3  # 4 - 1 (mevcut dilim ekstrede)
    assert insts[0]["first_due_date"] == "2026-07-01"  # due ayı (Haziran) + 1


@pytest.mark.asyncio
async def test_installment_last_not_projected(client: AsyncClient):
    """(4/4) son dilim → gelecek yok → taksit kaydı oluşmaz."""
    headers = await make_user(client, "si_inst_last@example.com")
    r = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_stmt_commit(target_card_id=None, period_month=8, due_date="2026-08-05", desc="SON DILIM", paid=4, total=4),
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["installments"] == []


@pytest.mark.asyncio
async def test_installment_description_cleaned(client: AsyncClient):
    """Saklanan taksit adı dilim göstergelerinden temizlenir (tüm bankalar için).

    "... 01.Tak ... (1/4)" → "(k/n)" eki + "01.Tak" işareti çıkar; temiz satıcı kalır."""
    headers = await make_user(client, "si_inst_clean@example.com")
    r = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_stmt_commit(
            target_card_id=None,
            period_month=6,
            due_date="2026-06-05",
            desc="01/06 IYZICO/HOYA TURKEY 01.Tak İSTANBUL",
            paid=1,
            total=4,
        ),
        headers=headers,
    )
    assert r.status_code == 201
    insts = r.json()["installments"]
    assert len(insts) == 1
    # "(1/4)" eki + "01.Tak" işareti çıkmış, temiz satıcı adı kalmış.
    assert insts[0]["description"] == "01/06 IYZICO/HOYA TURKEY İSTANBUL"


@pytest.mark.asyncio
async def test_installment_reimport_with_markers_still_matches(client: AsyncClient):
    """Ham (işaretli) açıklamayla re-import, temiz saklanan kayda eşleşir — duplike yok.

    Eşleştirme her iki tarafta da tam-temizleme uygular; ilk ekstre temiz saklanır,
    sonraki ekstre ham gelse de aynı plana ilerler."""
    headers = await make_user(client, "si_inst_marker_match@example.com")
    first = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_stmt_commit(target_card_id=None, period_month=6, due_date="2026-06-05", desc="HOYA TURKEY 01.Tak", paid=1, total=4),
        headers=headers,
    )
    cid = first.json()["card"]["id"]
    second = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_stmt_commit(target_card_id=cid, period_month=7, due_date="2026-07-05", desc="HOYA TURKEY 02.Tak", paid=2, total=4),
        headers=headers,
    )
    insts = second.json()["installments"]
    assert len(insts) == 1  # duplike DEĞİL — aynı plan (temiz ad eşleşti)
    assert insts[0]["installments_remaining"] == 2
    assert insts[0]["description"] == "HOYA TURKEY"


@pytest.mark.asyncio
async def test_installment_advances_on_reimport(client: AsyncClient):
    """Sonraki ay (2/4) yüklenince aynı plan ilerler: yeni satır DEĞİL, remaining=2."""
    headers = await make_user(client, "si_inst_adv@example.com")
    first = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_stmt_commit(target_card_id=None, period_month=6, due_date="2026-06-05", desc="HOYA TURKEY", paid=1, total=4),
        headers=headers,
    )
    cid = first.json()["card"]["id"]

    second = await client.post(
        "/api/v1/credit-cards/import-statement/commit",
        json=_stmt_commit(target_card_id=cid, period_month=7, due_date="2026-07-05", desc="HOYA TURKEY", paid=2, total=4),
        headers=headers,
    )
    insts = second.json()["installments"]
    assert len(insts) == 1  # YENİ satır değil — aynı plan güncellendi
    assert insts[0]["installments_remaining"] == 2  # 4 - 2
    assert insts[0]["first_due_date"] == "2026-08-01"  # Temmuz + 1


@pytest.mark.asyncio
async def test_installment_reimport_idempotent(client: AsyncClient):
    """Aynı (2/4) ekstresi 2 kez → remaining 2'de kalır (mutlak set, artımsal değil)."""
    headers = await make_user(client, "si_inst_idem@example.com")
    p = _stmt_commit(target_card_id=None, period_month=7, due_date="2026-07-05", desc="TEKRAR", paid=2, total=4)
    first = await client.post("/api/v1/credit-cards/import-statement/commit", json=p, headers=headers)
    cid = first.json()["card"]["id"]
    p2 = _stmt_commit(target_card_id=cid, period_month=7, due_date="2026-07-05", desc="TEKRAR", paid=2, total=4)
    second = await client.post("/api/v1/credit-cards/import-statement/commit", json=p2, headers=headers)
    insts = second.json()["installments"]
    assert len(insts) == 1
    assert insts[0]["installments_remaining"] == 2  # ilerletme mutlak — 1'e düşmedi
