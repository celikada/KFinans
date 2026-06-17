"""Yıllık nakit akış projeksiyonu — geçmiş + gelecek aylar.

Her ay için:
  Gelir = incomes(actual) + recurring_incomes(forecast, gelecek ay)
  Gider = expenses(actual, çift sayım filtresi) + credit_card_statements +
          planned_expenses(forecast, çift sayım filtresi) + installments

Bu ay (current month) ve geçmiş için actual; gelecek ay için forecast.
Net = Gelir - Gider.
"""

import calendar
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.credit_card import CreditCard, CreditCardInstallment, CreditCardStatement
from app.models.expense import Expense
from app.models.income import Income
from app.models.planned_expense import PlannedExpense
from app.models.recurring_income import RecurringIncome
from app.models.recurring_skip import RecurringSkip
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import PROVIDERS
from app.services import currency as currency_svc
from app.services import display_currency as display_svc

router = APIRouter(prefix="/cash-flow", tags=["cash-flow"])

_ISTANBUL = ZoneInfo("Europe/Istanbul")


class CashFlowMonth(BaseModel):
    month: int
    income_actual: Decimal  # gerçekleşen gelir (incomes)
    income_forecast: Decimal  # tahmini gelir (recurring_incomes)
    expense_actual: Decimal  # gerçekleşen gider (expenses + ekstre)
    expense_forecast: Decimal  # tahmini gider (planned + installments)
    income_total: Decimal  # actual + forecast (görüntü için)
    expense_total: Decimal  # actual + forecast
    net: Decimal  # income_total - expense_total
    is_past: bool  # bu ay'dan eski mi (UI'da farklı renk)
    # Görüntüleme para birimi (Faz B): actual → tarihsel, forecast → güncel kur.
    income_total_display: Decimal = Decimal(0)
    expense_total_display: Decimal = Decimal(0)
    net_display: Decimal = Decimal(0)
    # Kırılım display alanları (Faz C — tablo 4 sütunu için): actual=tarihsel, forecast=güncel.
    income_actual_display: Decimal = Decimal(0)
    income_forecast_display: Decimal = Decimal(0)
    expense_actual_display: Decimal = Decimal(0)
    expense_forecast_display: Decimal = Decimal(0)


class CashFlowYear(BaseModel):
    year: int
    months: list[CashFlowMonth]
    total_income: Decimal
    total_expense: Decimal
    total_net: Decimal
    display_currency: str = "TRY"
    total_income_display: Decimal = Decimal(0)
    total_expense_display: Decimal = Decimal(0)
    total_net_display: Decimal = Decimal(0)


class CashFlowItem(BaseModel):
    """Bir ayın gelir/gider toplamını oluşturan tek kalem (detay görünümü)."""

    kind: str  # "actual" | "forecast"
    category: str  # income|expense|statement|installment|recurring_income|planned
    label: str
    sub_label: str | None = None
    date: date_type | None = None
    amount: Decimal  # kalemin kendi para birimindeki tutarı
    currency: str
    amount_tl: Decimal  # TL karşılığı (toplama giren değer)
    # Görüntüleme para birimi (Faz B): kalemin date'i varsa tarihsel, yoksa güncel.
    amount_display: Decimal = Decimal(0)


class CashFlowMonthDetail(BaseModel):
    """Tek bir ayın itemize edilmiş gelir/gider dökümü.

    Toplamlar ``GET /cash-flow`` ile bire bir tutar (aynı çift-sayım/pending/taksit
    kuralları); kalemler tek tek listelenir."""

    year: int
    month: int
    is_past: bool
    is_current: bool
    income_items: list[CashFlowItem]
    expense_items: list[CashFlowItem]
    income_total: Decimal
    expense_total: Decimal
    net: Decimal
    display_currency: str = "TRY"
    income_total_display: Decimal = Decimal(0)
    expense_total_display: Decimal = Decimal(0)
    net_display: Decimal = Decimal(0)


def _applies_planned_in_month(pe: PlannedExpense, year: int, month: int) -> bool:
    """planned_expenses _applies_in_month logic (kopya, döngüsel import önlemi)."""
    last_day = calendar.monthrange(year, month)[1]
    first_of_month = date_type(year, month, 1)
    last_of_month = date_type(year, month, last_day)

    if pe.start_date > last_of_month:
        return False
    if pe.end_date is not None and pe.end_date < first_of_month:
        return False

    rec = pe.recurrence
    months_since = (year * 12 + month) - (pe.start_date.year * 12 + pe.start_date.month)

    if rec == "one_time":
        return pe.start_date.year == year and pe.start_date.month == month
    if rec == "monthly":
        return months_since >= 0
    if rec == "quarterly":
        return months_since >= 0 and months_since % 3 == 0
    if rec == "biannual":
        return months_since >= 0 and months_since % 6 == 0
    if rec == "yearly":
        return pe.start_date.month == month and pe.start_date.year <= year
    if rec == "custom":
        return pe.months is not None and month in pe.months and pe.start_date.year <= year
    return False


def _applies_recurring_income_in_month(ri: RecurringIncome, year: int, month: int) -> bool:
    """Aynı mantık recurring_incomes için."""
    last_day = calendar.monthrange(year, month)[1]
    first_of_month = date_type(year, month, 1)
    last_of_month = date_type(year, month, last_day)
    if ri.start_date > last_of_month:
        return False
    if ri.end_date is not None and ri.end_date < first_of_month:
        return False
    rec = ri.recurrence
    months_since = (year * 12 + month) - (ri.start_date.year * 12 + ri.start_date.month)
    if rec == "one_time":
        return ri.start_date.year == year and ri.start_date.month == month
    if rec == "monthly":
        return months_since >= 0
    if rec == "quarterly":
        return months_since >= 0 and months_since % 3 == 0
    if rec == "biannual":
        return months_since >= 0 and months_since % 6 == 0
    if rec == "yearly":
        return ri.start_date.month == month and ri.start_date.year <= year
    if rec == "custom":
        return ri.months is not None and month in ri.months and ri.start_date.year <= year
    return False


