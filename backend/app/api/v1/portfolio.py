import asyncio
import logging
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.core.security import decrypt_secret
from app.models.integration import Integration, WalletAddress
from app.models.portfolio import PortfolioSnapshot
from app.models.user import User
from app.schemas.live_cache import LivePortfolioOut, RefreshAcceptedOut
from app.schemas.portfolio import (
    CryptoPositionOut,
    CryptoResponse,
    PortfolioBreakdown,
    PortfolioChanges,
    SnapshotOut,
    SnapshotPreviewOut,
    StakingPosition,
    WalletPositionOut,
    WalletResponse,
)
from app.services import currency as currency_svc
from app.services.aggregator import fetch_combined_prices, fetch_usd_to_tl, lookup_usd_price
from app.services.audit import AuditAction, log_audit
from app.services.blockchain.algorand import AlgorandService
from app.services.blockchain.avalanche import AvalancheCChainService, AvalanchePChainService
from app.services.blockchain.bitcoin import BitcoinService
from app.services.blockchain.cardano import CardanoService
from app.services.blockchain.ethereum import EthereumService
from app.services.blockchain.litecoin import LitecoinService
from app.services.blockchain.polkadot import PolkadotService
from app.services.blockchain.solana import SolanaService
from app.services.blockchain.sonic import SonicService
from app.services.concurrency import gather_bounded
from app.services.exchange.binance import BinanceService
from app.services.exchange.binancetr import BinanceTRService
from app.services.exchange.icrypex import ICrypexService
from app.services.live_cache import (
    VALID_SECTIONS,
    get_live_cache,
    is_stale,
    preview_snapshot_from_cache,
    save_snapshot_from_cache,
    trigger_background_refresh,
    trigger_section_refresh,
    trigger_wallet_refresh,
)
from app.services.snapshot import compute_and_save_snapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_NO_PORTFOLIO_DATA = "Henüz portföy verisi yok"

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Zincir adı → blockchain servis sınıfı eşlemesi (cüzdan pozisyon çekimi)
_WALLET_SERVICES = {
    "sonic": SonicService,
    "avalanche_p": AvalanchePChainService,
    "avalanche_c": AvalancheCChainService,
    "ethereum": EthereumService,
    "bitcoin": BitcoinService,
    "solana": SolanaService,
    "litecoin": LitecoinService,
    "algorand": AlgorandService,
    "cardano": CardanoService,
    "polkadot": PolkadotService,
}


@router.get("/usd-rate")
async def get_usd_rate(
    _: CurrentUser,
):
    """Anlık USD/TRY kuru (TCMB → Yahoo Finance fallback). Frontend USD karşılığı
    göstermek için kullanır. 5 dk in-memory cache (aggregator katmanında)."""
    rate = await fetch_usd_to_tl()
    return {"usd_try": str(rate)}


@router.get("/rates")
async def get_rates(
    _: CurrentUser,
):
    """Desteklenen tüm para birimleri için 1 birim = X TL kur haritası (v0.3.0).

    Frontend görüntüleme para birimi (display currency) dönüşümü için: bir TL
    tutarı seçili para birimine çevirirken `tl / rates[currency]` kullanır.
    `currency_svc.fetch_rates()` (TCMB, TRY=1, eksik kur USD fallback, 5 dk cache)."""
    rates = await currency_svc.fetch_rates()
    return {"rates": {k: str(v) for k, v in rates.items()}}


@router.get("/live", response_model=LivePortfolioOut)
async def get_live_portfolio(
    current_user: CurrentUser,
    db: DbSession,
):
    """Sunucu-tarafı canlı portföy cache'ini döner (hızlı DB okuması).

    Dashboard + detay sayfaları her açılışta dış-API çağrısı yapmak yerine
    bu cache'i okur. Davranış:
    - Cache satırı YOKSA: arka planda refresh tetiklenir, status='refreshing'
      + boş sections döner (BLOKE ETMEZ — frontend kısa süre sonra tekrar çeker).
    - Cache varsa: satır döner; bayatsa (live_cache_stale_minutes dışında) arka
      planda refresh tetiklenir (stale-while-revalidate) ama mevcut veri hemen döner.
    """
    row = await get_live_cache(current_user.id, db)
    stale_minutes = settings.live_cache_stale_minutes

    if row is None:
        trigger_background_refresh(current_user.id)
        return LivePortfolioOut(
            status="refreshing",
            refreshed_at=None,
            stale=True,
            total_value_tl=None,
            rates=None,
            health_issues=None,
            error=None,
            sections={},
        )

    stale = is_stale(row, stale_minutes)
    if stale:
        # Stale-while-revalidate: eski veriyi hemen dön, arka planda tazele.
        trigger_background_refresh(current_user.id)

    return LivePortfolioOut(
        status=row.status,
        refreshed_at=row.refreshed_at,
        stale=stale,
        total_value_tl=row.total_value_tl,
        rates=row.rates,
        health_issues=row.health_issues,
        error=row.error,
        sections=row.payload or {},
    )


