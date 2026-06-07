"""Tarihsel TCMB döviz kuru servisi (Faz A altyapı).

Belirli bir TARİHTEKİ 1 birim döviz = X TL kurunu sağlar. Cache `daily_rates`
tablosunda tutulur; eksikse TCMB'nin tarihli XML endpoint'inden çekilir ve
upsert edilir.

Faz B (kayıt-bazlı dönüşüm) bunu kullanır. Bu fazda hiçbir endpoint/hesaplama
değişmez — yalnız altyapı.

Forward-fill: TCMB yalnız iş günlerinde kur yayınlar. Bir tarihin (hafta
sonu/tatil) kuru sorulduğunda DB'de `rate_date <= aranan_tarih` koşulunu
sağlayan EN YAKIN (en büyük rate_date) kayıt kullanılır. Ayrı forward-fill
satırı YAZILMAZ; lookup dinamiktir.
"""

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_rate import DailyRate
from app.services.aggregator import parse_tcmb_xml

logger = logging.getLogger(__name__)

# Sabit TCMB host — SSRF riski yok (kullanici girdisi URL'e girmez, yalniz tarih).
_TCMB_HISTORICAL_BASE = "https://www.tcmb.gov.tr/kurlar"

# Hafta sonu + uzun tatil (resmi bayram) icin geriye dogru en fazla bu kadar gun
# TCMB'den veri aranir. 7 gun en uzun resmi tatili (Ramazan/Kurban + hafta sonu)
# kapsar; bulunamazsa None (cagiran TL/exchange_rate fallback'e duser).
_MAX_BACKFILL_LOOKBACK_DAYS = 7

# TCMB rate-limit dostu paralelizm (bulk fetch).
_FETCH_PARALLELISM = 5
_FETCH_BACKOFF_SEC = 0.2

TRY = "TRY"


def _historical_url(d: date) -> str:
    """TCMB tarihli kur XML URL'i: .../YYYYMM/DDMMYYYY.xml."""
    return f"{_TCMB_HISTORICAL_BASE}/{d:%Y%m}/{d:%d%m%Y}.xml"


async def _fetch_tcmb_for_date(d: date) -> dict[str, Decimal] | None:
    """Belirli bir gunun TCMB XML'ini ceker ve parse eder.

    Yayin gunu degilse (hafta sonu/tatil) TCMB 404 doner → None.
    Ag/parse hatasi → None (cagiran forward-fill veya fallback'e duser).
    """
    url = _historical_url(d)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        rates = parse_tcmb_xml(resp.content)
        return rates or None
    except Exception as exc:  # noqa: BLE001 — ag/parse hatasi best-effort
        logger.warning("TCMB tarihsel kur cekilemedi (%s): %s", url, exc)
        return None


async def _upsert_rates(db: AsyncSession, d: date, rates: dict[str, Decimal]) -> None:
    """Bir gunun tum dovizlerini daily_rates'e idempotent upsert eder.

    TRY saklanmaz (=1 sabit). PK (rate_date, currency) cakismasinda rate_to_try
    + fetched_at guncellenir (yeniden cekimde tazelenir).
    """
    rows = [
        {
            "rate_date": d,
            "currency": code,
            "rate_to_try": value,
            "source": "tcmb",
        }
        for code, value in rates.items()
        if code != TRY and value is not None and value > 0
    ]
    if not rows:
        return

    stmt = pg_insert(DailyRate).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["rate_date", "currency"],
        set_={
            "rate_to_try": stmt.excluded.rate_to_try,
            "source": stmt.excluded.source,
            "fetched_at": func.now(),
        },
    )
    await db.execute(stmt)
    await db.commit()


async def ensure_date_cached(db: AsyncSession, d: date) -> None:
    """O günün TCMB verisini (tüm birimler tek XML) DB'de garanti eder.

    O gün için DB'de en az bir kayıt varsa TCMB'ye gidilmez (idempotent).
    Yoksa TCMB'den çekilip upsert edilir. Yayın günü değilse (404) no-op —
    forward-fill lookup zaten önceki iş gününü bulur.
    """
    exists = await db.execute(select(DailyRate.currency).where(DailyRate.rate_date == d).limit(1))
    if exists.first() is not None:
        return

    rates = await _fetch_tcmb_for_date(d)
    if rates:
        await _upsert_rates(db, d, rates)


