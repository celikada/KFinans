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


async def test_tefas_stocks_normalized_to_positions_object(monkeypatch):
    """tefas/stocks compute DÜZ LİSTE döner → cache {positions: [...]} nesnesi saklamalı.

    Frontend tüm bölümleri `sections.X.positions` ile okur; liste saklanırsa
    `.positions` undefined olup kart boş görünür (v0.8.6 prod bug'ı).
    """
    uid = await _create_user("lc_shape@example.com")
    _patch_all_compute(
        monkeypatch,
        tefas=[{"code": "YAC", "total_value_tl": "100.00"}],
        stocks=[{"ticker": "SISE", "total_value_tl": "50.00"}],
    )
    _patch_usd_rate(monkeypatch)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    assert row is not None
    # Liste değil, {positions: [...]} nesnesi (frontend bunu bekler)
    assert isinstance(row.payload["tefas"], dict)
    assert row.payload["tefas"]["positions"][0]["code"] == "YAC"
    assert isinstance(row.payload["stocks"], dict)
    assert row.payload["stocks"]["positions"][0]["ticker"] == "SISE"
    # Total normalize edilmiş pozisyonlardan toplanır
    assert row.total_value_tl == Decimal("150.00")


async def test_derive_section_notes_stale_stock(monkeypatch):
    """Hisse is_stale → stale_price notu cache health_issues'a yazılır.

    Regresyon: cache-snapshot info/warn notlarını (hisse stale, manuel kripto linked,
    emtia) kaybediyordu → snapshot'ta sarı ünlem çıkmıyordu. Notlar artık section+DB'den
    türetilip health_issues'a yazılır (snapshot preview modal + kayıtta saklama)."""
    uid = await _create_user("lc_notes@example.com")
    _patch_all_compute(
        monkeypatch,
        stocks=[{"ticker": "SISE", "is_stale": True, "total_value_tl": "100.00"}],
    )
    _patch_usd_rate(monkeypatch)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    assert row.health_issues is not None
    assert any(i["code"] == "stale_price" and i.get("symbol") == "SISE" for i in row.health_issues)


async def test_preview_snapshot_from_cache_surfaces_wallet_errors(monkeypatch):
    """preview_snapshot_from_cache cache'ten anında döner + çekilemeyen cüzdan
    zincirlerini (wallets.errors) issue olarak yüzeye çıkarır (snapshot onay modal'ı
    BTC eksik uyarısını gösterebilsin → modal-not-opening prod bug'ı)."""
    uid = await _create_user("lc_preview@example.com")
    wallets = WalletResponse(
        positions=[
            WalletPositionOut(
                wallet_id="w1",
                chain="ethereum",
                address="0xabc",
                symbol="ETH",
                liquid_quantity=Decimal("1"),
                staked_quantity=Decimal("0"),
                pending_rewards=Decimal("0"),
                unit_price_usd=Decimal("2000"),
                unit_price_tl=Decimal("70000"),
                total_value_tl=Decimal("70000"),
            )
        ],
        errors={"bitcoin:xpub6Cn": "Zaman aşımı (ağ/RPC yavaş)"},
    )
    _patch_all_compute(monkeypatch, wallets=wallets)
    _patch_usd_rate(monkeypatch)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    async with TestSession() as db:
        preview = await lc.preview_snapshot_from_cache(uid, db)
    assert preview["saved"] is False
    assert preview["asset_count"] == 1
    assert preview["total_value_tl"] == "70000.00"
    # BTC timeout → issue olarak görünür (modal kullanıcıya gösterir)
    assert any(i["source"] == "wallet" and i.get("chain") == "bitcoin" for i in preview["issues"])


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