def _installment_applies_in_month(inst: CreditCardInstallment, year: int, month: int) -> bool:
    """Bir taksit kaydı verilen ay-yılı yakalar mı?

    Invariant (v0.3.7): `first_due_date` = ilk GELECEK taksit ayı,
    `installments_remaining` = projekte edilecek (gelecek) taksit sayısı.
    Yani [first_due, first_due + remaining - 1] aralığı sayılır — ekstreye düşmüş
    (geçmiş/mevcut) dilimler buraya GİRMEZ (çift sayım yok).
    """
    if inst.installments_remaining <= 0:
        return False
    start = date_type(inst.first_due_date.year, inst.first_due_date.month, 1)
    end_year = inst.first_due_date.year
    end_month = inst.first_due_date.month + inst.installments_remaining - 1
    while end_month > 12:
        end_month -= 12
        end_year += 1
    end = date_type(end_year, end_month, 1)
    target = date_type(year, month, 1)
    return start <= target <= end


def _empty_month_map() -> dict[int, Decimal]:
    return {m: Decimal(0) for m in range(1, 13)}


async def _actual_income_by_month(db: AsyncSession, user_id, year: int) -> dict[int, Decimal]:
    """Gerçekleşen gelirler (incomes) — tüm yıl, aya göre toplam.

    Çoklu para birimi (v0.3.0): gerçekleşmiş kayıt → işlem-anı kuruyla sabit
    ``amount_tl`` kullanılır (kur sonradan değişse bile bu tutar değişmez).
    """
    inc_q = await db.execute(
        select(Income.date, Income.amount_tl).where(
            Income.user_id == user_id,
            Income.date >= date_type(year, 1, 1),
            Income.date <= date_type(year, 12, 31),
        )
    )
    by_month = _empty_month_map()
    for d, amt in inc_q.all():
        by_month[d.month] += Decimal(amt)
    return by_month


async def _actual_expense_by_month(db: AsyncSession, user_id, year: int) -> dict[int, Decimal]:
    """Gerçekleşen giderler (expenses, çift sayım filtresi).

    Çoklu para birimi (v0.3.0): işlem-anı kuruyla sabit ``amount_tl`` kullanılır.
    """
    exp_q = await db.execute(
        select(Expense.date, Expense.amount_tl).where(
            Expense.user_id == user_id,
            Expense.date >= date_type(year, 1, 1),
            Expense.date <= date_type(year, 12, 31),
            or_(Expense.credit_card_id.is_(None), Expense.is_paid.is_(False)),
        )
    )
    by_month = _empty_month_map()
    for d, amt in exp_q.all():
        by_month[d.month] += Decimal(amt)
    return by_month


def _statement_effective_amount(statement_amount: Decimal, paid_at, paid_amount) -> Decimal:
    """Ekstrenin nakit-akışına giren efektif tutarı.

    Kısmi ödenmişse (paid_at + paid_amount set) o ay yalnız ÖDENEN sayılır; kalan
    kartın dönem-içi borcuna taşınıp sonraki ekstrede görünür (çift sayım yok).
    Ödenmemiş veya tam ödenmiş → statement_amount.
    """
    if paid_at is not None and paid_amount is not None:
        return Decimal(paid_amount)
    return Decimal(statement_amount)


async def _statement_by_month(db: AsyncSession, user_id, year: int, rates: dict[str, Decimal]) -> dict[int, Decimal]:
    """Kredi kartı ekstreleri (due_date hangi aya denkse o ayın gideri).

    Çoklu para birimi (v0.3.0): forecast → ekstrenin para birimi güncel kurla
    TL'ye çevrilir. Kısmi ödenen ekstre o ay yalnız ödeneni sayar (`_statement_effective_amount`).
    """
    stmt_q = await db.execute(
        select(
            CreditCardStatement.due_date,
            CreditCardStatement.statement_amount,
            CreditCardStatement.currency,
            CreditCardStatement.paid_at,
            CreditCardStatement.paid_amount,
        )
        .join(CreditCard, CreditCardStatement.card_id == CreditCard.id)
        .where(
            CreditCard.user_id == user_id,
            CreditCardStatement.due_date >= date_type(year, 1, 1),
            CreditCardStatement.due_date <= date_type(year, 12, 31),
        )
    )
    by_month = _empty_month_map()
    for due_date, amount, ccy, paid_at, paid_amount in stmt_q.all():
        effective = _statement_effective_amount(amount, paid_at, paid_amount)
        by_month[due_date.month] += currency_svc.convert_to_tl(effective, ccy, rates)
    return by_month


async def _installment_by_month(db: AsyncSession, user_id, year: int, rates: dict[str, Decimal]) -> dict[int, Decimal]:
    """Kredi kartı taksitleri (her ay monthly_amount) — gelecek aylar için.

    Çoklu para birimi (v0.3.0): taksitin para birimi güncel kurla TL'ye çevrilir.
    """
    inst_q = await db.execute(
        select(CreditCardInstallment).join(CreditCard, CreditCardInstallment.card_id == CreditCard.id).where(CreditCard.user_id == user_id)
    )
    installments = inst_q.scalars().all()
    by_month = _empty_month_map()
    for inst in installments:
        monthly_tl = currency_svc.convert_to_tl(Decimal(inst.monthly_amount), inst.currency, rates)
        for m in range(1, 13):
            if _installment_applies_in_month(inst, year, m):
                by_month[m] += monthly_tl
    return by_month


