"""Görüntüleme (display) para birimi dönüşümü — okuma/raporlama katmanı (Faz B).

Bu modül **yalnız okuma yolunda** çalışır: write-path / `amount_tl` / backfill
DEĞİŞMEZ. Gerçekleşmiş kayıtların görünüm-birimindeki değerini *tarihsel* TCMB
kuruyla, tahmin kayıtlarınınkini *güncel* kurla hesaplar.

Çekirdek model (kesin):
    deger(record, display) =
      display == record.currency  -> amount            (TAM; lookup yok, c==d kısayolu)
      display == "TRY"            -> amount_tl          (record-bazlı, hızlı yol)
      aksi (çapraz)               -> amount × histRate(record.currency→TRY, date)
                                            / histRate(display→TRY, date)

Tahmin kayıtları (recurring_income / planned_expense / KK taksit-ekstre / gelecek):
`date` yok/gelecek → GÜNCEL kur (`currency.convert_to_tl` ile TL, sonra
/currentRate[display]). display==currency → amount; display==TRY → güncel TL.

TRY display = hızlı yol: çağıran tüm mevcut `Σ amount_tl` SQL'ini AYNEN kullanır;
bu modül yalnız `display != "TRY"` yolunda devreye girer.

Rounding: ham çevir-topla, SON adımda ROUND_HALF_UP 2 ondalık (kuruş birikmesin);
c==d'de `amount` doğrudan döner (float/round hatası yok).
"""

import logging
from collections.abc import Sequence
from datetime import date as date_type
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_rate import DailyRate
from app.services import historical_rates

logger = logging.getLogger(__name__)

TRY = "TRY"
_TWO_PLACES = Decimal("0.01")

# Gerçekleşmiş kayıt 3'lüsü: (tutar kendi biriminde, para birimi, işlem tarihi).
RealizedItem = tuple[Decimal, str, date_type]


def quantize_tl(value: Decimal) -> Decimal:
    """Son adım yuvarlama: ROUND_HALF_UP 2 ondalık (kuruş tutarlılığı)."""
    return Decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def normalize_display(display: str | None, default: str | None) -> str:
    """İstenen görünüm birimini normalize eder; verilmezse kullanıcı varsayılanı."""
    chosen = (display or default or TRY).upper()
    return chosen


async def _historical_rate_matrix(
    db: AsyncSession,
    dates: set[date_type],
    currencies: set[str],
) -> dict[date_type, dict[str, Decimal]]:
    """Verilen tarih+birim kümeleri için `{date: {currency: rate_to_try}}` döner.

    Önce her tarihi tek TCMB çağrısıyla cache'ler (`ensure_date_cached` o günün TÜM
    birimlerini getirir → tarih başına 1 fetch, çapraz dönüşümde her iki birim de
    aynı fetch'le gelir). Sonra forward-fill ile her (tarih, birim) için
    `rate_date <= tarih` en yakın yayın günü kuru atanır.
    """
    matrix: dict[date_type, dict[str, Decimal]] = {d: {} for d in dates}
    non_try = {c for c in currencies if c != TRY}
    if not dates or not non_try:
        return matrix

    # 1) Eksik günleri TCMB'den cache'le (tarih başına tek fetch, tüm birimler).
    for d in dates:
        await historical_rates.ensure_date_cached(db, d)

    # 2) Forward-fill için: en eski hedeften ~7 gün geri tüm yayın günü kurlarını
    #    tek query'de çek (currency IN non_try). Sonra Python'da en yakın <= seç.
    lower = min(dates) - historical_rates_lookback()
    upper = max(dates)
    rows = (
        await db.execute(
            select(DailyRate.rate_date, DailyRate.currency, DailyRate.rate_to_try).where(
                DailyRate.currency.in_(non_try),
                DailyRate.rate_date >= lower,
                DailyRate.rate_date <= upper,
            )
        )
    ).all()

    # currency → artan tarihli [(rate_date, rate)] listesi
    by_currency: dict[str, list[tuple[date_type, Decimal]]] = {c: [] for c in non_try}
    for rate_date, currency, rate in sorted(rows, key=lambda r: r[0]):
        by_currency.setdefault(currency, []).append((rate_date, Decimal(rate)))

    for d in dates:
        for c in non_try:
            chosen = _latest_on_or_before(by_currency.get(c, ()), d)
            if chosen is not None:
                matrix[d][c] = chosen
    return matrix


