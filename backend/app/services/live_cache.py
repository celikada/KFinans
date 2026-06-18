"""Sunucu-tarafı canlı portföy cache servisi.

Ağır/dış-API portföy verisi (cüzdan, kripto, TEFAS, hisse, emtia, manuel kripto)
her dashboard açılışında yeniden çekilmek yerine arka planda hesaplanıp
`live_portfolio_cache` tablosuna (kullanıcı başına tek satır) yazılır. Dashboard +
detay sayfaları bu satırı hızlı DB okumasıyla alır.

Akış:
- `refresh_live_cache(user_id)`: 6 `compute_*` fonksiyonunu paralel çalıştırır,
  sonucu JSON-safe (Decimal→str) payload olarak UPSERT eder. Taze cache varsa
  (force=False) no-op. In-process single-flight: aynı kullanıcı için aynı anda
  iki refresh koşmaz.
- `trigger_background_refresh(user_id)`: login/endpoint'ten best-effort fire-and-forget.
- `get_live_cache` / `is_stale`: okuma + bayatlık ölçümü.
- `save_snapshot_from_cache(user_id, db)`: taze cache'ten PortfolioSnapshot üretir
  (yeniden dış çağrı yapmadan); cache yoksa caller `compute_and_save_snapshot`'a düşer.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.live_cache import LivePortfolioCache
from app.models.portfolio import AssetPosition, PortfolioSnapshot
from app.services.aggregator import fetch_usd_to_tl, to_asset_position
from app.services.base import AssetData

logger = logging.getLogger(__name__)

# In-process single-flight: aynı kullanıcı için aynı anda yalnızca bir refresh.
# Task referansı GC'ye karşı burada tutulur; bitince callback ile temizlenir.
_REFRESH_TASKS: dict[str, asyncio.Task] = {}
# trigger_background_refresh fire-and-forget task referansları (GC engeli).
_BG_TASKS: set[asyncio.Task] = set()

# Toplam refresh deadline güvenlik ağı: per-compute zaten Faz 1 deadline'larıyla
# bounded; bu sınır tek bir patolojik kaynağın tüm refresh'i sonsuz tutmasını engeller.
_REFRESH_TOTAL_TIMEOUT = settings.wallet_total_timeout + 30.0


def is_stale(row: LivePortfolioCache | None, minutes: int) -> bool:
    """Cache satırı bayat mı? refreshed_at None ise (hiç başarılı refresh yok) True."""
    if row is None or row.refreshed_at is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    refreshed = row.refreshed_at
    if refreshed.tzinfo is None:
        refreshed = refreshed.replace(tzinfo=timezone.utc)
    return refreshed < cutoff


async def get_live_cache(user_id, db: AsyncSession) -> LivePortfolioCache | None:
    """Kullanıcının canlı cache satırını döner (yoksa None)."""
    result = await db.execute(select(LivePortfolioCache).where(LivePortfolioCache.user_id == user_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# UPSERT helper'ları
# ---------------------------------------------------------------------------
async def _set_status_refreshing(db: AsyncSession, user_id) -> None:
    """Refresh başlarken satırı status='refreshing' ile UPSERT eder.

    refreshed_at'e DOKUNMAZ (eski başarılı zaman korunur — bayatlık ölçümü için).
    """
    stmt = pg_insert(LivePortfolioCache).values(
        user_id=user_id,
        payload={},
        status="refreshing",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id"],
        set_={"status": "refreshing", "updated_at": datetime.now(timezone.utc)},
    )
    await db.execute(stmt)
    await db.commit()


async def _save_result(
    db: AsyncSession,
    user_id,
    *,
    payload: dict[str, Any],
    total_value_tl: Decimal | None,
    rates: dict[str, Any] | None,
    health_issues: list[dict[str, Any]] | None,
    status: str,
    error: str | None,
    update_refreshed_at: bool,
) -> None:
    """Refresh sonucunu UPSERT eder.

    update_refreshed_at=True (başarı) → refreshed_at=now. False (tam hata) →
    eski refreshed_at korunur (stale-while-revalidate eski veriyi göstersin).
    """
    now = datetime.now(timezone.utc)
    values: dict[str, Any] = {
        "user_id": user_id,
        "payload": payload,
        "total_value_tl": total_value_tl,
        "rates": rates,
        "health_issues": health_issues,
        "status": status,
        "error": error,
    }
    set_: dict[str, Any] = {
        "payload": payload,
        "total_value_tl": total_value_tl,
        "rates": rates,
        "health_issues": health_issues,
        "status": status,
        "error": error,
        "updated_at": now,
    }
    if update_refreshed_at:
        values["refreshed_at"] = now
        set_["refreshed_at"] = now
    stmt = pg_insert(LivePortfolioCache).values(**values)
    stmt = stmt.on_conflict_do_update(index_elements=["user_id"], set_=set_)
    await db.execute(stmt)
    await db.commit()


# ---------------------------------------------------------------------------
# Refresh çekirdeği
# ---------------------------------------------------------------------------
async def _gather_sections(
    user_id,
    session_factory: async_sessionmaker,
) -> tuple[dict[str, Any], Decimal, list[dict[str, Any]]]:
    """6 compute_* fonksiyonunu HER BİRİ KENDİ SESSION'INDA paralel çalıştırır.

    KRİTİK: Aynı AsyncSession üzerinde EŞZAMANLI `db.execute` SQLAlchemy'de
    desteklenmez ("another operation is in progress" — ilk coroutine kazanır,
    diğerleri patlar). Bu yüzden gather'da her bölüme AYRI session verilir
    (gerçek paralellik + izolasyon). snapshot.py aynı nedenle sıralıya çevrildi;
    burada arka plan task'ı olduğu için paralellik per-session ile korunur.

    Patlayan bölüm health_issues'a kaydedilir + sections'ta boş bırakılır
    (diğer bölümler etkilenmez).
    """
    # Geç import — modül seviyesinde import portfolio router'ı yüklerken döngü riski.
    from app.api.v1.commodity import compute_commodities
    from app.api.v1.manual_crypto import compute_manual_crypto
    from app.api.v1.portfolio import compute_crypto_positions, compute_wallet_positions
    from app.api.v1.stocks import compute_stock_positions
    from app.api.v1.tefas import compute_tefas_positions

    section_computers = [
        ("wallets", compute_wallet_positions),
        ("crypto", compute_crypto_positions),
        ("tefas", compute_tefas_positions),
        ("stocks", compute_stock_positions),
        ("commodities", compute_commodities),
        ("manual_crypto", compute_manual_crypto),
    ]

    async def _run(fn) -> Any:
        async with session_factory() as section_db:
            return await fn(user_id, section_db)

    names = [name for name, _ in section_computers]
    results = await asyncio.gather(*(_run(fn) for _, fn in section_computers), return_exceptions=True)

    sections: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []
    for name, res in zip(names, results):
        if isinstance(res, BaseException):
            # gather(return_exceptions=True) → res except bloğunda DEĞİL; logger.exception
            # burada sys.exc_info()=None okur ("NoneType: None"). Gerçek hatayı görmek
            # için exc_info=res ver (traceback + tip loglanır).
            logger.error(
                "Live cache: '%s' bölümü hesaplanamadı user_id=%s: %r",
                name,
                user_id,
                res,
                exc_info=res,
            )
            issues.append(
                {
                    "source": name,
                    "code": "section_failed",
                    "msg": "Bu bölüm geçici olarak hesaplanamadı.",
                    "level": "warn",
                }
            )
            sections[name] = _empty_section(name)
        else:
            encoded = jsonable_encoder(res)
            # tefas/stocks compute'ları düz LİSTE döner (list[...PositionOut]);
            # frontend tüm bölümleri {positions: [...]} nesnesi olarak okur. Liste
            # → {"positions": liste} normalize et (yoksa kart boş görünür).
            if isinstance(encoded, list):
                encoded = {"positions": encoded}
            sections[name] = encoded

    total_tl = _sum_sections_total(sections)
    return sections, total_tl, issues


def _empty_section(name: str) -> Any:
    """Patlayan bölüm için boş ama şekil-uyumlu placeholder."""
    if name in ("wallets", "crypto"):
        return {"positions": [], "errors": {}}
    if name in ("tefas", "stocks"):
        # Frontend {positions: [...]} bekler (compute düz liste döner → normalize edilir).
        return {"positions": []}
    if name == "commodities":
        return {
            "positions": [],
            "total_gold_gram": "0",
            "total_silver_gram": "0",
            "total_value_tl": "0",
            "gold_price_tl": "0",
            "silver_price_tl": "0",
            "gold_price_available": False,
            "silver_price_available": False,
        }
    # manual_crypto
    return {"positions": [], "total_value_tl": "0", "unknown_symbols": []}


def _iter_section_positions(section: Any) -> list[dict[str, Any]]:
    """Bir cache section'ından pozisyon dict listesini çıkarır (şekil normalize)."""
    if isinstance(section, list):
        return section
    if isinstance(section, dict):
        return section.get("positions", []) or []
    return []