@router.post("/refresh", response_model=RefreshAcceptedOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/hour")
async def refresh_live_portfolio(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    force: bool = False,
):
    """Canlı portföy cache'ini arka planda yeniden hesaplatır (fire-and-forget).

    202 + mevcut cache durumunu döner. `force=true` taze cache'i de yeniden
    hesaplar (kullanıcı "Yenile" butonu). force=false taze cache'i no-op geçer.
    """
    trigger_background_refresh(current_user.id, force=force)
    row = await get_live_cache(current_user.id, db)
    return RefreshAcceptedOut(
        status="refreshing",
        refreshed_at=row.refreshed_at if row else None,
    )


@router.post("/refresh/{section}", response_model=RefreshAcceptedOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("60/hour")
async def refresh_one_portfolio_section(
    request: Request,
    section: str,
    current_user: CurrentUser,
    db: DbSession,
):
    """Tek bir portföy bölümünü (kartı) arka planda yeniden hesaplatır (per-kart yenile).

    `section ∈ {wallets, crypto, tefas, stocks, commodities, manual_crypto}`. Yalnız o
    bölüm yeniden çekilir + cache'in o anahtarı yamalanır; diğer kartlar etkilenmez.
    202 + mevcut cache durumunu döner (frontend poll ile günceller).
    """
    if section not in VALID_SECTIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geçersiz bölüm")
    trigger_section_refresh(current_user.id, section)
    row = await get_live_cache(current_user.id, db)
    return RefreshAcceptedOut(
        status="refreshing",
        refreshed_at=row.refreshed_at if row else None,
    )


@router.post("/refresh/wallet/{wallet_id}", response_model=RefreshAcceptedOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("60/hour")
async def refresh_one_wallet_endpoint(
    request: Request,
    wallet_id: str,
    current_user: CurrentUser,
    db: DbSession,
):
    """Tek bir cüzdanı arka planda yeniden hesaplatır (per-cüzdan yenile ikonu).

    Cüzdan kullanıcıya ait + aktif değilse 404 (IDOR koruması). Yalnız o cüzdanın
    pozisyonları wallets cache section'ında yamalanır; diğer cüzdanlar/kartlar
    etkilenmez. 202 + mevcut cache durumunu döner (frontend poll ile günceller).
    """
    result = await db.execute(
        select(WalletAddress.id).where(
            WalletAddress.id == wallet_id,
            WalletAddress.user_id == current_user.id,
            WalletAddress.is_active.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cüzdan bulunamadı")
    trigger_wallet_refresh(current_user.id, wallet_id)
    row = await get_live_cache(current_user.id, db)
    return RefreshAcceptedOut(
        status="refreshing",
        refreshed_at=row.refreshed_at if row else None,
    )


@router.post("/snapshot/preview", response_model=SnapshotPreviewOut)
@limiter.limit("6/hour")
async def preview_snapshot(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
):
    """Snapshot öncesi sağlık kontrolü.

    Toplam + issues döndürür ama **DB'ye yazmaz**. Frontend bunu kullanır:
    issue varsa kullanıcıya popup gösterip onay alır; onay sonrası
    `POST /portfolio/snapshot` (force=True) ile gerçek kayıt.

    Performans (KRİTİK): taze live cache varsa ön-izleme CACHE'ten anında
    üretilir (yeniden dış çağrı YOK). Eskiden full re-fetch ~45 sn sürüp
    frontend 30 sn timeout'una takılıyordu → onay modal'ı hiç açılmıyordu.
    Cache yok/bayatsa compute_and_save_snapshot(dry_run) fallback'i.
    """
    # Cache VARSA (bayat olsa bile) ondan üret — snapshot = ekranda görünen durum
    # (dashboard zaten cache'i "son güncelleme" göstergesiyle gösterir). Bayatlık
    # kontrolü kaldırıldı: bayat cache 45 sn full re-fetch yoluna düşüp frontend
    # 30 sn timeout'una takılıyordu → modal açılmıyor/kayıt olmuyordu. Taze isterse
    # kullanıcı önce "Yenile" yapar. Cache HİÇ yoksa compute fallback.
    cache_row = await get_live_cache(current_user.id, db)
    if cache_row is not None:
        try:
            return await preview_snapshot_from_cache(current_user.id, db)
        except Exception:
            logger.exception("Snapshot preview cache'ten üretilemedi, compute fallback user_id=%s", current_user.id)

    try:
        result = await compute_and_save_snapshot(current_user.id, db, dry_run=True)
    except RuntimeError:
        # SEC-007 (FAZ H): RuntimeError mesaji internal (USD/TL fetch fail vs.)
        # bilgi sizdirabilir. Full trace ops log'a; client'a generic mesaj.
        logger.exception("Snapshot preflight failed user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snapshot ön kontrolü şu an yapılamıyor. Bazı veri kaynakları geçici olarak erişilemez.",
        )
    # dry_run=True her zaman dict döner, asla DB'ye yazmaz
    return result


@router.post("/snapshot", response_model=SnapshotOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("6/hour")
async def create_snapshot(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    force: bool = False,
):
    """Mevcut kullanici icin manuel olarak portfoy snapshot'i alir.

    Otomatik haftalik job (Pazar 23:00) ile ayni mantigi calistirir; ayni gun
    icinde tekrar cagrilirsa eski snapshot silinip yenisi olusturulur.

    `force=true` query parametresi: kullanıcı uyarıları onayladıktan sonra
    bu endpoint çağrılır. force=false (varsayılan) için preview endpoint'i
    önce çağrılmalı; issue varsa popup'ta onay alınır.

    Performans: canlı portföy cache (live_portfolio_cache) VARSA snapshot yeniden
    dış-API çağrısı yapılmadan o cache'ten üretilir (ekranda görünen durum; bayat
    olsa bile — preview ile tutarlı, 45 sn timeout yolu kapalı). Cache HİÇ yoksa
    klasik compute_and_save_snapshot fallback'i.
    """
    cache_row = await get_live_cache(current_user.id, db)
    if cache_row is not None:
        try:
            snapshot = await save_snapshot_from_cache(current_user.id, db)
            result = await db.execute(
                select(PortfolioSnapshot).where(PortfolioSnapshot.id == snapshot.id).options(selectinload(PortfolioSnapshot.asset_positions))
            )
            return result.scalar_one()
        except Exception:
            # Cache'ten snapshot üretilemezse klasik yola düş (veri kaybı olmasın).
            logger.exception("Snapshot cache'ten üretilemedi, compute fallback user_id=%s", current_user.id)
            await db.rollback()

    try:
        snapshot = await compute_and_save_snapshot(current_user.id, db, force=force)
    except RuntimeError:
        # SEC-007 (FAZ H): RuntimeError mesaji internal bilgi sizdirabilir.
        logger.exception("Snapshot save failed user_id=%s force=%s", current_user.id, force)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snapshot kaydedilemedi. Lütfen birkaç dakika sonra tekrar deneyin.",
        )
    # BACK-001 (FAZ H): dry_run=False oldugu icin compute_and_save_snapshot her zaman
    # PortfolioSnapshot doner. dict fallback dual-type response_model'i bypass ediyordu;
    # kaldirildi — `dry_run=True` ayri preview endpoint'inde kullaniliyor.
    # Asset position'lari donulen response icin tekrar yukle
    result = await db.execute(select(PortfolioSnapshot).where(PortfolioSnapshot.id == snapshot.id).options(selectinload(PortfolioSnapshot.asset_positions)))
    return result.scalar_one()


@router.delete("/snapshot/{snapshot_date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snapshot(
    snapshot_date: date,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
):
    """Belirli bir tarihteki snapshot'i siler. Yanlış kaydedilmiş (ör. timezone)
    snapshot'ları temizlemek için. Cascade ile asset_positions da silinir."""
    result = await db.execute(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == current_user.id,
            PortfolioSnapshot.snapshot_date == snapshot_date,
        )
    )
    snap = result.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot bulunamadı")
    await db.delete(snap)
    await log_audit(
        db,
        request,
        action=AuditAction.SNAPSHOT_DELETE,
        user_id=current_user.id,
        resource=f"snapshot:{snapshot_date.isoformat()}",
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Snapshot rapor indirme (Excel + PDF)
# ---------------------------------------------------------------------------
async def _load_snapshot_with_positions(snapshot_date: date, current_user: User, db: AsyncSession):
    """Verilen tarihteki snapshot'i pozisyonlarıyla birlikte yükler."""
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(
            PortfolioSnapshot.user_id == current_user.id,
            PortfolioSnapshot.snapshot_date == snapshot_date,
        )
        .options(selectinload(PortfolioSnapshot.asset_positions))
    )
    snap = result.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot bulunamadı")
    return snap


@router.get("/snapshot/{snapshot_date}/report.xlsx")
async def download_snapshot_xlsx(
    snapshot_date: date,
    current_user: CurrentUser,
    db: DbSession,
):
    """Belirli bir tarihteki snapshot için Excel raporu (tüm pozisyonlar)."""
    from app.services.reports import snapshot_to_xlsx

    snap = await _load_snapshot_with_positions(snapshot_date, current_user, db)
    content = snapshot_to_xlsx(snap, list(snap.asset_positions))
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=portfoy-{snapshot_date.isoformat()}.xlsx"},
    )


@router.get("/snapshot/{snapshot_date}/report.pdf")
async def download_snapshot_pdf(
    snapshot_date: date,
    current_user: CurrentUser,
    db: DbSession,
):
    """Belirli bir tarihteki snapshot için PDF raporu."""
    from app.services.reports import snapshot_to_pdf

    snap = await _load_snapshot_with_positions(snapshot_date, current_user, db)
    content = snapshot_to_pdf(snap, list(snap.asset_positions))
    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=portfoy-{snapshot_date.isoformat()}.pdf"},
    )


@router.get("", response_model=SnapshotOut)
async def get_current_portfolio(
    current_user: CurrentUser,
    db: DbSession,
):
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_PORTFOLIO_DATA)
    return snapshot


@router.get("/history", response_model=list[SnapshotOut])
async def get_portfolio_history(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = 12,
    year: int | None = None,
):
    """Snapshot geçmişi.

    `year` verilirse o yılın tüm snapshot'ları döner (limit yine de uygulanır).
    `year` boşsa en son N snapshot.
    """
    stmt = (
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
    )
    if year is not None:
        stmt = stmt.where(
            PortfolioSnapshot.snapshot_date >= date(year, 1, 1),
            PortfolioSnapshot.snapshot_date <= date(year, 12, 31),
        )
    result = await db.execute(stmt.limit(limit))
    return result.scalars().all()


@router.get("/history/years", response_model=list[int])
async def get_portfolio_history_years(
    current_user: CurrentUser,
    db: DbSession,
):
    """Kullanıcının snapshot'larının olduğu yılların listesi (yeni → eski)."""
    from sqlalchemy import extract

    result = await db.execute(
        select(extract("year", PortfolioSnapshot.snapshot_date).label("y"))
        .where(PortfolioSnapshot.user_id == current_user.id)
        .group_by("y")
        .order_by(desc("y"))
    )
    return [int(row[0]) for row in result.all()]


@router.get("/changes", response_model=PortfolioChanges)
async def get_portfolio_changes(
    current_user: CurrentUser,
    db: DbSession,
):
    result = await db.execute(
        select(PortfolioSnapshot).where(PortfolioSnapshot.user_id == current_user.id).order_by(desc(PortfolioSnapshot.snapshot_date)).limit(5)
    )
    snapshots = result.scalars().all()
    if not snapshots:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_PORTFOLIO_DATA)

    from app.services.aggregator import calculate_changes

    return calculate_changes(snapshots)


