"""Ortak çoklu para birimi altyapısı (v0.3.0 omurga).

Tüm gelir/gider/planlı/periyodik/bütçe/kredi-kartı modülleri bu util üzerinden
TL'ye çevrim yapar. `cash._amount_to_tl` + `goal._rate_to_tl` pattern'leri
buraya genelleştirildi (DRY); TCMB kurları `aggregator.fetch_tcmb_rates()`
ile çekilir (5 dk cache, JPY 100-unit normalize aggregator'da yapılır).

Hibrit kur kararı:
- Gerçekleşmiş kayıtlar (income/expense): işlem-anı kuru SABİT — kayıt anında
  `convert_to_tl` ile `amount_tl` hesaplanıp DB'ye yazılır, kur değişse de
  değişmez.
- Tahminler (planned_expense/recurring_income/budget): güncel kur — hesaplama
  anında `convert_to_tl` ile dinamik çevrilir.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.services.aggregator import fetch_tcmb_rates, fetch_usd_to_tl

logger = logging.getLogger(__name__)

# Desteklenen 6 para birimi (v0.3.0). Frontend select + CurrencyType ile senkron.
SUPPORTED: tuple[str, ...] = ("TRY", "USD", "EUR", "GBP", "CHF", "JPY")

CurrencyType = Literal["TRY", "USD", "EUR", "GBP", "CHF", "JPY"]

DEFAULT_CURRENCY = "TRY"

_TWO_PLACES = Decimal("0.01")


async def fetch_rates(*, fallback: bool = True) -> dict[str, Decimal]:
    """Tüm desteklenen para birimleri için 1 birim = X TL kur haritası.

    `aggregator.fetch_tcmb_rates()` sarmalanır: TRY=1 eklenir. `fallback=True`
    (varsayılan, cash pattern) ise eksik kur(lar) için USD/TRY fallback uygulanır
    + warning loglanır — kullanıcı yaklaşık değeri görür. `fallback=False`
    (goal pattern) ise sadece TCMB'nin verdiği kurlar döner; eksik döviz haritada
    yer almaz, çağıran 503 verebilir (kur olmadan yanlış hesap istemiyorsa).

    Dönüş: {"TRY": Decimal(1), "USD": Decimal(...), ...}. Çekilemeyen birim
    haritada yer almayabilir (convert_to_tl fallback'i devreye girer).
    """
    try:
        rates = dict(await fetch_tcmb_rates())
    except Exception as exc:
        logger.warning("TCMB rates çekilemedi (currency.fetch_rates): %s", exc)
        rates = {}

    rates["TRY"] = Decimal("1")

    if not fallback:
        return rates

    # Eksik kur(lar) için USD/TRY fallback — TCMB bir dövizi servis etmediyse
    # (ör. CHF/JPY o gün eksik) yaklaşık değer göster (cash pattern).
    missing = [c for c in SUPPORTED if c != "TRY" and (c not in rates or rates[c] <= 0)]
    if missing:
        try:
            usd_tl = await fetch_usd_to_tl()
        except Exception as exc:
            logger.error("USD/TRY fallback kuru çekilemedi (currency): %s", exc)
            usd_tl = None
        if usd_tl and usd_tl > 0:
            for c in missing:
                logger.warning(
                    "TCMB %s kuru bulunamadı, USD/TRY ile yaklaşık (gerçek değer farklı olabilir)",
                    c,
                )
                rates[c] = usd_tl

    return rates


def convert_to_tl(amount: Decimal, currency: str, rates: dict[str, Decimal]) -> Decimal:
    """Bir tutarı verilen kur haritasıyla TL'ye çevirir (ROUND_HALF_UP, 2 ondalık).

    `cash._amount_to_tl` mantığının genelleştirilmiş, senkron sürümü:
    - TRY → 1:1 (kur sorgusu yok).
    - Kur haritasında varsa → amount × rate.
    - Yoksa (eksik/0) → USD kuru ile yaklaşık; o da yoksa Decimal(0).

    rates haritası `fetch_rates()` çıktısı olmalı; çağıran tek sefer çeker,
    döngüde tekrar tekrar TCMB'ye gitmez (snapshot pattern).
    """
    if amount is None:
        return Decimal(0)
    currency = (currency or DEFAULT_CURRENCY).upper()
    if currency == "TRY":
        return Decimal(amount).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

    rate = rates.get(currency)
    if rate is not None and rate > 0:
        return (Decimal(amount) * rate).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

    # Fallback: USD kuru (ilgili döviz USD'ye yakın varsayım) — yoksa 0.
    usd_rate = rates.get("USD")
    if usd_rate is not None and usd_rate > 0:
        logger.warning(
            "%s kuru haritada yok, USD/TRY ile yaklaşık çevriliyor (gerçek değer farklı olabilir)",
            currency,
        )
        return (Decimal(amount) * usd_rate).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

    logger.error("%s için kur bulunamadı, 0 TL döndürülüyor", currency)
    return Decimal(0)