def _sum_sections_total(sections: dict[str, Any]) -> Decimal:
    """Tüm bölüm pozisyonlarının total_value_tl toplamı (cache total)."""
    total = Decimal(0)
    for section in sections.values():
        for pos in _iter_section_positions(section):
            raw = pos.get("total_value_tl")
            if raw is None:
                continue
            try:
                total += Decimal(str(raw))
            except (ValueError, ArithmeticError):
                continue
    return total.quantize(Decimal("0.01"))


async def _manual_crypto_notes(user_id, db: AsyncSession, sections: dict[str, Any]) -> list[dict[str, Any]]:
    """Manuel kripto linked fiyat-kaynağı notları (info) / fiyat çekilemedi (warn)."""
    from app.models.manual_crypto import ManualCryptoHolding

    linked = (
        (
            await db.execute(
                select(ManualCryptoHolding).where(
                    ManualCryptoHolding.user_id == user_id,
                    ManualCryptoHolding.price_source == "linked",
                )
            )
        )
        .scalars()
        .all()
    )
    if not linked:
        return []
    pos_by_key = {(p.get("exchange"), p.get("symbol")): p for p in _iter_section_positions(sections.get("manual_crypto", {}))}
    notes: list[dict[str, Any]] = []
    for h in linked:
        pos = pos_by_key.get((h.exchange, h.symbol))
        price = Decimal(str(pos.get("unit_price_tl", "0"))) if pos else Decimal(0)
        ls, lid = h.linked_source or "?", h.linked_id or "?"
        if price > 0:
            notes.append(
                {
                    "source": "manual_crypto",
                    "exchange": h.exchange,
                    "symbol": h.symbol,
                    "code": "info_linked",
                    "level": "info",
                    "msg": f"{h.exchange} {h.symbol}: {ls}:{lid} fiyatına bağlı (anlık {price} ₺/birim)",
                }
            )
        else:
            notes.append(
                {
                    "source": "manual_crypto",
                    "exchange": h.exchange,
                    "symbol": h.symbol,
                    "code": f"linked_{ls}_no_price",
                    "level": "warn",
                    "msg": f"{h.exchange} {h.symbol}: linked={ls}:{lid} fiyatı çekilemedi/bulunamadı",
                }
            )
    return notes