async def _recurring_income_by_month(db: AsyncSession, user_id, year: int, rates: dict[str, Decimal]) -> dict[int, Decimal]:
    """Periyodik gelirler (recurring_incomes) — gelecek için forecast.

    Çoklu para birimi (v0.3.0): güncel kurla TL'ye çevrilir.
    """
    rec_inc_q = await db.execute(select(RecurringIncome).where(RecurringIncome.user_id == user_id))
    recurring_incomes = rec_inc_q.scalars().all()
    by_month = _empty_month_map()
    for ri in recurring_incomes:
        amount_tl = currency_svc.convert_to_tl(Decimal(ri.amount), ri.currency, rates)
        for m in range(1, 13):
            if _applies_recurring_income_in_month(ri, year, m):
                by_month[m] += amount_tl
    return by_month


async def _planned_by_month(db: AsyncSession, user_id, year: int, rates: dict[str, Decimal]) -> dict[int, Decimal]:
    """Planlı giderler (planned_expenses, çift sayım filtresi).

    Çoklu para birimi (v0.3.0): güncel kurla TL'ye çevrilir.
    """
    pe_q = await db.execute(select(PlannedExpense).where(PlannedExpense.user_id == user_id))
    all_planned = pe_q.scalars().all()
    eligible_planned = [pe for pe in all_planned if pe.credit_card_id is None or not pe.is_paid]
    by_month = _empty_month_map()
    for pe in eligible_planned:
        amount_tl = currency_svc.convert_to_tl(Decimal(pe.amount), pe.currency, rates)
        for m in range(1, 13):
            if _applies_planned_in_month(pe, year, m):
                by_month[m] += amount_tl
    return by_month


async def _subscription_by_month(db: AsyncSession, user_id, year: int, rates: dict[str, Decimal]) -> dict[int, Decimal]:
    """Abonelik faturaları forecast (aktif abonelikler, ödenmemiş tutarlar — güncel kur).

    Her ay için: fatura yok → budget_amount; fatura var, ödenmemiş → bill_amount;
    fatura var, ödenmiş → 0 (gerçekleşmiş; actual'a expense üzerinden girer). Kart/nakit
    ödeme ayrımı Expense.credit_card_id ile actual tarafında çift-sayım filtresine takılır.
    """
    sub_q = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id, Subscription.active.is_(True)).options(selectinload(Subscription.bills))
    )
    by_month = _empty_month_map()
    for sub in sub_q.scalars().all():
        budget_tl = currency_svc.convert_to_tl(Decimal(sub.budget_amount), sub.currency, rates)
        bills = {(b.period_year, b.period_month): b for b in sub.bills if b.period_year == year}
        start = sub.start_date
        for m in range(1, 13):
            if (year, m) < (start.year, start.month):
                continue  # abonelik başlangıcından önce bütçe sayılmaz
            bill = bills.get((year, m))
            if bill is None:
                by_month[m] += budget_tl
            elif bill.paid_at is None:
                by_month[m] += currency_svc.convert_to_tl(Decimal(bill.bill_amount), bill.currency, rates)
            # ödenmiş → 0 (actual'da)
    return by_month


def _month_bounds(year: int, month: int) -> tuple[date_type, date_type]:
    last = calendar.monthrange(year, month)[1]
    return date_type(year, month, 1), date_type(year, month, last)


# ---------------------------------------------------------------------------
# Görüntüleme para birimi (Faz B) — ay-bazlı display map'leri
# ---------------------------------------------------------------------------
async def _actual_income_display_by_month(db: AsyncSession, user_id, year: int, display: str) -> dict[int, Decimal]:
    """Gerçekleşen gelirler — ay bazında görüntüleme-birimi (tarihsel kur)."""
    rows = (
        await db.execute(
            select(Income.date, Income.amount, Income.currency, Income.amount_tl).where(
                Income.user_id == user_id,
                Income.date >= date_type(year, 1, 1),
                Income.date <= date_type(year, 12, 31),
            )
        )
    ).all()
    return await _records_display_by_month(db, rows, display)


async def _actual_expense_display_by_month(db: AsyncSession, user_id, year: int, display: str) -> dict[int, Decimal]:
    """Gerçekleşen giderler (çift sayım filtresi) — ay bazında görüntüleme-birimi."""
    rows = (
        await db.execute(
            select(Expense.date, Expense.amount, Expense.currency, Expense.amount_tl).where(
                Expense.user_id == user_id,
                Expense.date >= date_type(year, 1, 1),
                Expense.date <= date_type(year, 12, 31),
                or_(Expense.credit_card_id.is_(None), Expense.is_paid.is_(False)),
            )
        )
    ).all()
    return await _records_display_by_month(db, rows, display)


async def _records_display_by_month(db: AsyncSession, rows, display: str) -> dict[int, Decimal]:
    """`(date, amount, currency, amount_tl)` satırlarını aya göre tarihsel-dönüşümle toplar."""
    by_month: dict[int, list] = {m: [] for m in range(1, 13)}
    tls_by_month: dict[int, list] = {m: [] for m in range(1, 13)}
    for d, amount, ccy, amt_tl in rows:
        by_month[d.month].append((Decimal(amount), ccy, d))
        tls_by_month[d.month].append(Decimal(amt_tl))
    out = _empty_month_map()
    for m in range(1, 13):
        if by_month[m]:
            out[m] = await display_svc.convert_realized(db, by_month[m], display, amount_tls=tls_by_month[m])
    return out


