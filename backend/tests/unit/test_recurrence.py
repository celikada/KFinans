"""Ortak recurrence util (applies_in_month / date_for_period / iter_due_periods) testleri."""

from dataclasses import dataclass, field
from datetime import date

from app.services import recurrence


@dataclass
class _Defn:
    """Duck-typed periyodik tanım (RecurringIncome / PlannedExpense yerine)."""

    recurrence: str
    start_date: date
    day_of_month: int = 1
    end_date: date | None = None
    months: list[int] | None = field(default=None)


def test_applies_monthly():
    d = _Defn("monthly", date(2026, 1, 15))
    assert recurrence.applies_in_month(d, 2026, 1)
    assert recurrence.applies_in_month(d, 2026, 5)
    assert not recurrence.applies_in_month(d, 2025, 12)  # start öncesi


def test_applies_quarterly():
    d = _Defn("quarterly", date(2026, 1, 1))
    assert recurrence.applies_in_month(d, 2026, 1)
    assert recurrence.applies_in_month(d, 2026, 4)
    assert not recurrence.applies_in_month(d, 2026, 2)


def test_applies_yearly():
    d = _Defn("yearly", date(2026, 3, 1))
    assert recurrence.applies_in_month(d, 2026, 3)
    assert recurrence.applies_in_month(d, 2027, 3)
    assert not recurrence.applies_in_month(d, 2026, 4)


def test_applies_custom_months():
    d = _Defn("custom", date(2026, 1, 1), months=[3, 6, 9])
    assert recurrence.applies_in_month(d, 2026, 6)
    assert not recurrence.applies_in_month(d, 2026, 5)


def test_applies_respects_end_date():
    d = _Defn("monthly", date(2026, 1, 1), end_date=date(2026, 3, 31))
    assert recurrence.applies_in_month(d, 2026, 3)
    assert not recurrence.applies_in_month(d, 2026, 4)  # end_date sonrası


def test_date_for_period_clamps_to_month_end():
    d = _Defn("monthly", date(2026, 1, 31), day_of_month=31)
    assert recurrence.date_for_period(d, 2026, 2) == date(2026, 2, 28)  # Şubat'a clamp
    assert recurrence.date_for_period(d, 2026, 1) == date(2026, 1, 31)


def test_iter_due_periods_monthly():
    d = _Defn("monthly", date(2026, 1, 10), day_of_month=10)
    today = date(2026, 3, 15)
    periods = list(recurrence.iter_due_periods(d, today))
    assert [(y, m) for y, m, _ in periods] == [(2026, 1), (2026, 2), (2026, 3)]
    assert periods[0][2] == date(2026, 1, 10)


def test_iter_due_periods_skips_future_payment_day():
    # Ödeme günü 20; bugün ayın 15'i → bu ay henüz gelmedi, atlanır
    d = _Defn("monthly", date(2026, 1, 20), day_of_month=20)
    today = date(2026, 3, 15)
    periods = [(y, m) for y, m, _ in recurrence.iter_due_periods(d, today)]
    assert periods == [(2026, 1), (2026, 2)]  # Mart (3) atlanır


def test_iter_due_periods_quarterly():
    d = _Defn("quarterly", date(2026, 1, 5), day_of_month=5)
    today = date(2026, 8, 10)
    periods = [(y, m) for y, m, _ in recurrence.iter_due_periods(d, today)]
    assert periods == [(2026, 1), (2026, 4), (2026, 7)]