async def _derive_section_notes(user_id, db: AsyncSession, sections: dict[str, Any]) -> list[dict[str, Any]]:
    """Section + DB verisinden veri-kalitesi notları türetir (yeniden çekim YOK).

    snapshot.py `_gather_*` notlarının cache karşılığı: hisse stale_price, emtia
    erişilemez, manuel kripto linked (info)/no_price (warn). Bu notlar cache
    health_issues'a yazılır → snapshot preview modal'da gösterir + snapshot kaydında
    saklanır (geçmiş listesindeki sarı ünlem).
    """
    notes: list[dict[str, Any]] = []
    # TEFAS: o an fiyatlanamayan fon (geçici 0 portföy değeri vb.) — pozisyon
    # listede price_available=False ile kalır; tek fiyatsız fon kartı çökertmez.
    for p in _iter_section_positions(sections.get("tefas", {})):
        if p.get("price_available") is False:
            code = p.get("code", "?")
            notes.append(
                {
                    "source": "tefas",
                    "symbol": code,
                    "code": "price_unavailable",
                    "level": "warn",
                    "msg": f"{code}: TEFAS fiyatı şu an alınamıyor (fon geçici olarak fiyatlanamıyor)",
                }
            )
    # Hisse: anlık fiyat alınamadı → son kapanış kullanıldı (is_stale)
    for p in _iter_section_positions(sections.get("stocks", {})):
        if p.get("is_stale"):
            tk = p.get("ticker", "?")
            notes.append(
                {
                    "source": "stocks",
                    "symbol": tk,
                    "code": "stale_price",
                    "level": "warn",
                    "msg": f"{tk}: anlık fiyat alınamadı, son bilinen kapanış kullanıldı",
                }
            )
    # Emtia: altın/gümüş anlık fiyatı erişilemez
    commodity = sections.get("commodities")
    if isinstance(commodity, dict):
        if commodity.get("gold_price_available") is False:
            notes.append({"source": "commodities", "code": "gold_unavailable", "level": "warn", "msg": "Altın anlık fiyatı alınamadı"})
        if commodity.get("silver_price_available") is False and commodity.get("positions"):
            notes.append({"source": "commodities", "code": "silver_unavailable", "level": "warn", "msg": "Gümüş anlık fiyatı alınamadı"})
    notes += await _manual_crypto_notes(user_id, db, sections)
    return notes