async def test_save_snapshot_from_cache_includes_bes(monkeypatch):
    """BES (+ Nakit) live cache'te YOK ama snapshot'a DB'den eklenmeli.

    Regresyon: cache'ten üretilen snapshot BES'i 0 kaydediyordu (prod 14 Haz)."""
    from app.models.bes import BesHolding

    uid = await _create_user("lc_bes@example.com")
    async with TestSession() as db:
        db.add(BesHolding(user_id=uid, plan_name="Emeklilik", paid_principal=Decimal("50000")))
        await db.commit()

    wallets = WalletResponse(
        positions=[
            WalletPositionOut(
                wallet_id="w1",
                chain="ethereum",
                address="0xabc",
                symbol="ETH",
                liquid_quantity=Decimal("1"),
                staked_quantity=Decimal("0"),
                pending_rewards=Decimal("0"),
                unit_price_usd=Decimal("2000"),
                unit_price_tl=Decimal("70000"),
                total_value_tl=Decimal("70000"),
            )
        ],
        errors={},
    )
    _patch_all_compute(monkeypatch, wallets=wallets)
    _patch_usd_rate(monkeypatch)

    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    async with TestSession() as db:
        from sqlalchemy.orm import selectinload

        snapshot = await lc.save_snapshot_from_cache(uid, db)
        result = await db.execute(select(PortfolioSnapshot).where(PortfolioSnapshot.id == snapshot.id).options(selectinload(PortfolioSnapshot.asset_positions)))
        snap = result.scalar_one()

    bes_positions = [p for p in snap.asset_positions if p.asset_type == "pension"]
    assert len(bes_positions) == 1
    assert bes_positions[0].total_value_tl == Decimal("50000.00")
    # Total = ETH (70000) + BES (50000) = 120000 — cache total'ı (70000) AŞAR
    assert snapshot.total_value_tl == Decimal("120000.00")


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


# ---------------------------------------------------------------------------
# refresh_one_section — tek-kart (per-bölüm) yenileme
# ---------------------------------------------------------------------------
async def test_refresh_one_section_updates_only_that_section(monkeypatch):
    """Tek bölüm yenileme: yalnız o bölümün payload'u değişir, diğerleri korunur."""
    from app.schemas.tefas import TefasPositionOut

    uid = await _create_user("lc_one_section@example.com")
    _patch_usd_rate(monkeypatch)
    # Önce tüm bölümleri boş yaz (cache satırı oluşsun).
    _patch_all_compute(monkeypatch)
    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    # Şimdi yalnız TEFAS'ı dolu veriyle yenile.
    tefas_pos = [
        TefasPositionOut(
            code="YAC",
            name="Yapı Kredi Fon",
            quantity=Decimal("100"),
            unit_price_tl=Decimal("2"),
            total_value_tl=Decimal("200"),
        )
    ]

    async def _t(_uid, _db):
        return tefas_pos

    monkeypatch.setattr("app.api.v1.tefas.compute_tefas_positions", _t)
    await lc.refresh_one_section(uid, "tefas", session_factory=TestSession)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    assert row is not None
    assert row.payload["tefas"]["positions"][0]["code"] == "YAC"
    # Diğer bölümler hâlâ mevcut (silinmedi).
    assert "wallets" in row.payload
    assert row.total_value_tl == Decimal("200.00")


async def test_refresh_one_section_invalid_noop(monkeypatch):
    """Geçersiz bölüm adı → no-op (çağrı sessizce döner, hata fırlatmaz)."""
    uid = await _create_user("lc_one_invalid@example.com")
    # Hata fırlatmamalı
    await lc.refresh_one_section(uid, "bilinmeyen", session_factory=TestSession)


async def test_post_refresh_section_returns_202(client, monkeypatch):
    triggered = {"section": None}

    def _fake(_uid, section):
        triggered["section"] = section

    monkeypatch.setattr("app.api.v1.portfolio.trigger_section_refresh", _fake)
    headers = await make_user(client, "lc_section_ep@example.com")

    resp = await client.post("/api/v1/portfolio/refresh/tefas", headers=headers)
    assert resp.status_code == 202
    assert resp.json()["status"] == "refreshing"
    assert triggered["section"] == "tefas"


async def test_post_refresh_section_invalid_404(client):
    headers = await make_user(client, "lc_section_bad@example.com")
    resp = await client.post("/api/v1/portfolio/refresh/bilinmeyen", headers=headers)
    assert resp.status_code == 404


