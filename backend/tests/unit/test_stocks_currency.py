"""
Hisse senedi para birimi dönüşümü — saf fonksiyon, DB veya HTTP gerekmez.

Daha önce GBp dönüşümü hatalıydı: GBp ÷ 100 sonucu USD varsayılıyordu.
Doğrusu: GBp -> GBP -> USD -> TL zincirinde GBP/USD kuru kullanılmalı.
"""
from decimal import Decimal

import pytest

from app.api.v1.stocks import convert_to_tl


class TestConvertToTl:
    USD_TL = Decimal("33.50")
    GBP_USD = Decimal("1.27")

    def test_try_returns_unchanged(self):
        result = convert_to_tl(Decimal("125.40"), "TRY", self.USD_TL, self.GBP_USD)
        assert result == Decimal("125.40")

    def test_usd_uses_usd_tl_rate(self):
        # 100 USD * 33.50 = 3350.00
        result = convert_to_tl(Decimal("100"), "USD", self.USD_TL, self.GBP_USD)
        assert result == Decimal("3350.0000")

    def test_gbp_pence_uses_full_chain(self):
        """500 GBp = 5 GBP -> 5 * 1.27 = 6.35 USD -> 6.35 * 33.50 = 212.7250 TL."""
        result = convert_to_tl(Decimal("500"), "GBp", self.USD_TL, self.GBP_USD)
        assert result == Decimal("212.7250")

    def test_gbp_pence_does_not_assume_1gbp_equals_1usd(self):
        """Eski hatali davranis: 500 GBp / 100 * 33.50 = 167.50 (yanlis)."""
        result = convert_to_tl(Decimal("500"), "GBp", self.USD_TL, self.GBP_USD)
        wrong = Decimal("167.50")  # eski kodun urettigi yanlis deger
        assert result != wrong

    def test_unknown_currency_falls_back_to_usd(self):
        # EUR, JPY vb. icin USD varsayimi
        result = convert_to_tl(Decimal("100"), "EUR", self.USD_TL, self.GBP_USD)
        assert result == Decimal("3350.0000")

    def test_zero_price_returns_zero(self):
        for currency in ("TRY", "USD", "GBp", "EUR"):
            result = convert_to_tl(Decimal("0"), currency, self.USD_TL, self.GBP_USD)
            assert result == Decimal("0") or result == Decimal("0.0000")

    def test_high_precision_preserved(self):
        # 0.01 GBp = 0.0001 GBP -> 0.0001 * 1.27 = 0.000127 USD -> 0.000127 * 33.50 = 0.00425450 TL
        # quantize 0.0001 -> 0.0043
        result = convert_to_tl(Decimal("0.01"), "GBp", self.USD_TL, self.GBP_USD)
        assert result == Decimal("0.0043")