async def _do_refresh(user_id, session_factory: async_sessionmaker) -> None:
    """Tek bir refresh turunu yürütür (kendi session'ında). Hata yutulur — best-effort."""
    async with session_factory() as db:
        try:
            await _set_status_refreshing(db, user_id)
        except Exception:
            logger.exception("Live cache: status=refreshing yazılamadı user_id=%s", user_id)
            return

    rates: dict[str, Any] | None = None
    try:
        usd_tl = await fetch_usd_to_tl()
        rates = {"usd_tl": str(usd_tl)}
    except Exception:
        logger.warning("Live cache: USD/TL kuru alınamadı user_id=%s", user_id)

    async with session_factory() as db:
        try:
            # _gather_sections her bölüme AYRI session açar (aynı session'da
            # eşzamanlı execute → "another operation is in progress" bug'ı).
            sections, total_tl, issues = await asyncio.wait_for(
                _gather_sections(user_id, session_factory),
                timeout=_REFRESH_TOTAL_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("Live cache: refresh toplam süre aşıldı user_id=%s", user_id)
            await _mark_error(session_factory, user_id, "Yenileme zaman aşımına uğradı.")
            return
        except Exception:
            logger.exception("Live cache: refresh sırasında hata user_id=%s", user_id)
            await _mark_error(session_factory, user_id, "Yenileme sırasında bir hata oluştu.")
            return

        # Tüm bölümler patladıysa hata; refreshed_at korunur (eski veri gösterilsin).
        all_failed = len(issues) >= 6
        # Veri-kalitesi notları (hisse stale / emtia / manuel kripto linked) — section+DB'den
        # türetilir (yeniden çekim yok). health_issues'a eklenir → snapshot modal + kayıt (sarı ünlem).
        if not all_failed:
            try:
                issues = issues + await _derive_section_notes(user_id, db, sections)
            except Exception:
                logger.exception("Live cache: veri-kalitesi notları türetilemedi user_id=%s", user_id)
        try:
            await _save_result(
                db,
                user_id,
                payload=sections,
                total_value_tl=total_tl,
                rates=rates,
                health_issues=issues or None,
                status="error" if all_failed else "ok",
                error="Tüm veri kaynakları geçici olarak erişilemez." if all_failed else None,
                update_refreshed_at=not all_failed,
            )
        except Exception:
            logger.exception("Live cache: sonuç yazılamadı user_id=%s", user_id)


async def _mark_error(session_factory: async_sessionmaker, user_id, message: str) -> None:
    """Refresh tamamen başarısız olduğunda status='error' yazar (refreshed_at korunur)."""
    async with session_factory() as db:
        existing = await get_live_cache(user_id, db)
        payload = existing.payload if existing else {}
        try:
            await _save_result(
                db,
                user_id,
                payload=payload,
                total_value_tl=existing.total_value_tl if existing else None,
                rates=existing.rates if existing else None,
                health_issues=existing.health_issues if existing else None,
                status="error",
                error=message,
                update_refreshed_at=False,
            )
        except Exception:
            logger.exception("Live cache: error durumu yazılamadı user_id=%s", user_id)


async def refresh_live_cache(
    user_id,
    session_factory: async_sessionmaker = AsyncSessionLocal,
    *,
    force: bool = False,
) -> None:
    """Kullanıcının canlı portföy cache'ini yeniden hesaplar.

    - force=False + mevcut satır taze (live_cache_stale_minutes içinde) → no-op.
    - In-process single-flight: aynı kullanıcı için refresh koşuyorsa o task beklenir.
    """
    key = str(user_id)

    # Taze cache + force değilse → no-op (gereksiz dış-API çağrısı yok).
    if not force:
        async with session_factory() as db:
            row = await get_live_cache(user_id, db)
        if row is not None and not is_stale(row, settings.live_cache_stale_minutes):
            return

    existing = _REFRESH_TASKS.get(key)
    if existing is not None and not existing.done():
        await existing
        return

    task = asyncio.ensure_future(_do_refresh(user_id, session_factory))
    _REFRESH_TASKS[key] = task

    def _cleanup(_t: asyncio.Task, k: str = key) -> None:
        if _REFRESH_TASKS.get(k) is _t:
            _REFRESH_TASKS.pop(k, None)

    task.add_done_callback(_cleanup)
    await task


def trigger_refresh_after_login(user_id) -> None:
    """Login/MFA-verify sonrası best-effort canlı cache tetikleme.

    `live_cache_refresh_on_login` gate'i + hata yutma tek yerde — endpoint'ler
    (auth.login, mfa.verify) bu tek satırı çağırır (cognitive complexity düşük kalır).
    """
    if not settings.live_cache_refresh_on_login:
        return
    try:
        trigger_background_refresh(user_id, force=False)
    except Exception:
        logger.warning("Login sonrası canlı cache tetiklenemedi user_id=%s", user_id)


def trigger_background_refresh(user_id, *, force: bool = False) -> None:
    """Best-effort fire-and-forget refresh (login/endpoint'ten çağrılır).

    Çalışan event loop yoksa (ör. sync test bağlamı) sessizce no-op. Task
    referansı _BG_TASKS'ta tutulur (GC engeli), bitince temizlenir.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(refresh_live_cache(user_id, force=force))
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)


# ---------------------------------------------------------------------------
# Tek-bölüm (per-kart) yenileme
# ---------------------------------------------------------------------------
# Dashboard'da tek bir kartın (cüzdan/kripto/TEFAS/hisse/emtia/manuel kripto)
# "yenile" ikonu: yalnız o bölümü yeniden hesaplar + cache payload'unu yamalar
# (diğer bölümlere dokunmaz). Tüm portföyü yeniden çekmeden hızlı retry sağlar.
VALID_SECTIONS: tuple[str, ...] = ("wallets", "crypto", "tefas", "stocks", "commodities", "manual_crypto")

# Tek-bölüm single-flight: aynı (user, section) için aynı anda tek refresh.
_SECTION_TASKS: dict[str, asyncio.Task] = {}


def _section_computer(section: str):
    """Bölüm adından compute_* fonksiyonunu döner (geç import — döngü engeli)."""
    from app.api.v1.commodity import compute_commodities
    from app.api.v1.manual_crypto import compute_manual_crypto
    from app.api.v1.portfolio import compute_crypto_positions, compute_wallet_positions
    from app.api.v1.stocks import compute_stock_positions
    from app.api.v1.tefas import compute_tefas_positions

    return {
        "wallets": compute_wallet_positions,
        "crypto": compute_crypto_positions,
        "tefas": compute_tefas_positions,
        "stocks": compute_stock_positions,
        "commodities": compute_commodities,
        "manual_crypto": compute_manual_crypto,
    }.get(section)


async def refresh_one_section(user_id, section: str, session_factory: async_sessionmaker = AsyncSessionLocal) -> None:
    """Tek bir bölümü yeniden hesaplar ve cache payload'unun yalnız o anahtarını yamalar.

    Diğer bölümler ve health_issues'ları korunur (yalnız bu bölümün notları yenilenir);
    toplam (`total_value_tl`) tüm bölümlerden yeniden toplanır. `refreshed_at` güncellenir.
    """
    computer = _section_computer(section)
    if computer is None:
        return

    encoded: Any
    try:
        async with session_factory() as section_db:
            res = await asyncio.wait_for(computer(user_id, section_db), timeout=_REFRESH_TOTAL_TIMEOUT)
        encoded = jsonable_encoder(res)
        if isinstance(encoded, list):
            encoded = {"positions": encoded}
        failed = False
    except Exception as exc:
        # Best-effort: hata yutulur, cache'e "section_failed" notu olarak yansır.
        logger.error("Live cache: tek bölüm '%s' yenilenemedi user_id=%s: %r", section, user_id, exc, exc_info=exc)
        encoded = _empty_section(section)
        failed = True

    async with session_factory() as db:
        existing = await get_live_cache(user_id, db)
        payload = dict(existing.payload) if existing and existing.payload else {}
        payload[section] = encoded
        total = _sum_sections_total(payload)
        # Diğer bölümlerin notlarını koru; bu bölümünkileri yenile.
        prior = [i for i in (existing.health_issues or []) if i.get("source") != section] if existing else []
        section_notes: list[dict[str, Any]] = []
        if failed:
            section_notes.append({"source": section, "code": "section_failed", "msg": "Bu bölüm geçici olarak hesaplanamadı.", "level": "warn"})
        else:
            try:
                derived = await _derive_section_notes(user_id, db, payload)
                section_notes = [n for n in derived if n.get("source") == section]
            except Exception:
                logger.exception("Live cache: tek bölüm '%s' notları türetilemedi user_id=%s", section, user_id)
        issues = prior + section_notes
        try:
            await _save_result(
                db,
                user_id,
                payload=payload,
                total_value_tl=total,
                rates=existing.rates if existing else None,
                health_issues=issues or None,
                status="ok",
                error=None,
                update_refreshed_at=True,
            )
        except Exception:
            logger.exception("Live cache: tek bölüm '%s' sonucu yazılamadı user_id=%s", section, user_id)


def trigger_section_refresh(user_id, section: str) -> None:
    """Best-effort fire-and-forget tek-bölüm yenileme (per-kart yenile ikonu).

    Aynı (user, section) için koşan task varsa yenisini başlatmaz (single-flight)."""
    if section not in VALID_SECTIONS:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    key = f"{user_id}:{section}"
    existing = _SECTION_TASKS.get(key)
    if existing is not None and not existing.done():
        return
    task = loop.create_task(refresh_one_section(user_id, section))
    _SECTION_TASKS[key] = task

    def _cleanup(_t: asyncio.Task, k: str = key) -> None:
        if _SECTION_TASKS.get(k) is _t:
            _SECTION_TASKS.pop(k, None)

    task.add_done_callback(_cleanup)


# ---------------------------------------------------------------------------
# Cache → Snapshot
# ---------------------------------------------------------------------------
def _wallet_assets_from_cache(section: dict[str, Any]) -> list[AssetData]:
    out: list[AssetData] = []
    for p in _iter_section_positions(section):
        liquid = Decimal(str(p.get("liquid_quantity", "0")))
        staked = Decimal(str(p.get("staked_quantity", "0")))
        pending = Decimal(str(p.get("pending_rewards", "0")))
        out.append(
            AssetData(
                symbol=p["symbol"],
                name=p.get("label") or p["symbol"],
                provider=p.get("chain", "wallet"),
                asset_type="staked_crypto" if (staked + pending) > liquid else "crypto",
                source_type="blockchain",
                liquid_quantity=liquid,
                staked_quantity=staked,
                pending_rewards=pending,
                unit_price_usd=Decimal(str(p.get("unit_price_usd", "0"))),
                unit_price_tl=Decimal(str(p.get("unit_price_tl", "0"))),
                # wallet_address_id (FK) bilerek bağlanmaz: cache'teki wallet_id
                # snapshot anında hâlâ var olmayabilir (silinmiş cüzdan) → FK ihlali
                # riski. History wallet-attribution bu yoldan kritik değil; total/
                # pozisyon doğru. compute_and_save_snapshot fallback'i FK'yi korur.
                wallet_address_id=None,
            )
        )
    return out


def _crypto_assets_from_cache(section: dict[str, Any]) -> list[AssetData]:
    out: list[AssetData] = []
    for p in _iter_section_positions(section):
        liquid = Decimal(str(p.get("liquid_quantity", "0")))
        staked = Decimal(str(p.get("staked_quantity", "0")))
        out.append(
            AssetData(
                symbol=p["symbol"],
                name=p["symbol"],
                provider=p.get("provider", "exchange"),
                asset_type="staked_crypto" if staked > liquid else "crypto",
                source_type="exchange",
                liquid_quantity=liquid,
                staked_quantity=staked,
                unit_price_usd=Decimal(str(p.get("unit_price_usd", "0"))),
                unit_price_tl=Decimal(str(p.get("unit_price_tl", "0"))),
            )
        )
    return out


def _tefas_assets_from_cache(section: Any) -> list[AssetData]:
    out: list[AssetData] = []
    for p in _iter_section_positions(section):
        out.append(
            AssetData(
                symbol=p["code"],
                name=p.get("name", ""),
                provider="tefas",
                asset_type="fund",
                source_type="exchange",
                liquid_quantity=Decimal(str(p.get("quantity", "0"))),
                unit_price_tl=Decimal(str(p.get("unit_price_tl", "0"))),
            )
        )
    return out


def _stock_assets_from_cache(section: Any) -> list[AssetData]:
    out: list[AssetData] = []
    for p in _iter_section_positions(section):
        out.append(
            AssetData(
                symbol=p["ticker"],
                name=p.get("name", ""),
                provider="stock",
                asset_type="stock",
                source_type="stock",
                liquid_quantity=Decimal(str(p.get("quantity", "0"))),
                unit_price_tl=Decimal(str(p.get("unit_price_tl", "0"))),
            )
        )
    return out


def _commodity_assets_from_cache(section: Any) -> list[AssetData]:
    out: list[AssetData] = []
    for p in _iter_section_positions(section):
        value_tl = Decimal(str(p.get("total_value_tl", "0")))
        if value_tl <= 0:
            continue
        # Snapshot konvansiyonu: liquid_quantity=1, unit_price_tl=toplam değer
        out.append(
            AssetData(
                symbol="XAU" if p.get("metal") == "gold" else "XAG",
                name=p.get("metal", "commodity"),
                provider="commodity",
                asset_type="commodity",
                source_type="manual",
                liquid_quantity=Decimal("1"),
                unit_price_tl=value_tl,
            )
        )
    return out


def _manual_crypto_assets_from_cache(section: Any) -> list[AssetData]:
    out: list[AssetData] = []
    for p in _iter_section_positions(section):
        out.append(
            AssetData(
                symbol=p["symbol"],
                name=p.get("label") or f"{p.get('exchange', '')} {p['symbol']}".strip(),
                provider=f"manual:{p.get('exchange', '')}",
                asset_type="crypto",
                source_type="manual",
                liquid_quantity=Decimal(str(p.get("quantity", "0"))),
                unit_price_tl=Decimal(str(p.get("unit_price_tl", "0"))),
            )
        )
    return out


def _assets_from_cache(sections: dict[str, Any]) -> list[AssetData]:
    """Cache sections'ı snapshot için AssetData listesine çevirir.

    Snapshot servisindeki (snapshot.py) provider/asset_type/source_type
    konvansiyonlarıyla birebir uyumlu.
    """
    return (
        _wallet_assets_from_cache(sections.get("wallets", {}))
        + _crypto_assets_from_cache(sections.get("crypto", {}))
        + _tefas_assets_from_cache(sections.get("tefas", []))
        + _stock_assets_from_cache(sections.get("stocks", []))
        + _commodity_assets_from_cache(sections.get("commodities", {}))
        + _manual_crypto_assets_from_cache(sections.get("manual_crypto", {}))
    )


def _cache_issues(cache: LivePortfolioCache) -> list[dict[str, Any]]:
    """Cache'teki TÜM sorunları tek issue listesine toplar: bölüm-seviyesi
    (health_issues) + çekilemeyen cüzdan zincirleri (wallets.errors) + borsa
    hataları (crypto.errors). Snapshot preview/save bunu kullanır → kullanıcı
    'şu veriler eksik, yine de kaydet?' uyarısını görür (BTC timeout vb.)."""
    issues: list[dict[str, Any]] = list(cache.health_issues or [])
    payload = cache.payload or {}
    for key, msg in ((payload.get("wallets") or {}).get("errors") or {}).items():
        if key == "_timeout":
            continue
        issues.append({"source": "wallet", "chain": key.split(":")[0], "code": "fetch_failed", "msg": str(msg), "level": "warn"})
    for key, msg in ((payload.get("crypto") or {}).get("errors") or {}).items():
        issues.append({"source": "crypto", "provider": key, "code": "fetch_failed", "msg": str(msg), "level": "warn"})
    return issues


def _usd_tl_from_cache(cache: LivePortfolioCache) -> Decimal:
    """Cache.rates'ten usd_tl Decimal (yoksa/parse hatasında 0)."""
    if cache.rates and cache.rates.get("usd_tl"):
        try:
            return Decimal(str(cache.rates["usd_tl"]))
        except (ValueError, ArithmeticError):
            return Decimal(0)
    return Decimal(0)


def _sum_asset_total(assets: list[AssetData], usd_tl: Decimal) -> Decimal:
    """Tüm asset'lerin TL toplamı (compute_and_save_snapshot ile aynı formül)."""
    total = Decimal(0)
    for a in assets:
        price_tl = a.unit_price_tl if a.unit_price_tl > 0 else a.unit_price_usd * usd_tl
        qty = a.liquid_quantity + a.staked_quantity + a.pending_rewards
        total += qty * price_tl
    return total.quantize(Decimal("0.01"))


async def _db_only_assets(user_id, db: AsyncSession, usd_tl: Decimal, issues: list[dict[str, Any]]) -> tuple[list[AssetData], Decimal]:
    """BES + Nakit (live cache'te olmayan DB-only kartlar) → (assets, usd_tl).

    usd_tl ≤0 ise (cash dönüşümü için) TCMB'den çekilir. Dış API yok dışında —
    TCMB usd/rates 5 dk cache'li.
    """
    from app.models.bes import BesHolding
    from app.models.cash import CashHolding
    from app.services.aggregator import fetch_tcmb_rates, fetch_usd_to_tl
    from app.services.snapshot import _gather_bes_assets, _gather_cash_assets

    bes_holdings = (await db.execute(select(BesHolding).where(BesHolding.user_id == user_id))).scalars().all()
    cash_holdings = (await db.execute(select(CashHolding).where(CashHolding.user_id == user_id))).scalars().all()
    if not (bes_holdings or cash_holdings):
        return [], usd_tl
    if usd_tl <= 0:
        try:
            usd_tl = await fetch_usd_to_tl()
        except Exception:
            usd_tl = Decimal(0)
    extras = list(_gather_bes_assets(bes_holdings))
    if cash_holdings:
        try:
            tcmb_rates = await fetch_tcmb_rates()
        except Exception:
            tcmb_rates = {}
        extras += await _gather_cash_assets(cash_holdings, usd_tl, tcmb_rates, issues)
    return extras, usd_tl


async def _full_snapshot_assets(user_id, db: AsyncSession, cache: LivePortfolioCache) -> tuple[list[AssetData], Decimal, Decimal, list[dict[str, Any]]]:
    """Cache'in 6 ağır bölümü + DB-only BES/Nakit → (assets, total_tl, usd_tl, issues).

    Snapshot preview + save ORTAK kullanır → ikisi de TAM (BES/Nakit dahil) ve
    tutarlı toplam üretir. BES/Nakit eklenmezse snapshot bunları 0 kaydederdi.
    """
    assets = list(_assets_from_cache(cache.payload or {}))
    issues = _cache_issues(cache)
    usd_tl = _usd_tl_from_cache(cache)
    extras, usd_tl = await _db_only_assets(user_id, db, usd_tl, issues)
    assets += extras
    return assets, _sum_asset_total(assets, usd_tl), usd_tl, issues


async def preview_snapshot_from_cache(user_id, db: AsyncSession) -> dict[str, Any]:
    """Taze live cache'ten snapshot ön-izlemesi (yeniden dış çağrı YOK → hızlı).

    compute_and_save_snapshot(dry_run=True) ile AYNI sözleşme:
    {total_value_tl, asset_count, issues, usd_try_rate, saved}. Snapshot preview
    eskiden 45 sn full re-fetch yapıp frontend 30 sn timeout'una takılıyordu →
    onay modal'ı açılmıyordu. Cache'ten (+ BES/Nakit) anında döner.
    """
    cache = await get_live_cache(user_id, db)
    if cache is None:
        raise ValueError("Live cache bulunamadı")
    assets, total_tl, usd_tl, issues = await _full_snapshot_assets(user_id, db, cache)
    return {
        "total_value_tl": str(total_tl),
        "asset_count": len(assets),
        "issues": issues,
        "usd_try_rate": str(usd_tl) if usd_tl > 0 else None,
        "saved": False,
    }


async def save_snapshot_from_cache(user_id, db: AsyncSession) -> PortfolioSnapshot:
    """Taze live cache'ten yeniden dış çağrı yapmadan PortfolioSnapshot üretir.

    Aynı güne ait snapshot varsa silinip yenilenir (compute_and_save_snapshot ile
    aynı idempotent/aynı-gün-replace mantığı). usd_try_rate + health_issues + total
    cache'ten gelir.

    Çağıran taze cache olduğunu (is_stale=False) garanti etmelidir; bayat/yoksa
    compute_and_save_snapshot fallback'i kullanılmalı.
    """
    from datetime import date as _date
    from zoneinfo import ZoneInfo

    cache = await get_live_cache(user_id, db)
    if cache is None:
        raise ValueError("Live cache bulunamadı")

    today: _date = datetime.now(ZoneInfo("Europe/Istanbul")).date()

    # Aynı güne ait mevcut snapshot'ı temizle (cascade ile asset_positions da silinir)
    existing_q = await db.execute(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.snapshot_date == today,
        )
    )
    for old in existing_q.scalars().all():
        await db.delete(old)
    await db.flush()

    # 6 ağır bölüm + DB-only BES/Nakit (ortak helper → preview ile tutarlı, TAM).
    assets, total_tl, usd_tl, snap_issues = await _full_snapshot_assets(user_id, db, cache)

    snapshot = PortfolioSnapshot(
        user_id=user_id,
        snapshot_date=today,
        total_value_tl=total_tl,
        usd_try_rate=usd_tl.quantize(Decimal("0.000001")) if usd_tl > 0 else None,
        health_issues=snap_issues or None,
    )
    db.add(snapshot)
    await db.flush()

    for asset in assets:
        pos: AssetPosition = to_asset_position(asset, snapshot.id, usd_tl, total_tl)
        db.add(pos)

    await db.commit()
    await db.refresh(snapshot)
    logger.info(
        "Snapshot cache'ten olusturuldu: user_id=%s, total_tl=%s, asset=%d",
        user_id,
        snapshot.total_value_tl,
        len(assets),
    )
    return snapshot