async def test_post_refresh_section_unauthenticated(client):
    resp = await client.post("/api/v1/portfolio/refresh/tefas")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# refresh_one_wallet — tek-cüzdan (per-cüzdan) yenileme
# ---------------------------------------------------------------------------
def _wallet_response(wid: str, *, total: str, errors=None, wallet_errors=None) -> WalletResponse:
    return WalletResponse(
        positions=[
            WalletPositionOut(
                wallet_id=wid,
                chain="ethereum",
                address="0xabcabcabcabc",
                symbol="ETH",
                liquid_quantity=Decimal("1"),
                staked_quantity=Decimal("0"),
                pending_rewards=Decimal("0"),
                unit_price_usd=Decimal("2000"),
                unit_price_tl=Decimal("70000"),
                total_value_tl=Decimal(total),
            )
        ],
        errors=errors or {},
        wallet_errors=wallet_errors or {},
    )


async def test_refresh_one_wallet_patches_only_that_wallet(monkeypatch):
    """Tek cüzdan yenileme: yalnız o wallet_id'nin pozisyonları değişir,
    diğer cüzdanlar + diğer section'lar korunur, total yeniden toplanır."""
    uid = await _create_user("lc_one_wallet@example.com")
    _patch_usd_rate(monkeypatch)

    # İki cüzdanlı başlangıç cache'i: w1=140000, w2=10000.
    initial = WalletResponse(
        positions=[
            WalletPositionOut(
                wallet_id="w1",
                chain="ethereum",
                address="0xaaa",
                symbol="ETH",
                liquid_quantity=Decimal("2"),
                staked_quantity=Decimal("0"),
                pending_rewards=Decimal("0"),
                unit_price_usd=Decimal("2000"),
                unit_price_tl=Decimal("70000"),
                total_value_tl=Decimal("140000"),
            ),
            WalletPositionOut(
                wallet_id="w2",
                chain="bitcoin",
                address="bc1qxyz",
                symbol="BTC",
                liquid_quantity=Decimal("1"),
                staked_quantity=Decimal("0"),
                pending_rewards=Decimal("0"),
                unit_price_usd=Decimal("0"),
                unit_price_tl=Decimal("10000"),
                total_value_tl=Decimal("10000"),
            ),
        ],
        errors={},
        wallet_errors={},
    )
    _patch_all_compute(monkeypatch, wallets=initial)
    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    # Şimdi yalnız w1'i farklı değerle yenile (single-wallet compute).
    async def _single(_uid, _wid, _db):
        return _wallet_response("w1", total="200000")

    monkeypatch.setattr("app.api.v1.portfolio.compute_single_wallet_positions", _single)
    await lc.refresh_one_wallet(uid, "w1", session_factory=TestSession)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    positions = {p["wallet_id"]: p for p in row.payload["wallets"]["positions"]}
    # w1 güncellendi, w2 korundu. (string format mock'a bağlı → Decimal ile kıyas)
    assert Decimal(positions["w1"]["total_value_tl"]) == Decimal("200000")
    assert Decimal(positions["w2"]["total_value_tl"]) == Decimal("10000")
    # total = 200000 + 10000.
    assert row.total_value_tl == Decimal("210000.00")
    assert row.status == "ok"
    assert row.refreshed_at is not None


