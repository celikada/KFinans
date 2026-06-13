"""live_cache servisi için unit/integration testler.

refresh_live_cache (ok / stale-noop / error path), single-flight, get_live_cache,
save_snapshot_from_cache (total eşitliği) + GET/POST endpoint davranışı.

compute_* fonksiyonları monkeypatch ile sahte değerlere bağlanır — dış-API
çağrısı yapılmaz. DB gerçek (Postgres test container), session_factory=TestSession.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.live_cache import LivePortfolioCache
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.schemas.portfolio import (
    CryptoPositionOut,
    CryptoResponse,
    WalletPositionOut,
    WalletResponse,
)
from app.services import live_cache as lc
from tests.conftest import TestSession, make_user

pytestmark = pytest.mark.asyncio


async def _create_user(email: str) -> uuid.UUID:
    """Test kullanıcısı oluşturur ve id'sini döner (DB'ye doğrudan yazar)."""
    pwd = "guclu-sifre-123"
    async with TestSession() as session:
        from app.core.security import hash_password

        user = User(
            email=email,
            password_hash=hash_password(pwd),
            email_verified=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


def _patch_all_compute(monkeypatch, *, wallets=None, crypto=None, tefas=None, stocks=None, commodities=None, manual=None):
    """6 compute_* fonksiyonunu sahte coroutine'lere bağlar."""

    async def _w(_uid, _db):
        return wallets if wallets is not None else WalletResponse(positions=[], errors={})

    async def _c(_uid, _db):
        return crypto if crypto is not None else CryptoResponse(positions=[], errors={})

    async def _t(_uid, _db):
        return tefas if tefas is not None else []

    async def _s(_uid, _db):
        return stocks if stocks is not None else []

    async def _cm(_uid, _db):
        from app.schemas.commodity import CommoditySummaryOut

        return (
            commodities
            if commodities is not None
            else CommoditySummaryOut(
                positions=[],
                total_gold_gram=Decimal(0),
                total_silver_gram=Decimal(0),
                total_value_tl=Decimal(0),
                gold_price_tl=Decimal(0),
                silver_price_tl=Decimal(0),
            )
        )

    async def _mc(_uid, _db):
        from app.schemas.manual_crypto import ManualCryptoSummaryOut

        return manual if manual is not None else ManualCryptoSummaryOut(positions=[], total_value_tl=Decimal(0), unknown_symbols=[])

    monkeypatch.setattr("app.api.v1.portfolio.compute_wallet_positions", _w)
    monkeypatch.setattr("app.api.v1.portfolio.compute_crypto_positions", _c)
    monkeypatch.setattr("app.api.v1.tefas.compute_tefas_positions", _t)
    monkeypatch.setattr("app.api.v1.stocks.compute_stock_positions", _s)
    monkeypatch.setattr("app.api.v1.commodity.compute_commodities", _cm)
    monkeypatch.setattr("app.api.v1.manual_crypto.compute_manual_crypto", _mc)


def _patch_usd_rate(monkeypatch, rate=Decimal("35")):
    async def _usd():
        return rate

    monkeypatch.setattr("app.services.live_cache.fetch_usd_to_tl", _usd)


# ---------------------------------------------------------------------------
# is_stale
# ---------------------------------------------------------------------------
async def test_is_stale_none_row():
    assert lc.is_stale(None, 15) is True


async def test_is_stale_no_refreshed_at():
    row = LivePortfolioCache(user_id=uuid.uuid4(), refreshed_at=None)
    assert lc.is_stale(row, 15) is True


async def test_is_stale_fresh_and_old():
    fresh = LivePortfolioCache(user_id=uuid.uuid4(), refreshed_at=datetime.now(timezone.utc))
    old = LivePortfolioCache(user_id=uuid.uuid4(), refreshed_at=datetime.now(timezone.utc) - timedelta(minutes=30))
    assert lc.is_stale(fresh, 15) is False
    assert lc.is_stale(old, 15) is True