def _latest_on_or_before(published: Sequence[tuple[date_type, Decimal]], on: date_type) -> Decimal | None:
    """Artan tarihli `(rate_date, rate)` listesinden `rate_date <= on` en yakın kuru."""
    chosen: Decimal | None = None
    for pub_date, value in published:
        if pub_date <= on:
            chosen = value
        else:
            break
    return chosen


def historical_rates_lookback():
    """Forward-fill alt sınırı için gün marjı (Faz A ile aynı: 7 gün)."""
    from datetime import timedelta

    return timedelta(days=historical_rates._MAX_BACKFILL_LOOKBACK_DAYS)


def _value_in_display(
    amount: Decimal,
    currency: str,
    amount_tl: Decimal | None,
    on: date_type,
    display: str,
    matrix: dict[date_type, dict[str, Decimal]],
) -> Decimal:
    """Tek gerçekleşmiş kaydın display birimindeki HAM değeri (yuvarlanmamış).

    c==d → amount; display==TRY → amount_tl; aksi → çapraz tarihsel cross.
    """
    currency = (currency or TRY).upper()
    if currency == display:
        return Decimal(amount)
    if display == TRY:
        # amount_tl record-bazlı sabit (işlem-anı kuru). Yoksa (eski/eksik kayıt)
        # tarihsel src kuruyla türet.
        if amount_tl is not None:
            return Decimal(amount_tl)
        src = _rate_for(matrix, on, currency)
        return Decimal(amount) * src if src is not None else Decimal(0)
    if currency == TRY:
        # TL kaydı → display birimine: amount / histRate(display→TRY, date).
        dst = _rate_for(matrix, on, display)
        return Decimal(amount) / dst if dst and dst > 0 else Decimal(0)

    # Çapraz: amount × histRate(src→TRY) / histRate(display→TRY).
    src = _rate_for(matrix, on, currency)
    dst = _rate_for(matrix, on, display)
    if src is None or not dst or dst <= 0:
        logger.warning(
            "Tarihsel çapraz kur eksik (%s→%s @ %s); 0 döndürülüyor",
            currency,
            display,
            on.isoformat(),
        )
        return Decimal(0)
    return Decimal(amount) * src / dst


def _rate_for(matrix: dict[date_type, dict[str, Decimal]], on: date_type, currency: str) -> Decimal | None:
    if currency == TRY:
        return Decimal(1)
    return matrix.get(on, {}).get(currency)


async def convert_realized(
    db: AsyncSession,
    items: Sequence[RealizedItem],
    display: str,
    *,
    amount_tls: Sequence[Decimal | None] | None = None,
) -> Decimal:
    """Gerçekleşmiş kayıt listesinin display birimindeki TOPLAMINI döner.

    `items`: (amount, currency, date) üçlüleri. `amount_tls` verilirse (mevcut
    `record.amount_tl`) display==TRY hızlı yolunda lookup'sız kullanılır; yoksa
    tarihsel türetme yapılır.

    Algoritma:
    - display==TRY: Σ amount_tl (varsa) — sıfır lookup. (Çağıranın zaten SQL ile
      yapması beklenir; bu yol tutarlılık/yardımcı amaçlı.)
    - Aksi: çapraz dönüşüm gereken (currency != display, currency != TRY veya
      display != TRY) kayıtlar için gerekli (tarih) kümesini tek seferde cache'le
      + matrix kur; her kaydı çevir; SON adımda yuvarla.
    """
    display = display.upper()
    if not items:
        return Decimal(0)

    tl_list: list[Decimal | None] = list(amount_tls) if amount_tls is not None else [None] * len(items)

    # Hangi (tarih, birim) ikilileri için tarihsel kur gerekir?
    needed_dates: set[date_type] = set()
    needed_currencies: set[str] = set()
    for (amount, currency, on), amount_tl in zip(items, tl_list):
        c = (currency or TRY).upper()
        if c == display:
            continue  # c==d kısayolu — lookup yok
        if display == TRY and amount_tl is not None:
            continue  # amount_tl sabit — lookup yok
        # Çapraz/türetme: tarih + ilgili birim(ler) gerekir.
        needed_dates.add(on)
        if c != TRY:
            needed_currencies.add(c)
        if display != TRY:
            needed_currencies.add(display)

    matrix = await _historical_rate_matrix(db, needed_dates, needed_currencies) if needed_dates else {}

    total = Decimal(0)
    for (amount, currency, on), amount_tl in zip(items, tl_list):
        total += _value_in_display(Decimal(amount), currency, amount_tl, on, display, matrix)
    return quantize_tl(total)