def _to_display_map(tl_map: dict[int, Decimal], display: str, rates: dict[str, Decimal]) -> dict[int, Decimal]:
    """TL ay-haritasını güncel kurla display birimine çevirir (forecast/cari kalemler)."""
    return {m: display_svc.tl_to_display(v, display, rates) for m, v in tl_map.items()}


async def _pending_planned_for_month(db: AsyncSession, user_id, year: int, month: int, rates: dict[str, Decimal]) -> Decimal:
    """BU AY geçerli ama henüz realize edilmemiş ve skip edilmemiş planlı giderler.

    Bu ay (current month) için forecast'a girer: ödeme günü ay içinde ileride olup
    henüz gerçekleşmeyen kira/aidat gibi kayıtlar "tahmini gider" olarak sayılır
    (aksi halde ne actual'da ne forecast'ta görünmeyip arada kaybolurlardı).
    Realize edilmiş olanlar zaten actual'da olduğu için hariç (çift sayım yok)."""
    pe_q = await db.execute(select(PlannedExpense).where(PlannedExpense.user_id == user_id))
    all_planned = pe_q.scalars().all()
    eligible = [pe for pe in all_planned if (pe.credit_card_id is None or not pe.is_paid) and _applies_planned_in_month(pe, year, month)]
    if not eligible:
        return Decimal(0)

    start, end = _month_bounds(year, month)
    realized_q = await db.execute(
        select(Expense.planned_expense_id).where(
            Expense.user_id == user_id,
            Expense.planned_expense_id.is_not(None),
            Expense.date >= start,
            Expense.date <= end,
        )
    )
    realized_ids = {r for (r,) in realized_q.all()}
    skip_q = await db.execute(
        select(RecurringSkip.ref_id).where(
            RecurringSkip.user_id == user_id,
            RecurringSkip.kind == "expense",
            RecurringSkip.period_year == year,
            RecurringSkip.period_month == month,
        )
    )
    skipped_ids = {r for (r,) in skip_q.all()}

    total = Decimal(0)
    for pe in eligible:
        if pe.id in realized_ids or pe.id in skipped_ids:
            continue
        total += currency_svc.convert_to_tl(Decimal(pe.amount), pe.currency, rates)
    return total


async def _pending_recurring_income_for_month(db: AsyncSession, user_id, year: int, month: int, rates: dict[str, Decimal]) -> Decimal:
    """BU AY geçerli ama henüz realize/skip edilmemiş periyodik gelirler (forecast).

    Planlı gider ile simetrik: bu ay beklenen ama henüz gerçekleşmemiş maaş/kira
    geliri "tahmini gelir" olarak sayılır."""
    ri_q = await db.execute(select(RecurringIncome).where(RecurringIncome.user_id == user_id))
    all_ri = ri_q.scalars().all()
    eligible = [ri for ri in all_ri if _applies_recurring_income_in_month(ri, year, month)]
    if not eligible:
        return Decimal(0)

    realized_q = await db.execute(
        select(Income.recurring_income_id).where(
            Income.user_id == user_id,
            Income.recurring_income_id.is_not(None),
            *_month_filter(year, month),
        )
    )
    realized_ids = {r for (r,) in realized_q.all()}
    skip_q = await db.execute(
        select(RecurringSkip.ref_id).where(
            RecurringSkip.user_id == user_id,
            RecurringSkip.kind == "income",
            RecurringSkip.period_year == year,
            RecurringSkip.period_month == month,
        )
    )
    skipped_ids = {r for (r,) in skip_q.all()}

    total = Decimal(0)
    for ri in eligible:
        if ri.id in realized_ids or ri.id in skipped_ids:
            continue
        total += currency_svc.convert_to_tl(Decimal(ri.amount), ri.currency, rates)
    return total


def _month_filter(year: int, month: int):
    start, end = _month_bounds(year, month)
    return (Income.date >= start, Income.date <= end)


def _forecast_for_month(
    m: int,
    is_past: bool,
    is_current: bool,
    pending_income: Decimal,
    pending_expense: Decimal,
    statement: dict[int, Decimal],
    recurring_income: dict[int, Decimal],
    planned: dict[int, Decimal],
    installment: dict[int, Decimal],
    subscription: dict[int, Decimal],
) -> tuple[Decimal, Decimal]:
    """Bir ay için (income_forecast, expense_forecast) — actual ekstre hariç.

    Bu ay (current): pending periyodikler + abonelik; geçmiş: 0; gelecek: tam periyodik
    forecast + abonelik. statement zaten actual sayılır (expense_actual'a girer).
    Abonelik forecast'i current + gelecek aynıdır (ödenmemiş budget/issued tutar)."""
    if is_current:
        return pending_income, pending_expense + installment[m] + subscription[m]
    if is_past:
        return Decimal(0), Decimal(0)
    return recurring_income[m], planned[m] + installment[m] + subscription[m]