async def test_refresh_one_wallet_sets_and_clears_wallet_errors(monkeypatch):
    """Yenileme sonrası bu cüzdana hata gelirse wallet_errors[wid] set edilir;
    sonraki başarılı yenilemede temizlenir."""
    uid = await _create_user("lc_wallet_err@example.com")
    _patch_usd_rate(monkeypatch)
    _patch_all_compute(monkeypatch, wallets=_wallet_response("w1", total="140000"))
    await lc.refresh_live_cache(uid, session_factory=TestSession, force=True)

    # 1) Hata ile yenile.
    async def _err(_uid, _wid, _db):
        return WalletResponse(
            positions=[],
            errors={"ethereum:0xabcabcab": "Zaman aşımı (ağ/RPC yavaş)"},
            wallet_errors={"w1": "Zaman aşımı (ağ/RPC yavaş)"},
        )

    monkeypatch.setattr("app.api.v1.portfolio.compute_single_wallet_positions", _err)
    await lc.refresh_one_wallet(uid, "w1", session_factory=TestSession)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    assert row.payload["wallets"]["wallet_errors"].get("w1") == "Zaman aşımı (ağ/RPC yavaş)"
    # Hatalı cüzdanın pozisyonu çıkarıldı (boş döndü).
    assert all(p["wallet_id"] != "w1" for p in row.payload["wallets"]["positions"])

    # 2) Başarılı yenileme → wallet_errors temizlenir.
    async def _ok(_uid, _wid, _db):
        return _wallet_response("w1", total="150000")

    monkeypatch.setattr("app.api.v1.portfolio.compute_single_wallet_positions", _ok)
    await lc.refresh_one_wallet(uid, "w1", session_factory=TestSession)

    async with TestSession() as db:
        row = await lc.get_live_cache(uid, db)
    assert "w1" not in row.payload["wallets"]["wallet_errors"]
    positions = {p["wallet_id"]: p for p in row.payload["wallets"]["positions"]}
    assert Decimal(positions["w1"]["total_value_tl"]) == Decimal("150000")


async def test_post_refresh_wallet_returns_202_for_own_wallet(client, monkeypatch):
    """Kullanıcının kendi aktif cüzdanı → 202 + trigger çağrılır."""
    triggered = {"wallet_id": None}

    def _fake(_uid, wallet_id):
        triggered["wallet_id"] = wallet_id

    monkeypatch.setattr("app.api.v1.portfolio.trigger_wallet_refresh", _fake)
    headers = await make_user(client, "lc_wallet_ep@example.com")
    add = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0x1111000000000000000000000000000000000001"},
        headers=headers,
    )
    wid = add.json()["id"]

    resp = await client.post(f"/api/v1/portfolio/refresh/wallet/{wid}", headers=headers)
    assert resp.status_code == 202
    assert resp.json()["status"] == "refreshing"
    assert triggered["wallet_id"] == wid


async def test_post_refresh_wallet_404_for_other_user(client, monkeypatch):
    """Başka kullanıcının cüzdanı → 404 (IDOR), trigger çağrılmaz."""
    triggered = {"n": 0}
    monkeypatch.setattr(
        "app.api.v1.portfolio.trigger_wallet_refresh",
        lambda *_a, **_k: triggered.__setitem__("n", triggered["n"] + 1),
    )
    h1 = await make_user(client, "lc_wallet_idor_a@example.com")
    h2 = await make_user(client, "lc_wallet_idor_b@example.com")
    add = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0x2222000000000000000000000000000000000001"},
        headers=h1,
    )
    wid = add.json()["id"]

    resp = await client.post(f"/api/v1/portfolio/refresh/wallet/{wid}", headers=h2)
    assert resp.status_code == 404
    assert triggered["n"] == 0


async def test_post_refresh_wallet_404_for_missing_wallet(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.portfolio.trigger_wallet_refresh", lambda *_a, **_k: None)
    headers = await make_user(client, "lc_wallet_missing@example.com")
    resp = await client.post(f"/api/v1/portfolio/refresh/wallet/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


async def test_post_refresh_wallet_unauthenticated(client):
    resp = await client.post(f"/api/v1/portfolio/refresh/wallet/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# compute_single_wallet_positions — IDOR + tek-satır sorgu
# ---------------------------------------------------------------------------
async def test_compute_single_wallet_positions_idor_returns_empty(client, monkeypatch):
    """Başka kullanıcının wallet_id'si → boş WalletResponse (sorgu eşleşmez)."""
    from app.api.v1.portfolio import compute_single_wallet_positions

    h1 = await make_user(client, "csw_idor_a@example.com")
    add = await client.post(
        "/api/v1/wallets",
        json={"chain": "ethereum", "address": "0x3333000000000000000000000000000000000001"},
        headers=h1,
    )
    wid = add.json()["id"]

    other_uid = await _create_user("csw_idor_b@example.com")
    async with TestSession() as db:
        res = await compute_single_wallet_positions(other_uid, wid, db)
    assert res.positions == []
    assert res.wallet_errors == {}
