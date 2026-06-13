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
    db: AsyncSession,
) -> tuple[dict[str, Any], Decimal, list[dict[str, Any]]]:
    """6 compute_* fonksiyonunu paralel çalıştırır; (sections, total_tl, issues) döner.

    Patlayan bölüm health_issues'a kaydedilir + sections'ta boş bırakılır
    (diğer bölümler etkilenmez).
    """
    # Geç import — modül seviyesinde import portfolio router'ı yüklerken döngü riski.
    from app.api.v1.commodity import compute_commodities
    from app.api.v1.manual_crypto import compute_manual_crypto
    from app.api.v1.portfolio import compute_crypto_positions, compute_wallet_positions
    from app.api.v1.stocks import compute_stock_positions
    from app.api.v1.tefas import compute_tefas_positions

    section_specs = [
        ("wallets", compute_wallet_positions(user_id, db)),
        ("crypto", compute_crypto_positions(user_id, db)),
        ("tefas", compute_tefas_positions(user_id, db)),
        ("stocks", compute_stock_positions(user_id, db)),
        ("commodities", compute_commodities(user_id, db)),
        ("manual_crypto", compute_manual_crypto(user_id, db)),
    ]
    names = [name for name, _ in section_specs]
    results = await asyncio.gather(*(coro for _, coro in section_specs), return_exceptions=True)

    sections: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []
    for name, res in zip(names, results):
        if isinstance(res, BaseException):
            logger.exception("Live cache: '%s' bölümü hesaplanamadı user_id=%s", name, user_id)
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
            sections[name] = jsonable_encoder(res)

    total_tl = _sum_sections_total(sections)
    return sections, total_tl, issues


def _empty_section(name: str) -> Any:
    """Patlayan bölüm için boş ama şekil-uyumlu placeholder."""
    if name in ("wallets", "crypto"):
        return {"positions": [], "errors": {}}
    if name in ("tefas", "stocks"):
        return []
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
            sections, total_tl, issues = await asyncio.wait_for(
                _gather_sections(user_id, db),
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

    sections = cache.payload or {}
    assets = _assets_from_cache(sections)

    usd_tl = Decimal(0)
    if cache.rates and cache.rates.get("usd_tl"):
        try:
            usd_tl = Decimal(str(cache.rates["usd_tl"]))
        except (ValueError, ArithmeticError):
            usd_tl = Decimal(0)

    total_tl = cache.total_value_tl if cache.total_value_tl is not None else _sum_sections_total(sections)

    snapshot = PortfolioSnapshot(
        user_id=user_id,
        snapshot_date=today,
        total_value_tl=Decimal(str(total_tl)).quantize(Decimal("0.01")),
        usd_try_rate=usd_tl.quantize(Decimal("0.000001")) if usd_tl > 0 else None,
        health_issues=cache.health_issues if cache.health_issues else None,
    )
    db.add(snapshot)
    await db.flush()

    for asset in assets:
        pos: AssetPosition = to_asset_position(asset, snapshot.id, usd_tl, Decimal(str(total_tl)))
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