def _build_month_row(
    m: int,
    is_past: bool,
    is_current: bool,
    pending_income: Decimal,
    pending_expense: Decimal,
    actual_income: dict[int, Decimal],
    actual_expense: dict[int, Decimal],
    statement: dict[int, Decimal],
    recurring_income: dict[int, Decimal],
    planned: dict[int, Decimal],
    installment: dict[int, Decimal],
    subscription: dict[int, Decimal],
    display_maps: dict | None = None,
) -> CashFlowMonth:
    """Tek bir ay satırını üretir (actual + forecast birleştirme).

    `display_maps` verilirse (display != TRY) görüntüleme-birimi toplamları da
    doldurulur; aksi halde *_display == TL (hızlı yol)."""
    income_actual = actual_income[m]
    expense_actual = actual_expense[m] + statement[m]
    income_forecast, expense_forecast = _forecast_for_month(
        m, is_past, is_current, pending_income, pending_expense, statement, recurring_income, planned, installment, subscription
    )
    income_total = income_actual + income_forecast
    expense_total = expense_actual + expense_forecast

    if display_maps is None:
        # TRY hızlı yolu: kırılımlar da TL ile birebir.
        income_actual_d = income_actual
        income_forecast_d = income_forecast
        expense_actual_d = expense_actual
        expense_forecast_d = expense_forecast
    else:
        d_inc_f, d_exp_f = _forecast_for_month(
            m,
            is_past,
            is_current,
            display_maps["pending_income"],
            display_maps["pending_expense"],
            display_maps["statement"],
            display_maps["recurring_income"],
            display_maps["planned"],
            display_maps["installment"],
            display_maps["subscription"],
        )
        income_actual_d = display_svc.quantize_tl(display_maps["actual_income"][m])
        income_forecast_d = display_svc.quantize_tl(d_inc_f)
        # Gerçekleşen gider = expenses (tarihsel) + ekstreler (cari, statement güncel kur).
        expense_actual_d = display_svc.quantize_tl(display_maps["actual_expense"][m] + display_maps["statement"][m])
        expense_forecast_d = display_svc.quantize_tl(d_exp_f)

    income_total_display = display_svc.quantize_tl(income_actual_d + income_forecast_d)
    expense_total_display = display_svc.quantize_tl(expense_actual_d + expense_forecast_d)

    return CashFlowMonth(
        month=m,
        income_actual=income_actual,
        income_forecast=income_forecast,
        expense_actual=expense_actual,
        expense_forecast=expense_forecast,
        income_total=income_total,
        expense_total=expense_total,
        net=income_total - expense_total,
        is_past=is_past,
        income_total_display=income_total_display,
        expense_total_display=expense_total_display,
        net_display=display_svc.quantize_tl(income_total_display - expense_total_display),
        income_actual_display=income_actual_d,
        income_forecast_display=income_forecast_d,
        expense_actual_display=expense_actual_d,
        expense_forecast_display=expense_forecast_d,
    )


async def _build_display_maps(db: AsyncSession, uid, year: int, current_year: int, current_month: int, display: str, rates: dict[str, Decimal]) -> dict:
    """display != TRY için ay-bazlı görüntüleme-birimi map'leri (Faz B).

    actual income/expense → tarihsel (kayıt-bazlı); statement/installment/recurring/
    planned + pending → güncel kur (TL map'leri tl_to_display ile çevrilir)."""
    actual_income_d = await _actual_income_display_by_month(db, uid, year, display)
    actual_expense_d = await _actual_expense_display_by_month(db, uid, year, display)
    statement_tl = await _statement_by_month(db, uid, year, rates)
    installment_tl = await _installment_by_month(db, uid, year, rates)
    recurring_tl = await _recurring_income_by_month(db, uid, year, rates)
    planned_tl = await _planned_by_month(db, uid, year, rates)
    subscription_tl = await _subscription_by_month(db, uid, year, rates)
    pending_income_d = Decimal(0)
    pending_expense_d = Decimal(0)
    if year == current_year:
        pi = await _pending_recurring_income_for_month(db, uid, year, current_month, rates)
        pe = await _pending_planned_for_month(db, uid, year, current_month, rates)
        pending_income_d = display_svc.tl_to_display(pi, display, rates)
        pending_expense_d = display_svc.tl_to_display(pe, display, rates)
    return {
        "actual_income": actual_income_d,
        "actual_expense": actual_expense_d,
        "statement": _to_display_map(statement_tl, display, rates),
        "installment": _to_display_map(installment_tl, display, rates),
        "recurring_income": _to_display_map(recurring_tl, display, rates),
        "planned": _to_display_map(planned_tl, display, rates),
        "subscription": _to_display_map(subscription_tl, display, rates),
        "pending_income": pending_income_d,
        "pending_expense": pending_expense_d,
    }


@router.get("", response_model=CashFlowYear)
async def get_cash_flow(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Query(ge=2020, le=2100)],
    display: Annotated[str | None, Query()] = None,
):
    """Yıllık nakit akış projeksiyonu (12 ay)."""
    today = datetime.now(_ISTANBUL).date()
    current_year = today.year
    current_month = today.month
    uid = current_user.id
    display_ccy = display_svc.normalize_display(display, current_user.default_currency)

    # Forecast hesapları için güncel kurları bir kez çek (TRY=1 dahil).
    rates = await currency_svc.fetch_rates()

    actual_income = await _actual_income_by_month(db, uid, year)
    actual_expense = await _actual_expense_by_month(db, uid, year)
    statement = await _statement_by_month(db, uid, year, rates)
    installment = await _installment_by_month(db, uid, year, rates)
    recurring_income = await _recurring_income_by_month(db, uid, year, rates)
    planned = await _planned_by_month(db, uid, year, rates)
    subscription = await _subscription_by_month(db, uid, year, rates)

    # Bu ay (current month) için henüz gerçekleşmemiş periyodik forecast (kira/aidat
    # gibi ödeme günü ay içinde ileride olanlar). Yalnızca görüntülenen yıl bu yılsa.
    pending_income = Decimal(0)
    pending_expense = Decimal(0)
    if year == current_year:
        pending_income = await _pending_recurring_income_for_month(db, uid, year, current_month, rates)
        pending_expense = await _pending_planned_for_month(db, uid, year, current_month, rates)

    # Görüntüleme map'leri (TRY → None hızlı yol, *_display == TL).
    display_maps = None
    if display_ccy != display_svc.TRY:
        display_maps = await _build_display_maps(db, uid, year, current_year, current_month, display_ccy, rates)

    # Aylık birleştirme: actual = geçmiş+bu ay; forecast = gelecek aylar + bu ay pending.
    months_out: list[CashFlowMonth] = []
    total_income = Decimal(0)
    total_expense = Decimal(0)
    total_income_display = Decimal(0)
    total_expense_display = Decimal(0)
    for m in range(1, 13):
        is_current = year == current_year and m == current_month
        is_past = (year < current_year) or (year == current_year and m <= current_month)
        row = _build_month_row(
            m,
            is_past,
            is_current,
            pending_income,
            pending_expense,
            actual_income,
            actual_expense,
            statement,
            recurring_income,
            planned,
            installment,
            subscription,
            display_maps,
        )
        total_income += row.income_total
        total_expense += row.expense_total
        total_income_display += row.income_total_display
        total_expense_display += row.expense_total_display
        months_out.append(row)

    return CashFlowYear(
        year=year,
        months=months_out,
        total_income=total_income,
        total_expense=total_expense,
        total_net=total_income - total_expense,
        display_currency=display_ccy,
        total_income_display=display_svc.quantize_tl(total_income_display),
        total_expense_display=display_svc.quantize_tl(total_expense_display),
        total_net_display=display_svc.quantize_tl(total_income_display - total_expense_display),
    )


