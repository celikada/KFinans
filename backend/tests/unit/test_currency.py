"""Çoklu para birimi (v0.3.0) util birim testleri — DB'siz, hızlı.

`app/services/currency.py` içindeki `convert_to_tl` (saf fonksiyon) ve
`fetch_rates` (TCMB wrapper) test edilir. Gerçek TCMB çağrısı YOK —
`aggregator.fetch_tcmb_rates` / `fetch_usd_to_tl` monkeypatch ile mock'lanır.

Doğrulanan gerçek imzalar (app/services/currency.py'den okundu):
- SUPPORTED = ("TRY", "USD", "EUR", "GBP", "CHF", "JPY")
- async fetch_rates(*, fallback=True) -> dict[str, Decimal]  (TRY=1 ekler)
- convert_to_tl(amount, currency, rates) -> Decimal  (ROUND_HALF_UP, 2 ondalık)
"""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.services import currency as currency_svc
from app.services.currency import (
    DEFAULT_CURRENCY,
    SUPPORTED,
    convert_to_tl,
    fetch_rates,
)

# Sabit mock kur haritası — testler boyunca yeniden kullanılır.
_RATES = {
    "TRY": Decimal("1"),
    "USD": Decimal("35"),
    "EUR": Decimal("38"),
    "GBP": Decimal("44"),
    "CHF": Decimal("40"),
    "JPY": Decimal("0.23"),  # TCMB 100-unit normalize aggregator'da yapılır
}


# ---------------------------------------------------------------------------
# convert_to_tl — saf çevrim fonksiyonu
# ---------------------------------------------------------------------------
def test_convert_try_returns_amount_unchanged():
    """TRY → kur sorgusu olmadan amount'un 2 ondalıklı hali döner."""
    assert convert_to_tl(Decimal("1234.56"), "TRY", _RATES) == Decimal("1234.56")


def test_convert_try_quantizes_two_places():
    """TRY bile 2 ondalığa quantize edilir (Numeric(18,2) uyumu)."""
    assert convert_to_tl(Decimal("100"), "TRY", _RATES) == Decimal("100.00")


def test_convert_usd_multiplies_by_rate():
    """USD → amount × USD kuru."""
    assert convert_to_tl(Decimal("10"), "USD", _RATES) == Decimal("350.00")


def test_convert_eur_multiplies_by_rate():
    """EUR → amount × EUR kuru."""
    assert convert_to_tl(Decimal("100"), "EUR", _RATES) == Decimal("3800.00")


def test_convert_jpy_just_multiplies_no_double_normalize():
    """JPY 100-unit normalize TCMB tarafında yapılır; convert sadece çarpar.

    rates["JPY"]=0.23 (1 JPY = 0.23 TL varsayımı) → 1000 JPY = 230 TL.
    """
    assert convert_to_tl(Decimal("1000"), "JPY", _RATES) == Decimal("230.00")


def test_convert_lowercase_currency_normalized():
    """Para birimi küçük harf gelirse .upper() ile normalize edilir."""
    assert convert_to_tl(Decimal("10"), "usd", _RATES) == Decimal("350.00")


def test_convert_rounds_half_up():
    """ROUND_HALF_UP: 0.005 yukarı yuvarlanır (banker's rounding değil)."""
    # 1.005 * 1 (TRY) -> 1.01 (HALF_UP); HALF_EVEN olsaydı 1.00 olurdu.
    assert convert_to_tl(Decimal("1.005"), "TRY", _RATES) == Decimal("1.01")
    # USD örneği: 0.1 * 35.05 = 3.505 -> 3.51
    rates = {"USD": Decimal("35.05")}
    assert convert_to_tl(Decimal("0.1"), "USD", rates) == Decimal("3.51")


def test_convert_missing_currency_falls_back_to_usd():
    """Kur haritasında olmayan döviz → USD kuru ile yaklaşık çevrilir."""
    rates = {"USD": Decimal("35")}  # CHF yok
    # 10 CHF → USD kuru (35) ile yaklaşık = 350
    assert convert_to_tl(Decimal("10"), "CHF", rates) == Decimal("350.00")