@router.get("/breakdown", response_model=PortfolioBreakdown)
async def get_portfolio_breakdown(
    current_user: CurrentUser,
    db: DbSession,
):
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_PORTFOLIO_DATA)

    from app.services.aggregator import calculate_breakdown

    return calculate_breakdown(snapshot)


async def compute_crypto_positions(user_id, db: AsyncSession) -> CryptoResponse:
    """Kullanıcının borsa entegrasyonları için canlı kripto pozisyonları.

    Endpoint (`GET /crypto`) + live cache refresh servisi ortak kullanır.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider.in_(["binance", "binancetr", "icrypex"]),
            Integration.is_active.is_(True),
        )
    )
    integrations = result.scalars().all()
    if not integrations:
        return CryptoResponse(positions=[], errors={})

    usd_tl = await fetch_usd_to_tl()
    all_assets = []
    errors: dict[str, str] = {}

    async def _fetch_integration(intg):
        """Tek borsa entegrasyonunu çeker → (assets, hata|None). Her borsa ayrı
        API olduğundan bounded-parallel güvenli (gather_bounded, limit=3)."""
        try:
            api_key = decrypt_secret(intg.encrypted_key)
            api_secret = decrypt_secret(intg.encrypted_secret) if intg.encrypted_secret else ""
            if intg.provider == "binance":
                svc = BinanceService(api_key, api_secret)
            elif intg.provider == "binancetr":
                session_token = decrypt_secret(intg.encrypted_extra) if intg.encrypted_extra else ""
                svc = BinanceTRService(api_key, api_secret, session_token)
            else:
                svc = ICrypexService(api_key, api_secret)
            return await svc.fetch(), None
        except Exception as e:
            logger.error("Kripto fetch hatası [%s]: %s", intg.provider, e)
            return [], (intg.provider, str(e))

    for assets, err in await gather_bounded(integrations, _fetch_integration, limit=3):
        all_assets.extend(assets)
        if err is not None:
            errors[err[0]] = err[1]

    positions = [
        CryptoPositionOut(
            provider=a.provider,
            symbol=a.symbol,
            liquid_quantity=a.liquid_quantity,
            staked_quantity=a.staked_quantity,
            unit_price_usd=a.unit_price_usd,
            unit_price_tl=(a.unit_price_usd * usd_tl).quantize(Decimal("0.01")),
            total_value_tl=((a.liquid_quantity + a.staked_quantity) * a.unit_price_usd * usd_tl).quantize(Decimal("0.01")),
        )
        for a in all_assets
    ]
    return CryptoResponse(positions=positions, errors=errors)


@router.get("/crypto", response_model=CryptoResponse)
async def get_crypto_positions(
    current_user: CurrentUser,
    db: DbSession,
):
    return await compute_crypto_positions(current_user.id, db)


async def _wallet_positions_for(wallets) -> WalletResponse:
    """Verilen cüzdan listesi için canlı pozisyonları hesaplar (ortak çekirdek).

    `compute_wallet_positions` (tüm aktif cüzdanlar) + `compute_single_wallet_positions`
    (tek cüzdan) ortak kullanır. Per-wallet + toplam deadline ile bounded
    (yavaş/ölü RPC kilitlemesin). Hatalar HEM `errors[chain:address[:10]]`
    (snapshot health parse formatı — DEĞİŞTİRME) HEM `wallet_errors[wallet_id]`
    (frontend per-cüzdan ⚠ uyarısı) altında raporlanır.
    """
    if not wallets:
        return WalletResponse(positions=[], errors={}, wallet_errors={})

    usd_tl, prices = await asyncio.gather(
        fetch_usd_to_tl(),
        fetch_combined_prices(
            [
                "S",
                "AVAX",
                "ETH",
                "BTC",
                "SOL",
                "ADA",
                "DOT",
                "ALGO",
                "LTC",
                "LINK",
                "USDT",
                "USDC",
            ]
        ),
    )

    all_positions: list[WalletPositionOut] = []
    errors: dict[str, str] = {}
    wallet_errors: dict[str, str] = {}

    def _build_position(wallet: WalletAddress, wid: str, a) -> WalletPositionOut:
        usd = lookup_usd_price(a.symbol, prices)
        # Snapshot ile tutarlı: pending_rewards da toplama dahil
        total_qty = a.liquid_quantity + a.staked_quantity + a.pending_rewards
        return WalletPositionOut(
            wallet_id=wid,
            chain=wallet.chain,
            address=wallet.address,
            label=wallet.label,
            symbol=a.symbol,
            liquid_quantity=a.liquid_quantity,
            staked_quantity=a.staked_quantity,
            pending_rewards=a.pending_rewards,
            unit_price_usd=usd,
            unit_price_tl=(usd * usd_tl).quantize(Decimal("0.01")),
            total_value_tl=(total_qty * usd * usd_tl).quantize(Decimal("0.01")),
        )

    async def fetch_wallet(wallet: WalletAddress) -> list[WalletPositionOut]:
        wid = str(wallet.id)
        svc_cls = _WALLET_SERVICES.get(wallet.chain)
        if svc_cls is None:
            return []
        # Test monkeypatch destegi: "app.api.v1.portfolio.<Service>" modul
        # attribute'u yamali ise import-time dict referansi yerine onu kullan.
        svc_cls = globals().get(svc_cls.__name__, svc_cls)
        key = f"{wallet.chain}:{wallet.address[:10]}"
        try:
            svc = svc_cls(wallet.address, wid)
            # Per-wallet deadline: tek bir yavaş/ölü zincir tüm dashboard'u
            # kilitlemesin (prod 2026-06-13: wallets 373s). Timeout → bu cüzdan
            # errors'a, diğerleri etkilenmez.
            assets = await asyncio.wait_for(svc.fetch(), timeout=settings.wallet_per_fetch_timeout)
            return [_build_position(wallet, wid, a) for a in assets]
        except TimeoutError:
            logger.warning("Cüzdan fetch timeout [%s] (%.0fs)", key, settings.wallet_per_fetch_timeout)
            msg = "Zaman aşımı (ağ/RPC yavaş)"
            errors[key] = msg
            wallet_errors[wid] = msg
            return []
        except Exception as e:
            logger.error("Cüzdan fetch hatası [%s]: %s", key, e)
            errors[key] = str(e)
            wallet_errors[wid] = str(e)
            return []

    # Toplam deadline (güvenlik ağı): per-wallet sınırı zaten paralelde ~tek
    # cüzdan süresi verir; bu sınır çok sayıda cüzdanda event-loop tıkanmasına
    # karşı korur. Süre dolarsa biten cüzdanlar döner, kalanlar timeout sayılır.
    tasks = [asyncio.ensure_future(fetch_wallet(w)) for w in wallets]
    done, pending = await asyncio.wait(tasks, timeout=settings.wallet_total_timeout)
    for task in pending:
        task.cancel()
    if pending:
        # Aggregate timeout yalnız `errors`'a girer (wallet_errors'a DEĞİL):
        # hangi cüzdanın takıldığı belirsiz, per-cüzdan ⚠ atfedilemez.
        errors["_timeout"] = f"{len(pending)} cüzdan toplam süre sınırını aştı"
    for task in done:
        try:
            all_positions.extend(task.result())
        except Exception:  # cancelled/exception — fetch_wallet zaten yutuyor
            pass

    return WalletResponse(positions=all_positions, errors=errors, wallet_errors=wallet_errors)


async def compute_wallet_positions(user_id, db: AsyncSession) -> WalletResponse:
    """Kullanıcının TÜM aktif cüzdanları için canlı pozisyonları hesaplar.

    Endpoint (`GET /wallets`) + live cache refresh servisi ortak kullanır.
    """
    result = await db.execute(
        select(WalletAddress).where(
            WalletAddress.user_id == user_id,
            WalletAddress.is_active.is_(True),
        )
    )
    wallets = result.scalars().all()
    return await _wallet_positions_for(wallets)


async def compute_single_wallet_positions(user_id, wallet_id, db: AsyncSession) -> WalletResponse:
    """Tek bir aktif cüzdan için canlı pozisyonları hesaplar (per-cüzdan yenile).

    Cüzdan bulunamazsa (yok/başkasının/pasif) boş WalletResponse döner — IDOR
    güvenli (yalnız user_id + is_active eşleşeni sorgular).
    """
    result = await db.execute(
        select(WalletAddress).where(
            WalletAddress.id == wallet_id,
            WalletAddress.user_id == user_id,
            WalletAddress.is_active.is_(True),
        )
    )
    wallets = result.scalars().all()
    return await _wallet_positions_for(wallets)


@router.get("/wallets", response_model=WalletResponse)
async def get_wallet_positions(
    current_user: CurrentUser,
    db: DbSession,
):
    return await compute_wallet_positions(current_user.id, db)


@router.get("/staking", response_model=list[StakingPosition])
async def get_staking_positions(
    current_user: CurrentUser,
    db: DbSession,
):
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == current_user.id)
        .options(selectinload(PortfolioSnapshot.asset_positions))
        .order_by(desc(PortfolioSnapshot.snapshot_date))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_PORTFOLIO_DATA)

    from app.services.aggregator import extract_staking_positions

    return extract_staking_positions(snapshot)