async def _income_items_for_month(
    db: AsyncSession, user_id, year: int, month: int, is_past: bool, is_current: bool, rates: dict[str, Decimal]
) -> list[CashFlowItem]:
    """Bir ayın gelir kalemleri (actual incomes + forecast recurring) — toplama uyumlu."""
    start, end = _month_bounds(year, month)
    items: list[CashFlowItem] = []

    # 1) Gerçekleşen gelirler (incomes) — her ay için (geçmiş/gelecek farketmez).
    inc_q = await db.execute(select(Income).where(Income.user_id == user_id, Income.date >= start, Income.date <= end).order_by(Income.date))
    for inc in inc_q.scalars().all():
        items.append(
            CashFlowItem(
                kind="actual",
                category="income",
                label=inc.description or inc.category,
                sub_label=("periyodik" if inc.recurring_income_id is not None else inc.category),
                date=inc.date,
                amount=Decimal(inc.amount),
                currency=inc.currency,
                amount_tl=Decimal(inc.amount_tl),
            )
        )

    # 2) Forecast (periyodik gelir): current ay → pending (realize/skip edilmemiş);
    #    gelecek ay → uygulanan tüm periyodikler; strictly geçmiş → yok.
    if is_current or not is_past:
        ri_q = await db.execute(select(RecurringIncome).where(RecurringIncome.user_id == user_id))
        eligible = [ri for ri in ri_q.scalars().all() if _applies_recurring_income_in_month(ri, year, month)]
        skip_ids: set[int] = set()
        realized_ids: set[int] = set()
        if is_current and eligible:
            realized_q = await db.execute(
                select(Income.recurring_income_id).where(
                    Income.user_id == user_id,
                    Income.recurring_income_id.is_not(None),
                    Income.date >= start,
                    Income.date <= end,
                )
            )
            realized_ids = {r for (r,) in realized_q.all()}
            skip_q = await db.execute(
                select(RecurringSkip.ref_id).where(
                    RecurringSkip.user_id == user_id,
                    RecurringSkip.kind == "income",
                    RecurringSkip.period_year == year,
                    RecurringSkip.period_month == month,
                )
            )
            skip_ids = {r for (r,) in skip_q.all()}
        for ri in eligible:
            if ri.id in realized_ids or ri.id in skip_ids:
                continue
            items.append(
                CashFlowItem(
                    kind="forecast",
                    category="recurring_income",
                    label=ri.title,
                    sub_label=ri.category,
                    date=None,
                    amount=Decimal(ri.amount),
                    currency=ri.currency,
                    amount_tl=currency_svc.convert_to_tl(Decimal(ri.amount), ri.currency, rates),
                )
            )
    return items


async def _expense_items_for_month(
    db: AsyncSession, user_id, year: int, month: int, is_past: bool, is_current: bool, rates: dict[str, Decimal]
) -> list[CashFlowItem]:
    """Bir ayın gider kalemleri (actual expenses + ekstreler + forecast planned/taksit)."""
    start, end = _month_bounds(year, month)
    items: list[CashFlowItem] = []

    # Kart adı haritası (ekstre + taksit etiketleri için).
    card_q = await db.execute(select(CreditCard.id, CreditCard.name).where(CreditCard.user_id == user_id))
    card_names = dict(card_q.all())

    # 1) Gerçekleşen giderler (çift sayım filtresi: kart + ödendi olanlar hariç).
    exp_q = await db.execute(
        select(Expense)
        .where(
            Expense.user_id == user_id,
            Expense.date >= start,
            Expense.date <= end,
            or_(Expense.credit_card_id.is_(None), Expense.is_paid.is_(False)),
        )
        .order_by(Expense.date)
    )
    for exp in exp_q.scalars().all():
        items.append(
            CashFlowItem(
                kind="actual",
                category="expense",
                label=exp.description or exp.category,
                sub_label=exp.category,
                date=exp.date,
                amount=Decimal(exp.amount),
                currency=exp.currency,
                amount_tl=Decimal(exp.amount_tl),
            )
        )

    # 2) Kredi kartı ekstreleri (due_date bu aya denk) — her ay actual sayılır.
    stmt_q = await db.execute(
        select(CreditCardStatement)
        .join(CreditCard, CreditCardStatement.card_id == CreditCard.id)
        .where(CreditCard.user_id == user_id, CreditCardStatement.due_date >= start, CreditCardStatement.due_date <= end)
        .order_by(CreditCardStatement.due_date)
    )
    for st in stmt_q.scalars().all():
        effective = _statement_effective_amount(st.statement_amount, st.paid_at, st.paid_amount)
        partial = st.paid_at is not None and st.paid_amount is not None and Decimal(st.paid_amount) < Decimal(st.statement_amount)
        if st.paid_at is None:
            paid_label = ""
        elif partial:
            paid_label = " · kısmi ödendi"
        else:
            paid_label = " · ödendi"
        items.append(
            CashFlowItem(
                kind="actual",
                category="statement",
                label=card_names.get(st.card_id, "Kredi kartı"),
                sub_label=f"{st.period_month:02d}/{st.period_year} ekstresi" + paid_label,
                date=st.due_date,
                amount=effective,
                currency=st.currency,
                amount_tl=currency_svc.convert_to_tl(effective, st.currency, rates),
            )
        )

    # 3) Forecast: current → pending planned + taksit; gelecek → planned + taksit;
    #    strictly geçmiş → yok.
    if is_current or not is_past:
        items.extend(await _planned_forecast_items(db, user_id, year, month, is_current, rates))
        items.extend(await _installment_forecast_items(db, user_id, year, month, card_names, rates))
        items.extend(await _subscription_forecast_items(db, user_id, year, month, rates))
    return items