# ---------------------------------------------------------------------------
# refresh_live_cache — happy path
# ---------------------------------------------------------------------------
async def test_refresh_ok_writes_row(monkeypatch):
    uid = await _create_user("lc_ok@example.com")
    wallets = WalletResponse(
        positions=[
            WalletPositionOut(
                wallet_id="w1",
                chain="ethereum",
                address="0xabcabcabcabc",
                symbol="ETH",
                liquid_quantity=Decimal("2"),
                staked_quantity=Decimal("0"),
                pending_rewards=Decimal("0"),
                unit_price_usd=Decimal("2000"),
                unit_price_tl=Decimal("70000"),
                total_value_tl=Decimal("140000"),
            )
        ],
        errors={},
    )
    _patch_all_compute(monkeypatch, wallets=wallets)
    _patch_usd_rate(monkeypatch)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    assert row is not None
    assert row.status == "ok"
    assert row.refreshed_at is not None
    assert row.total_value_tl == Decimal("140000.00")
    assert row.rates == {"usd_tl": "35"}
    assert "wallets" in row.payload
    assert row.payload["wallets"]["positions"][0]["symbol"] == "ETH"


async def test_refresh_fresh_noop(monkeypatch):
    """force=False + taze satır → compute çağrılmaz (no-op)."""
    uid = await _create_user("lc_noop@example.com")
    # Önce taze bir satır yaz
    async with TestSession() as db:
        db.add(
            LivePortfolioCache(
                user_id=uid,
                payload={"wallets": {"positions": [], "errors": {}}},
                status="ok",
                refreshed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    called = {"n": 0}

    async def _w(_uid, _db):
        called["n"] += 1
        return WalletResponse(positions=[], errors={})

    monkeypatch.setattr("app.api.v1.portfolio.compute_wallet_positions", _w)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=False)
    assert called["n"] == 0  # taze → compute çalışmadı


async def test_refresh_all_sections_fail_marks_error(monkeypatch):
    uid = await _create_user("lc_err@example.com")
    _patch_usd_rate(monkeypatch)

    async def _boom(_uid, _db):
        raise RuntimeError("dış servis patladı")

    monkeypatch.setattr("app.api.v1.portfolio.compute_wallet_positions", _boom)
    monkeypatch.setattr("app.api.v1.portfolio.compute_crypto_positions", _boom)
    monkeypatch.setattr("app.api.v1.tefas.compute_tefas_positions", _boom)
    monkeypatch.setattr("app.api.v1.stocks.compute_stock_positions", _boom)
    monkeypatch.setattr("app.api.v1.commodity.compute_commodities", _boom)
    monkeypatch.setattr("app.api.v1.manual_crypto.compute_manual_crypto", _boom)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    assert row is not None
    assert row.status == "error"
    # Tüm bölümler patladı → refreshed_at güncellenmedi (None kaldı)
    assert row.refreshed_at is None
    assert row.error is not None


async def test_refresh_partial_fail_still_ok(monkeypatch):
    """Bir bölüm patlasa diğerleri yazılır + health_issues kaydedilir."""
    uid = await _create_user("lc_partial@example.com")
    _patch_usd_rate(monkeypatch)
    _patch_all_compute(monkeypatch)  # hepsi boş-başarılı

    async def _boom(_uid, _db):
        raise RuntimeError("tefas patladı")

    monkeypatch.setattr("app.api.v1.tefas.compute_tefas_positions", _boom)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    assert row.status == "ok"
    assert row.refreshed_at is not None
    assert row.health_issues is not None
    assert any(i["source"] == "tefas" for i in row.health_issues)


# ---------------------------------------------------------------------------
# single-flight
# ---------------------------------------------------------------------------
async def test_single_flight_dedups(monkeypatch):
    uid = await _create_user("lc_sf@example.com")
    _patch_usd_rate(monkeypatch)

    import asyncio

    starts = {"n": 0}

    async def _slow_wallet(_uid, _db):
        starts["n"] += 1
        await asyncio.sleep(0.2)
        return WalletResponse(positions=[], errors={})

    _patch_all_compute(monkeypatch)
    monkeypatch.setattr("app.api.v1.portfolio.compute_wallet_positions", _slow_wallet)

    # İki refresh aynı anda — single-flight ile tek tur koşmalı
    await asyncio.gather(
        lc.refresh_live_cache(uid, session_factory=TestSession, force=True),
        lc.refresh_live_cache(uid, session_factory=TestSession, force=True),
    )
    assert starts["n"] == 1


# ---------------------------------------------------------------------------
# save_snapshot_from_cache — total eşitliği
# ---------------------------------------------------------------------------
async def test_save_snapshot_from_cache_total_matches(monkeypatch):
    uid = await _create_user("lc_snap@example.com")
    wallets = WalletResponse(
        positions=[
            WalletPositionOut(
                wallet_id="w1",
                chain="ethereum",
                address="0xabcabcabcabc",
                symbol="ETH",
                liquid_quantity=Decimal("2"),
                staked_quantity=Decimal("0"),
                pending_rewards=Decimal("0"),
                unit_price_usd=Decimal("2000"),
                unit_price_tl=Decimal("70000"),
                total_value_tl=Decimal("140000"),
            )
        ],
        errors={},
    )
    crypto = CryptoResponse(
        positions=[
            CryptoPositionOut(
                provider="binance",
                symbol="BTC",
                liquid_quantity=Decimal("0.5"),
                staked_quantity=Decimal("0"),
                unit_price_usd=Decimal("60000"),
                unit_price_tl=Decimal("2100000"),
                total_value_tl=Decimal("1050000"),
            )
        ],
        errors={},
    )
    _patch_all_compute(monkeypatch, wallets=wallets, crypto=crypto)
    _patch_usd_rate(monkeypatch)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    async with TestSession() as db:
        cache = await lc.get_live_cache(uid, db)
        cache_total = cache.total_value_tl
        snapshot = await lc.save_snapshot_from_cache(uid, db)

    # Snapshot total == cache total (cache'ten üretildi, yeniden çekim yok)
    assert snapshot.total_value_tl == cache_total
    assert snapshot.total_value_tl == Decimal("1190000.00")

    async with TestSession() as db:
        from sqlalchemy.orm import selectinload

        result = await db.execute(select(PortfolioSnapshot).where(PortfolioSnapshot.id == snapshot.id).options(selectinload(PortfolioSnapshot.asset_positions)))
        snap = result.scalar_one()
    symbols = {p.symbol for p in snap.asset_positions}
    assert symbols == {"ETH", "BTC"}
    # AssetPosition toplamı snapshot total'ına eşit olmalı
    pos_total = sum(p.total_value_tl for p in snap.asset_positions)
    assert pos_total == snapshot.total_value_tl


async def test_save_snapshot_from_cache_no_cache_raises():
    uid = await _create_user("lc_nocache@example.com")
    async with TestSession() as db:
        with pytest.raises(ValueError):
            await lc.save_snapshot_from_cache(uid, db)


# ---------------------------------------------------------------------------
# Endpoint testleri
# ---------------------------------------------------------------------------
async def test_get_live_no_cache_returns_refreshing(client, monkeypatch):
    # trigger_background_refresh no-op'a çevir (gerçek arka plan task açılmasın)
    monkeypatch.setattr("app.api.v1.portfolio.trigger_background_refresh", lambda *a, **k: None)
    headers = await make_user(client, "lc_live_empty@example.com")

    resp = await client.get("/api/v1/portfolio/live", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "refreshing"
    assert data["stale"] is True
    assert data["sections"] == {}


async def test_get_live_with_cache_returns_sections(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.portfolio.trigger_background_refresh", lambda *a, **k: None)
    headers = await make_user(client, "lc_live_full@example.com")

    # Kullanıcının id'sini al + cache satırı yaz
    async with TestSession() as db:
        user = (await db.execute(select(User).where(User.email == "lc_live_full@example.com"))).scalar_one()
        db.add(
            LivePortfolioCache(
                user_id=user.id,
                payload={"wallets": {"positions": [{"symbol": "ETH", "total_value_tl": "140000"}], "errors": {}}},
                total_value_tl=Decimal("140000"),
                rates={"usd_tl": "35"},
                status="ok",
                refreshed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    resp = await client.get("/api/v1/portfolio/live", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["stale"] is False
    assert data["sections"]["wallets"]["positions"][0]["symbol"] == "ETH"
    assert data["total_value_tl"] == "140000.00"


async def test_post_refresh_returns_202(client, monkeypatch):
    triggered = {"n": 0}

    def _fake_trigger(*_a, **_k):
        triggered["n"] += 1

    monkeypatch.setattr("app.api.v1.portfolio.trigger_background_refresh", _fake_trigger)
    headers = await make_user(client, "lc_refresh@example.com")

    resp = await client.post("/api/v1/portfolio/refresh", headers=headers)
    assert resp.status_code == 202
    assert resp.json()["status"] == "refreshing"
    assert triggered["n"] == 1
