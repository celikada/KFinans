"""Periyodik (recurring) tanımlar için ortak dönem hesaplama yardımcıları.

`RecurringIncome` ve `PlannedExpense` aynı recurrence şemasını paylaşır
(recurrence/months/day_of_month/start_date/end_date). Bu modül duck-typed çalışır:
`defn` bu alanlara sahip herhangi bir nesne olabilir. Hem gelir hem gider realize
ve "bekleyen dönem" (pending) hesabı bu util'i kullanır (DRY).
"""

from __future__ import annotations

import calendar
from collections.abc import Iterator
from datetime import date


def applies_in_month(defn, year: int, month: int) -> bool:
    """Periyodik tanımın verilen ay içinde geçerli olup olmadığı."""
    last_day = calendar.monthrange(year, month)[1]
    first_of_month = date(year, month, 1)
    last_of_month = date(year, month, last_day)

    if defn.start_date > last_of_month:
        return False
    if defn.end_date is not None and defn.end_date < first_of_month:
        return False

    rec = defn.recurrence
    months_since = (year * 12 + month) - (defn.start_date.year * 12 + defn.start_date.month)

    if rec == "one_time":
        return defn.start_date.year == year and defn.start_date.month == month
    if rec == "monthly":
        return months_since >= 0
    if rec == "quarterly":
        return months_since >= 0 and months_since % 3 == 0
    if rec == "biannual":
        return months_since >= 0 and months_since % 6 == 0
    if rec == "yearly":
        return defn.start_date.month == month and defn.start_date.year <= year
    if rec == "custom":
        return defn.months is not None and month in defn.months and defn.start_date.year <= year
    return False


def date_for_period(defn, year: int, month: int) -> date:
    """Tanımın o ay-yıl için 'gerçekleştiği gün' tarihi.

    day_of_month o ayın son gününden büyükse son güne çekilir.
    """
    last_day = calendar.monthrange(year, month)[1]
    day = min(defn.day_of_month, last_day)
    return date(year, month, day)


def iter_due_periods(defn, today: date) -> Iterator[tuple[int, int, date]]:
    """start_date'ten today'e kadar, ödeme günü gelmiş geçerli dönemleri üretir.

    Her öğe `(year, month, date_for_period)`. `applies_in_month` False olan veya
    ödeme günü today'den ileride olan aylar atlanır (future-dated kayıt yaratılmaz).
    """
    y, m = defn.start_date.year, defn.start_date.month
    while date(y, m, 1) <= today:
        if applies_in_month(defn, y, m):
            target = date_for_period(defn, y, m)
            if target <= today:
                yield y, m, target
        m += 1
        if m > 12:
            m = 1
            y += 1