async def _subscription_forecast_items(db: AsyncSession, user_id, year: int, month: int, rates: dict[str, Decimal]) -> list[CashFlowItem]:
    """Abonelik fatura forecast kalemleri (aktif + ödenmemiş; budget veya issued tutar)."""
    sub_q = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id, Subscription.active.is_(True)).options(selectinload(Subscription.bills))
    )
    items: list[CashFlowItem] = []
    for sub in sub_q.scalars().all():
        if (year, month) < (sub.start_date.year, sub.start_date.month):
            continue  # başlangıçtan önce
        bill = next((b for b in sub.bills if b.period_year == year and b.period_month == month), None)
        if bill is not None and bill.paid_at is not None:
            continue  # ödenmiş → actual'da
        provider_name = PROVIDERS.get(sub.provider_code, (sub.provider_code, sub.category))[0]
        if bill is None:
            amount, ccy, sub_label = Decimal(sub.budget_amount), sub.currency, "bütçe (tahmini)"
        else:
            amount, ccy, sub_label = Decimal(bill.bill_amount), bill.currency, "fatura geldi"
        items.append(
            CashFlowItem(
                kind="forecast",
                category="subscription",
                label=sub.label or provider_name,
                sub_label=f"{provider_name} · {sub_label}",
                date=None,
                amount=amount,
                currency=ccy,
                amount_tl=currency_svc.convert_to_tl(amount, ccy, rates),
            )
        )
    return items


async def _planned_forecast_items(db: AsyncSession, user_id, year: int, month: int, is_current: bool, rates: dict[str, Decimal]) -> list[CashFlowItem]:
    """Planlı gider forecast kalemleri (çift sayım filtresi + current ay realize/skip hariç)."""
    pe_q = await db.execute(select(PlannedExpense).where(PlannedExpense.user_id == user_id))
    eligible = [pe for pe in pe_q.scalars().all() if (pe.credit_card_id is None or not pe.is_paid) and _applies_planned_in_month(pe, year, month)]
    realized_ids, skip_ids = await _realized_and_skipped_expense_ids(db, user_id, year, month, is_current and bool(eligible))
    return [
        CashFlowItem(
            kind="forecast",
            category="planned",
            label=pe.title,
            sub_label=pe.category,
            date=None,
            amount=Decimal(pe.amount),
            currency=pe.currency,
            amount_tl=currency_svc.convert_to_tl(Decimal(pe.amount), pe.currency, rates),
        )
        for pe in eligible
        if pe.id not in realized_ids and pe.id not in skip_ids
    ]


async def _realized_and_skipped_expense_ids(db: AsyncSession, user_id, year: int, month: int, active: bool) -> tuple[set, set]:
    """Current ay için realize edilmiş (planned_expense_id) + skip edilmiş pe id'leri."""
    if not active:
        return set(), set()
    start, end = _month_bounds(year, month)
    realized_q = await db.execute(
        select(Expense.planned_expense_id).where(
            Expense.user_id == user_id,
            Expense.planned_expense_id.is_not(None),
            Expense.date >= start,
            Expense.date <= end,
        )
    )
    realized_ids = {r for (r,) in realized_q.all()}
    skip_q = await db.execute(
        select(RecurringSkip.ref_id).where(
            RecurringSkip.user_id == user_id,
            RecurringSkip.kind == "expense",
            RecurringSkip.period_year == year,
            RecurringSkip.period_month == month,
        )
    )
    skip_ids = {r for (r,) in skip_q.all()}
    return realized_ids, skip_ids


async def _installment_forecast_items(db: AsyncSession, user_id, year: int, month: int, card_names: dict, rates: dict[str, Decimal]) -> list[CashFlowItem]:
    """Kredi kartı taksiti forecast kalemleri (yalnızca GELECEK dilimler — v0.3.7 invariant)."""
    inst_q = await db.execute(
        select(CreditCardInstallment).join(CreditCard, CreditCardInstallment.card_id == CreditCard.id).where(CreditCard.user_id == user_id)
    )
    return [
        CashFlowItem(
            kind="forecast",
            category="installment",
            label=f"{card_names.get(inst.card_id, 'Kredi kartı')} · {inst.description}",
            sub_label=f"{inst.installments_remaining}/{inst.installments_total} taksit kaldı · ilk vade {inst.first_due_date.isoformat()}",
            date=None,
            amount=Decimal(inst.monthly_amount),
            currency=inst.currency,
            amount_tl=currency_svc.convert_to_tl(Decimal(inst.monthly_amount), inst.currency, rates),
        )
        for inst in inst_q.scalars().all()
        if _installment_applies_in_month(inst, year, month)
    ]


