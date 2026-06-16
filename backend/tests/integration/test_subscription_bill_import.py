"""Abonelik PDF fatura import endpoint testleri (preview + commit).

`extract_text` monkeypatch ile fixture metni döndürülür (gerçek PDF parse zaten
unit testlerde); endpoint akışı (eşle/oluştur/idempotent/fail-safe) test edilir.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.conftest import make_user

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "bills"
_PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _text(name: str) -> str:
    return (_FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


def _patch_extract(monkeypatch, name: str) -> None:
    import app.api.v1.subscriptions as sub_mod

    monkeypatch.setattr(sub_mod, "extract_text", lambda _content: _text(name))


def _upload():
    return {"file": ("bill.pdf", _PDF_BYTES, "application/pdf")}


@pytest.mark.asyncio
async def test_preview_no_match(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "bill_prev@example.com")
    _patch_extract(monkeypatch, "vodafone")
    resp = await client.post("/api/v1/subscriptions/import-bill/preview", files=_upload(), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider_code"] == "vodafone"
    assert body["provider_name"] == "Vodafone"
    assert body["subscriber_no"] == "500 000 00 00"
    assert float(body["bill_amount"]) == 1077.0
    assert body["matched_subscription_id"] is None  # henüz abonelik yok


@pytest.mark.asyncio
async def test_commit_creates_subscription_and_bill(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "bill_commit@example.com")
    _patch_extract(monkeypatch, "esgaz")
    prev = await client.post("/api/v1/subscriptions/import-bill/preview", files=_upload(), headers=headers)
    parsed = prev.json()
    parsed["subscription_id"] = None
    commit = await client.post("/api/v1/subscriptions/import-bill/commit", json=parsed, headers=headers)
    assert commit.status_code == 200, commit.text
    assert commit.json()["status"] == "issued"
    assert float(commit.json()["bill_amount"]) == 1004.0
    # Abonelik otomatik oluşmuş olmalı (doğalgaz)
    lst = await client.get("/api/v1/subscriptions", headers=headers)
    subs = lst.json()
    assert len(subs) == 1
    assert subs[0]["provider_code"] == "esgaz"
    assert subs[0]["category"] == "gas"
    assert subs[0]["subscriber_no"] == "1234567890"
    assert subs[0]["next_bill_date"] == "2026-07-08"


@pytest.mark.asyncio
async def test_commit_matches_existing_subscription(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "bill_match@example.com")
    # Önce aynı abone no ile abonelik oluştur (boşluklu farklı format → normalize eşleşir)
    create = await client.post(
        "/api/v1/subscriptions",
        json={"provider_code": "vodafone", "subscriber_no": "5000000000", "budget_amount": 900},
        headers=headers,
    )
    sub_id = create.json()["id"]
    _patch_extract(monkeypatch, "vodafone")
    prev = await client.post("/api/v1/subscriptions/import-bill/preview", files=_upload(), headers=headers)
    body = prev.json()
    # "500 000 00 00" normalize → "5000000000" eşleşmeli
    assert body["matched_subscription_id"] == sub_id
    body["subscription_id"] = sub_id
    commit = await client.post("/api/v1/subscriptions/import-bill/commit", json=body, headers=headers)
    assert commit.status_code == 200
    # Yeni abonelik OLUŞMAMALI (hâlâ 1)
    lst = await client.get("/api/v1/subscriptions", headers=headers)
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_commit_idempotent_reimport(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "bill_idem@example.com")
    _patch_extract(monkeypatch, "ttnet")
    prev = await client.post("/api/v1/subscriptions/import-bill/preview", files=_upload(), headers=headers)
    parsed = prev.json()
    parsed["subscription_id"] = None
    await client.post("/api/v1/subscriptions/import-bill/commit", json=parsed, headers=headers)
    # İkinci kez aynı fatura → mevcut aboneliğe eşleşir, dönem upsert (duplike yok)
    prev2 = await client.post("/api/v1/subscriptions/import-bill/preview", files=_upload(), headers=headers)
    parsed2 = prev2.json()
    parsed2["subscription_id"] = parsed2["matched_subscription_id"]
    commit2 = await client.post("/api/v1/subscriptions/import-bill/commit", json=parsed2, headers=headers)
    assert commit2.status_code == 200
    lst = await client.get("/api/v1/subscriptions", headers=headers)
    assert len(lst.json()) == 1
    bills = await client.get(f"/api/v1/subscriptions/{lst.json()[0]['id']}/bills", headers=headers)
    issued = [b for b in bills.json() if b["status"] == "issued"]
    assert len(issued) == 1  # tek dönem, duplike yok


@pytest.mark.asyncio
async def test_preview_image_pdf_fail_safe(client: AsyncClient, monkeypatch):
    """Metin katmanı yok (taranmış görüntü) → 422, asla tahmini veri."""
    headers = await make_user(client, "bill_img@example.com")
    import app.api.v1.subscriptions as sub_mod

    monkeypatch.setattr(sub_mod, "extract_text", lambda _c: "")
    resp = await client.post("/api/v1/subscriptions/import-bill/preview", files=_upload(), headers=headers)
    assert resp.status_code == 422
    assert "metin" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_unknown_provider_fail_safe(client: AsyncClient, monkeypatch):
    headers = await make_user(client, "bill_unk@example.com")
    import app.api.v1.subscriptions as sub_mod

    monkeypatch.setattr(sub_mod, "extract_text", lambda _c: "Bilinmeyen bir kurumun faturası, uzun metin " * 3)
    resp = await client.post("/api/v1/subscriptions/import-bill/preview", files=_upload(), headers=headers)
    assert resp.status_code == 422