def test_convert_missing_currency_and_no_usd_returns_zero():
    """Ne istenen döviz ne USD haritada varsa → Decimal(0)."""
    rates = {"TRY": Decimal("1")}  # USD ve EUR yok
    assert convert_to_tl(Decimal("10"), "EUR", rates) == Decimal(0)


def test_convert_zero_or_negative_rate_falls_back():
    """Kur 0/negatif ise geçersiz sayılır → USD fallback."""
    rates = {"EUR": Decimal("0"), "USD": Decimal("35")}
    assert convert_to_tl(Decimal("10"), "EUR", rates) == Decimal("350.00")


def test_convert_none_amount_returns_zero():
    """amount None ise (defensive) Decimal(0) döner."""
    assert convert_to_tl(None, "USD", _RATES) == Decimal(0)


def test_convert_none_currency_defaults_to_try():
    """currency None → DEFAULT_CURRENCY (TRY) → amount aynen."""
    assert DEFAULT_CURRENCY == "TRY"
    assert convert_to_tl(Decimal("500"), None, _RATES) == Decimal("500.00")


def test_supported_currencies_constant():
    """SUPPORTED 6 para birimini içerir (frontend select ile senkron)."""
    assert SUPPORTED == ("TRY", "USD", "EUR", "GBP", "CHF", "JPY")


# ---------------------------------------------------------------------------
# fetch_rates — TCMB wrapper (mock'lu, gerçek ağ çağrısı yok)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_rates_adds_try_and_returns_dict(monkeypatch):
    """TCMB başarılı → dict döner ve TRY=1 eklenir."""
    tcmb = {"USD": Decimal("35"), "EUR": Decimal("38")}
    monkeypatch.setattr(
        "app.services.currency.fetch_tcmb_rates",
        AsyncMock(return_value=dict(tcmb)),
    )
    rates = await fetch_rates()
    assert rates["TRY"] == Decimal("1")
    assert rates["USD"] == Decimal("35")
    assert rates["EUR"] == Decimal("38")


@pytest.mark.asyncio
async def test_fetch_rates_tcmb_failure_returns_at_least_try(monkeypatch):
    """TCMB exception fırlatırsa fetch_rates yutar; en azından TRY=1 döner.

    fallback=False ile USD/TRY fallback denemesi de yapılmaz.
    """
    monkeypatch.setattr(
        "app.services.currency.fetch_tcmb_rates",
        AsyncMock(side_effect=RuntimeError("TCMB down")),
    )
    rates = await fetch_rates(fallback=False)
    assert rates == {"TRY": Decimal("1")}


@pytest.mark.asyncio
async def test_fetch_rates_fallback_fills_missing_with_usd(monkeypatch):
    """Eksik döviz(ler) için fallback=True → USD/TRY kuru ile doldurulur."""
    # TCMB sadece USD verir; EUR/GBP/CHF/JPY eksik.
    monkeypatch.setattr(
        "app.services.currency.fetch_tcmb_rates",
        AsyncMock(return_value={"USD": Decimal("35")}),
    )
    monkeypatch.setattr(
        "app.services.currency.fetch_usd_to_tl",
        AsyncMock(return_value=Decimal("35")),
    )
    rates = await fetch_rates(fallback=True)
    assert rates["TRY"] == Decimal("1")
    assert rates["USD"] == Decimal("35")
    # Eksik dövizler USD kuru ile dolduruldu
    for c in ("EUR", "GBP", "CHF", "JPY"):
        assert rates[c] == Decimal("35")


@pytest.mark.asyncio
async def test_fetch_rates_no_fallback_leaves_missing_out(monkeypatch):
    """fallback=False → eksik dövizler haritada yer almaz (TRY+USD yalnızca)."""
    monkeypatch.setattr(
        "app.services.currency.fetch_tcmb_rates",
        AsyncMock(return_value={"USD": Decimal("35")}),
    )
    rates = await fetch_rates(fallback=False)
    assert set(rates.keys()) == {"TRY", "USD"}


@pytest.mark.asyncio
async def test_fetch_rates_module_alias_consistency(monkeypatch):
    """currency_svc.fetch_rates ile doğrudan import edilen fetch_rates aynı obje."""
    assert currency_svc.fetch_rates is fetch_rates