async def _db_rate_on_or_before(db: AsyncSession, currency: str, on: date) -> tuple[date, Decimal] | None:
    """DB'de `rate_date <= on` en yakın (en büyük rate_date) kuru döner.

    Forward-fill çekirdeği: hafta sonu/tatil → önceki iş günü kuru.
    """
    result = await db.execute(
        select(DailyRate.rate_date, DailyRate.rate_to_try)
        .where(DailyRate.currency == currency, DailyRate.rate_date <= on)
        .order_by(DailyRate.rate_date.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    return row[0], Decimal(row[1])


async def get_historical_rate(db: AsyncSession, currency: str, on: date) -> Decimal | None:
    """`on` tarihinde 1 birim `currency` = X TL kuru (Decimal) döner.

    Akış:
    1. TRY → Decimal(1) (DB sorgusu yok).
    2. DB'de `rate_date <= on` en yakın kayıt (dinamik forward-fill) → kullan.
    3. Yoksa TCMB'den `on`'dan geriye ≤7 gün dene (uzun tatil); ilk başarılı XML'i
       o yayın günü için upsert et + DB'den tekrar oku.
    4. 7 günde de yoksa None (çağıran TL/exchange_rate fallback'e düşer).
    """
    currency = (currency or "").upper()
    if currency == TRY:
        return Decimal(1)

    hit = await _db_rate_on_or_before(db, currency, on)
    if hit is not None:
        return hit[1]

    # DB'de yok — TCMB'den geriye dogru dene (yayin gunu olmayanlar 404 → atla).
    for delta in range(_MAX_BACKFILL_LOOKBACK_DAYS + 1):
        probe = on - timedelta(days=delta)
        rates = await _fetch_tcmb_for_date(probe)
        if rates:
            await _upsert_rates(db, probe, rates)
            value = rates.get(currency)
            if value is not None and value > 0:
                return value
            # XML geldi ama bu doviz yok — yine de upsert'ledik; daha geriye bakma.
            return None

    logger.warning(
        "Tarihsel kur bulunamadi: %s @ %s (≤%d gun geriye TCMB bos)",
        currency,
        on.isoformat(),
        _MAX_BACKFILL_LOOKBACK_DAYS,
    )
    return None


def _forward_fill_dates(sorted_published: list[tuple[date, Decimal]], dates: set[date]) -> dict[date, Decimal]:
    """Yayın günü kurlarını her hedef tarihe forward-fill ile eşler.

    `sorted_published` artan rate_date sıralı (tarih, kur). Her hedef tarih için
    `rate_date <= hedef` en büyük yayın günü kuru atanır. Karşılık yoksa
    (hedef tüm yayın günlerinden eski) o tarih sonuca eklenmez.
    """
    out: dict[date, Decimal] = {}
    if not sorted_published:
        return out
    for target in dates:
        chosen: Decimal | None = None
        for pub_date, value in sorted_published:
            if pub_date <= target:
                chosen = value
            else:
                break
        if chosen is not None:
            out[target] = chosen
    return out


async def _fetch_dates_parallel(missing: list[date]) -> dict[date, dict[str, Decimal] | None]:
    """Verilen tarihler için TCMB XML'lerini PARALEL (yalnız HTTP) çeker.

    Sadece ağ I/O paralelleştirilir (Semaphore + backoff, TCMB rate-limit);
    DB'ye DOKUNULMAZ. Çağıran upsert'leri tek session'da SERİ yapmalı
    (AsyncSession concurrent operasyona izin vermez).
    """
    semaphore = asyncio.Semaphore(_FETCH_PARALLELISM)

    async def _fetch_one(d: date) -> tuple[date, dict[str, Decimal] | None]:
        async with semaphore:
            rates = await _fetch_tcmb_for_date(d)
            await asyncio.sleep(_FETCH_BACKOFF_SEC)
            return d, rates

    fetched = await asyncio.gather(*[_fetch_one(d) for d in missing])
    return dict(fetched)


async def _query_published(db: AsyncSession, currency: str, lower: date, upper: date) -> list[tuple[date, Decimal]]:
    """`[lower, upper]` aralığındaki yayın günü kurlarını artan tarihli döner."""
    result = await db.execute(
        select(DailyRate.rate_date, DailyRate.rate_to_try)
        .where(
            DailyRate.currency == currency,
            DailyRate.rate_date >= lower,
            DailyRate.rate_date <= upper,
        )
        .order_by(DailyRate.rate_date.asc())
    )
    return [(r[0], Decimal(r[1])) for r in result.all()]


async def get_historical_rates_bulk(db: AsyncSession, currency: str, dates: set[date]) -> dict[date, Decimal]:
    """Tek display birimi için bir tarih kümesinin kurlarını toplu döner.

    Dashboard tek çağrısı için optimize: distinct tarihleri tek query'de çeker,
    DB'de hiç olmayan tarihleri batch TCMB fetch (Semaphore + backoff), Python'da
    forward-fill ile her hedef tarihe eşler.

    Yalnız TEK display birimi gerekir (tüm birimler değil). TRY → her tarih için 1.
    """
    currency = (currency or "").upper()
    if not dates:
        return {}
    if currency == TRY:
        return {d: Decimal(1) for d in dates}

    # forward-fill icin min'den ONCESI son yayin gununu da kapsamak icin lower
    # bound'u biraz geri al.
    lower = min(dates) - timedelta(days=_MAX_BACKFILL_LOOKBACK_DAYS)
    upper = max(dates)

    # 1) Mevcut yayin gunlerini tek query'de cek + forward-fill.
    published = await _query_published(db, currency, lower, upper)
    filled = _forward_fill_dates(published, dates)
    missing = [d for d in dates if d not in filled]
    if not missing:
        return filled

    # 2) Eksik hedefleri PARALEL fetch (yalniz HTTP) → SERI upsert.
    rates_by_date = await _fetch_dates_parallel(missing)
    for d, rates in rates_by_date.items():
        if rates:
            await _upsert_rates(db, d, rates)

    # 3) Yeni cekilenleri DB'den tekrar okuyup forward-fill'i tazele.
    published2 = await _query_published(db, currency, lower, upper)
    return _forward_fill_dates(published2, dates)


async def backfill_dates(db: AsyncSession, dates: set[date]) -> int:
    """Verilen tarih kümesini cache'e doldurur (Faz D / ilk yük yardımcısı).

    Endpoint/cron'a bağlı DEĞİL — yalnız fonksiyon (manuel/script kullanımı).
    Her tarih için (DB'de o gün yoksa) TCMB'den çekip upsert eder. Yayın günü
    olmayan tarihler no-op. Kaç günün TCMB'den çekildiğini döner.

    Returns: TCMB'den başarıyla çekilip cache'lenen gün sayısı.
    """
    if not dates:
        return 0

    # 1) DB'de zaten cache'li gunleri tek query'de tespit et (concurrent session
    # erisimi YOK — AsyncSession tek operasyon kuralina uyulur).
    existing_result = await db.execute(select(DailyRate.rate_date).where(DailyRate.rate_date.in_(dates)).distinct())
    existing = {row[0] for row in existing_result.all()}
    missing = [d for d in dates if d not in existing]
    if not missing:
        return 0

    # 2) Yalniz HTTP fetch'leri paralel (DB degil) — gather guvenli.
    rates_by_date = await _fetch_dates_parallel(missing)

    # 3) Upsert'leri tek session'da SERI yap (concurrent DB erisimini onle).
    cached = 0
    for d, rates in rates_by_date.items():
        if rates:
            await _upsert_rates(db, d, rates)
            cached += 1
    return cached
