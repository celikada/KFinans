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

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.credit_card import CreditCard, CreditCardInstallment, CreditCardStatement
from app.models.expense import Expense
from app.models.income import Income
from app.models.planned_expense import PlannedExpense
from app.models.recurring_income import RecurringIncome
from app.models.recurring_skip import RecurringSkip
from app.models.user import User
from app.services import currency as currency_svc

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


class CashFlowYear(BaseModel):
    year: int
    months: list[CashFlowMonth]
    total_income: Decimal
    total_expense: Decimal
    total_net: Decimal


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

    İlk vade ile installments_total kadar ay sürer. first_due ay'ı dahil
    sayılır (installments_total - 1 ay daha sonra biter).
    """
    start = date_type(inst.first_due_date.year, inst.first_due_date.month, 1)
    end_year = inst.first_due_date.year
    end_month = inst.first_due_date.month + inst.installments_total - 1
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


async def _statement_by_month(db: AsyncSession, user_id, year: int, rates: dict[str, Decimal]) -> dict[int, Decimal]:
    """Kredi kartı ekstreleri (due_date hangi aya denkse o ayın gideri).

    Çoklu para birimi (v0.3.0): forecast → ekstrenin para birimi güncel kurla
    TL'ye çevrilir.
    """
    stmt_q = await db.execute(
        select(CreditCardStatement.due_date, CreditCardStatement.statement_amount, CreditCardStatement.currency)
        .join(CreditCard, CreditCardStatement.card_id == CreditCard.id)
        .where(
            CreditCard.user_id == user_id,
            CreditCardStatement.due_date >= date_type(year, 1, 1),
            CreditCardStatement.due_date <= date_type(year, 12, 31),
        )
    )
    by_month = _empty_month_map()
    for due_date, amount, ccy in stmt_q.all():
        by_month[due_date.month] += currency_svc.convert_to_tl(Decimal(amount), ccy, rates)
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


def _month_bounds(year: int, month: int) -> tuple[date_type, date_type]:
    last = calendar.monthrange(year, month)[1]
    return date_type(year, month, 1), date_type(year, month, last)


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
) -> CashFlowMonth:
    """Tek bir ay satırını üretir (actual + forecast birleştirme)."""
    income_actual = actual_income[m]
    expense_actual = actual_expense[m] + statement[m]

    # Forecast ölçüler:
    #  - Bu ay (current): gerçekleşen + henüz gerçekleşmemiş (ödeme günü ay içinde
    #    ileride olup realize/skip edilmemiş) periyodik kayıtlar forecast'a girer —
    #    aksi halde kira/aidat gibi kayıtlar ne actual ne forecast'ta görünmezdi.
    #  - Strictly geçmiş ay: forecast 0 (yanıltıcı olmasın).
    #  - Gelecek ay: tam periyodik forecast.
    if is_current:
        income_forecast = pending_income
        expense_forecast = pending_expense + installment[m]
    elif is_past:
        income_forecast = Decimal(0)
        expense_forecast = Decimal(0)
    else:
        income_forecast = recurring_income[m]
        expense_forecast = planned[m] + installment[m]

    income_total = income_actual + income_forecast
    expense_total = expense_actual + expense_forecast
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
    )


@router.get("", response_model=CashFlowYear)
async def get_cash_flow(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Annotated[int, Query(ge=2020, le=2100)],
):
    """Yıllık nakit akış projeksiyonu (12 ay)."""
    today = datetime.now(_ISTANBUL).date()
    current_year = today.year
    current_month = today.month
    uid = current_user.id

    # Forecast hesapları için güncel kurları bir kez çek (TRY=1 dahil).
    rates = await currency_svc.fetch_rates()

    actual_income = await _actual_income_by_month(db, uid, year)
    actual_expense = await _actual_expense_by_month(db, uid, year)
    statement = await _statement_by_month(db, uid, year, rates)
    installment = await _installment_by_month(db, uid, year, rates)
    recurring_income = await _recurring_income_by_month(db, uid, year, rates)
    planned = await _planned_by_month(db, uid, year, rates)

    # Bu ay (current month) için henüz gerçekleşmemiş periyodik forecast (kira/aidat
    # gibi ödeme günü ay içinde ileride olanlar). Yalnızca görüntülenen yıl bu yılsa.
    pending_income = Decimal(0)
    pending_expense = Decimal(0)
    if year == current_year:
        pending_income = await _pending_recurring_income_for_month(db, uid, year, current_month, rates)
        pending_expense = await _pending_planned_for_month(db, uid, year, current_month, rates)

    # Aylık birleştirme: actual = geçmiş+bu ay; forecast = gelecek aylar + bu ay pending.
    months_out: list[CashFlowMonth] = []
    total_income = Decimal(0)
    total_expense = Decimal(0)
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
        )
        total_income += row.income_total
        total_expense += row.expense_total
        months_out.append(row)

    return CashFlowYear(
        year=year,
        months=months_out,
        total_income=total_income,
        total_expense=total_expense,
        total_net=total_income - total_expense,
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