async def convert_realized_grouped(
    db: AsyncSession,
    rows: Sequence[tuple],
    display: str,
) -> tuple[dict[str, Decimal], Decimal]:
    """`(key, amount, currency, date, amount_tl)` satırlarını anahtar bazında dönüştürür.

    Income/Expense özeti + bütçe karşılaştırması ortak kullanır (DRY, S4144). Her
    anahtar (kategori) için `convert_realized` çağrılır; `(harita, toplam)` döner.
    `display == TRY` çağıranın hızlı yolu (Σ amount_tl SQL) ile yapılır; bu fonksiyon
    yalnız `display != TRY`'de çağrılmalı."""
    by_key_items: dict[str, list[RealizedItem]] = {}
    by_key_tls: dict[str, list[Decimal]] = {}
    for key, amount, currency, on, amount_tl in rows:
        by_key_items.setdefault(key, []).append((Decimal(amount), currency, on))
        by_key_tls.setdefault(key, []).append(Decimal(amount_tl))
    out: dict[str, Decimal] = {}
    total = Decimal(0)
    for key, items in by_key_items.items():
        value = await convert_realized(db, items, display, amount_tls=by_key_tls[key])
        out[key] = value
        total += value
    return out, quantize_tl(total)


def convert_forecast(
    amount: Decimal,
    currency: str,
    display: str,
    current_rates: dict[str, Decimal],
) -> Decimal:
    """Tahmin kaydının display birimindeki değeri (GÜNCEL kur).

    - display == currency → amount (TAM).
    - display == TRY → güncel TL (currency.convert_to_tl mantığı).
    - aksi → amount × currentRate[currency] / currentRate[display].

    `current_rates`: `currency.fetch_rates()` çıktısı (1 birim = X TL). Çağıran tek
    sefer çeker; bu fonksiyon senkron (döngüde tekrar TCMB yok).
    """
    display = display.upper()
    currency = (currency or TRY).upper()
    amount = Decimal(amount)
    if currency == display:
        return quantize_tl(amount)

    src = Decimal(1) if currency == TRY else current_rates.get(currency)
    if src is None or src <= 0:
        src = current_rates.get("USD")  # cash pattern fallback
        if src:
            logger.warning("Güncel %s kuru yok, USD ile yaklaşık (forecast)", currency)
    if not src or src <= 0:
        logger.error("Güncel kur yok (%s); forecast 0 döndürülüyor", currency)
        return Decimal(0)
    tl = amount * src

    if display == TRY:
        return quantize_tl(tl)
    dst = current_rates.get(display)
    if not dst or dst <= 0:
        logger.error("Güncel display kuru yok (%s); forecast 0", display)
        return Decimal(0)
    return quantize_tl(tl / dst)


def tl_to_display(tl: Decimal, display: str, current_rates: dict[str, Decimal]) -> Decimal:
    """Halihazırda TL olan bir toplamı display birimine GÜNCEL kurla çevirir.

    Tahmin/cari nitelikli TL toplamları (ör. KK ekstre/borç) için. display==TRY →
    olduğu gibi (yuvarlanmış). Aksi → tl / currentRate[display].
    """
    display = display.upper()
    tl = Decimal(tl)
    if display == TRY:
        return quantize_tl(tl)
    dst = current_rates.get(display)
    if not dst or dst <= 0:
        logger.error("Güncel display kuru yok (%s); TL döndürülüyor (fallback)", display)
        return quantize_tl(tl)
    return quantize_tl(tl / dst)
