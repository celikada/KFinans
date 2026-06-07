"""Görüntüleme para birimi dönüşümü — DB gerektirmeyen birim testleri (Faz B).

c==d kısayolu, forecast (güncel kur), tl_to_display ve yuvarlama yolları. DB-backed
(tarihsel çapraz, convert_realized) testleri integration tarafında.
"""

from decimal import Decimal

import pytest

from app.services import display_currency as disp


class TestNormalizeDisplay:
    def test_explicit_wins(self):
        assert disp.normalize_display("usd", "EUR") == "USD"

    def test_falls_back_to_default(self):
        assert disp.normalize_display(None, "eur") == "EUR"

    def test_default_try_when_nothing(self):
        assert disp.normalize_display(None, None) == "TRY"


class TestConvertForecast:
    _RATES = {"TRY": Decimal(1), "USD": Decimal("40"), "EUR": Decimal("44")}

    def test_c_equals_d_returns_amount_exact(self):
        # display == currency → amount aynen (lookup yok, çarpıtma yok)
        out = disp.convert_forecast(Decimal("123.45"), "USD", "USD", self._RATES)
        assert out == Decimal("123.45")

    def test_to_try_uses_current_rate(self):
        # 10 USD × 40 = 400 TL
        out = disp.convert_forecast(Decimal("10"), "USD", "TRY", self._RATES)
        assert out == Decimal("400.00")

    def test_try_to_other(self):
        # 440 TL / 44 = 10 EUR
        out = disp.convert_forecast(Decimal("440"), "TRY", "EUR", self._RATES)
        assert out == Decimal("10.00")

    def test_cross_current(self):
        # 10 USD = 400 TL → /44 = 9.0909... EUR (ROUND_HALF_UP 2)
        out = disp.convert_forecast(Decimal("10"), "USD", "EUR", self._RATES)
        assert out == Decimal("9.09")

    def test_missing_rate_returns_zero(self):
        out = disp.convert_forecast(Decimal("10"), "CHF", "EUR", {"TRY": Decimal(1)})
        assert out == Decimal(0)


class TestTlToDisplay:
    _RATES = {"TRY": Decimal(1), "USD": Decimal("40")}

    def test_try_passthrough(self):
        assert disp.tl_to_display(Decimal("100.005"), "TRY", self._RATES) == Decimal("100.01")

    def test_to_usd(self):
        assert disp.tl_to_display(Decimal("400"), "USD", self._RATES) == Decimal("10.00")

    def test_missing_rate_falls_back_to_tl(self):
        assert disp.tl_to_display(Decimal("400"), "EUR", self._RATES) == Decimal("400.00")


class TestQuantize:
    def test_round_half_up(self):
        assert disp.quantize_tl(Decimal("1.005")) == Decimal("1.01")


@pytest.mark.asyncio
async def test_convert_realized_empty_no_db():
    # Boş liste → 0, DB'ye dokunmadan
    assert await disp.convert_realized(None, [], "USD") == Decimal(0)


@pytest.mark.asyncio
async def test_convert_realized_c_equals_d_no_db():
    # Tüm kayıtlar display ile aynı birimde → lookup yok, db=None ile patlamaz, amount toplamı
    from datetime import date

    items = [(Decimal("10.50"), "USD", date(2026, 1, 5)), (Decimal("4.50"), "usd", date(2026, 2, 1))]
    out = await disp.convert_realized(None, items, "USD")
    assert out == Decimal("15.00")


@pytest.mark.asyncio
async def test_convert_realized_try_fastpath_no_db():
    # display TRY + amount_tl verili → Σ amount_tl, lookup yok (db=None patlamaz)
    from datetime import date

    items = [(Decimal("10"), "USD", date(2026, 1, 5)), (Decimal("20"), "EUR", date(2026, 2, 1))]
    tls = [Decimal("400.00"), Decimal("880.00")]
    out = await disp.convert_realized(None, items, "TRY", amount_tls=tls)
    assert out == Decimal("1280.00")
