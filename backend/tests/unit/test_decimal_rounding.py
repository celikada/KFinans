"""
Audit 2026-05-22 P0 #8 — Decimal global rounding mode regression guard.

`app.main` import-time `getcontext().rounding = ROUND_HALF_UP` set eder.
Test bu setting'in beklenen davranışı verdiğini doğrular. Python default
`ROUND_HALF_EVEN` (banker's) muhasebede/vergi raporlamada 0.005 -> 0.00
gibi beklenmeyen sonuç verir; KFinans için `ROUND_HALF_UP` standart.
"""

from decimal import ROUND_HALF_UP, Decimal, getcontext

import app.main  # noqa: F401 — import-time side effect: rounding mode set


def test_global_rounding_mode_is_half_up():
    assert getcontext().rounding == ROUND_HALF_UP


def test_half_up_rounds_half_away_from_zero():
    """0.005 -> 0.01 (HALF_UP), NOT 0.00 (HALF_EVEN banker's)"""
    assert Decimal("0.005").quantize(Decimal("0.01")) == Decimal("0.01")


def test_half_up_consistent_across_magnitudes():
    """0.025 -> 0.03 (HALF_UP), NOT 0.02 (HALF_EVEN banker's)"""
    assert Decimal("0.025").quantize(Decimal("0.01")) == Decimal("0.03")
    assert Decimal("0.0255").quantize(Decimal("0.001")) == Decimal("0.026")


def test_half_up_negative_rounds_away_from_zero():
    """-0.005 -> -0.01 (HALF_UP rounds away from zero on negatives too)"""
    assert Decimal("-0.005").quantize(Decimal("0.01")) == Decimal("-0.01")