async def _fill_item_displays(db: AsyncSession, items: list[CashFlowItem], display: str, rates: dict[str, Decimal]) -> Decimal:
    """Her kalemin `amount_display`'ini doldurur + display-birimi toplamı döner (Faz B).

    date'i olan kalem (actual) → tarihsel kur (kayıt-bazlı); date yoksa (forecast)
    → güncel kur. TRY display → amount_display = amount_tl (hızlı yol)."""
    if display == display_svc.TRY:
        total = Decimal(0)
        for it in items:
            it.amount_display = Decimal(it.amount_tl)
            total += it.amount_tl
        return display_svc.quantize_tl(total)

    # Tarihsel gereken (date'li) kalemleri tek seferde dönüştür (toplu cache).
    dated = [(Decimal(it.amount), it.currency, it.date) for it in items if it.date is not None]
    dated_tls = [Decimal(it.amount_tl) for it in items if it.date is not None]
    # convert_realized listenin toplamını döner; tek tek lazım → sırayla yine
    # kullanırız ama tek matris paylaşılsın diye önce cache'i ısıtırız.
    if dated:
        await display_svc.convert_realized(db, dated, display, amount_tls=dated_tls)

    total = Decimal(0)
    for it in items:
        if it.date is not None:
            val = await display_svc.convert_realized(db, [(Decimal(it.amount), it.currency, it.date)], display, amount_tls=[Decimal(it.amount_tl)])
        else:
            val = display_svc.convert_forecast(Decimal(it.amount), it.currency, display, rates)
        it.amount_display = val
        total += val
    return display_svc.quantize_tl(total)


@router.get("/{year}/{month}/detail", response_model=CashFlowMonthDetail)
async def get_cash_flow_month_detail(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Path(ge=2020, le=2100)],
    month: Annotated[int, Path(ge=1, le=12)],
    display: Annotated[str | None, Query()] = None,
):
    """Tek bir ayın gelir/gider kalemlerinin dökümü (popup detayı).

    Toplamlar ``GET /cash-flow``'daki o ayın ``income_total``/``expense_total``
    değerleriyle bire bir tutar. `display` (Faz B): her kaleme `amount_display`
    eklenir (date'li → tarihsel, forecast → güncel)."""
    today = datetime.now(_ISTANBUL).date()
    is_current = year == today.year and month == today.month
    is_past = (year < today.year) or (year == today.year and month <= today.month)
    uid = current_user.id
    display_ccy = display_svc.normalize_display(display, current_user.default_currency)

    rates = await currency_svc.fetch_rates()
    income_items = await _income_items_for_month(db, uid, year, month, is_past, is_current, rates)
    expense_items = await _expense_items_for_month(db, uid, year, month, is_past, is_current, rates)

    income_total = sum((it.amount_tl for it in income_items), Decimal(0))
    expense_total = sum((it.amount_tl for it in expense_items), Decimal(0))
    income_total_display = await _fill_item_displays(db, income_items, display_ccy, rates)
    expense_total_display = await _fill_item_displays(db, expense_items, display_ccy, rates)
    return CashFlowMonthDetail(
        year=year,
        month=month,
        is_past=is_past,
        is_current=is_current,
        income_items=income_items,
        expense_items=expense_items,
        income_total=income_total,
        expense_total=expense_total,
        net=income_total - expense_total,
        display_currency=display_ccy,
        income_total_display=income_total_display,
        expense_total_display=expense_total_display,
        net_display=display_svc.quantize_tl(income_total_display - expense_total_display),
    )


# ---------------------------------------------------------------------------
# Rapor indirme endpoint'leri (Excel + PDF)
# ---------------------------------------------------------------------------
async def _build_cash_flow_data(year: int, current_user: User, db: AsyncSession):
    """get_cash_flow ile aynı hesabı yapar, model'leri dict'e çevirir."""
    result = await get_cash_flow(current_user, db, year)
    months_dict = [
        {
            "month": m.month,
            "income_actual": m.income_actual,
            "income_forecast": m.income_forecast,
            "expense_actual": m.expense_actual,
            "expense_forecast": m.expense_forecast,
            "net": m.net,
            "is_past": m.is_past,
        }
        for m in result.months
    ]
    totals = {
        "total_income": result.total_income,
        "total_expense": result.total_expense,
        "total_net": result.total_net,
    }
    return months_dict, totals


@router.get("/report.xlsx")
async def download_cash_flow_xlsx(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Query(ge=2020, le=2100)],
):
    """Yıllık nakit akış Excel raporu."""
    from app.services.reports import cash_flow_to_xlsx

    months, totals = await _build_cash_flow_data(year, current_user, db)
    content = cash_flow_to_xlsx(year, months, totals)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=nakit-akis-{year}.xlsx"},
    )


@router.get("/report.pdf")
async def download_cash_flow_pdf(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Query(ge=2020, le=2100)],
):
    """Yıllık nakit akış PDF raporu."""
    from app.services.reports import cash_flow_to_pdf

    months, totals = await _build_cash_flow_data(year, current_user, db)
    content = cash_flow_to_pdf(year, months, totals)
    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=nakit-akis-{year}.pdf"},
    )
