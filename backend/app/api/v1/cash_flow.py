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
from app.models.user import User

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
    """Gerçekleşen gelirler (incomes) — tüm yıl, aya göre toplam."""
    inc_q = await db.execute(
        select(Income.date, Income.amount).where(
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
    """Gerçekleşen giderler (expenses, çift sayım filtresi)."""
    exp_q = await db.execute(
        select(Expense.date, Expense.amount).where(
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


async def _statement_by_month(db: AsyncSession, user_id, year: int) -> dict[int, Decimal]:
    """Kredi kartı ekstreleri (due_date hangi aya denkse o ayın gideri)."""
    stmt_q = await db.execute(
        select(CreditCardStatement.due_date, CreditCardStatement.statement_amount)
        .join(CreditCard, CreditCardStatement.card_id == CreditCard.id)
        .where(
            CreditCard.user_id == user_id,
            CreditCardStatement.due_date >= date_type(year, 1, 1),
            CreditCardStatement.due_date <= date_type(year, 12, 31),
        )
    )
    by_month = _empty_month_map()
    for due_date, amount in stmt_q.all():
        by_month[due_date.month] += Decimal(amount)
    return by_month


async def _installment_by_month(db: AsyncSession, user_id, year: int) -> dict[int, Decimal]:
    """Kredi kartı taksitleri (her ay monthly_amount) — gelecek aylar için."""
    inst_q = await db.execute(
        select(CreditCardInstallment).join(CreditCard, CreditCardInstallment.card_id == CreditCard.id).where(CreditCard.user_id == user_id)
    )
    installments = inst_q.scalars().all()
    by_month = _empty_month_map()
    for inst in installments:
        for m in range(1, 13):
            if _installment_applies_in_month(inst, year, m):
                by_month[m] += Decimal(inst.monthly_amount)
    return by_month


async def _recurring_income_by_month(db: AsyncSession, user_id, year: int) -> dict[int, Decimal]:
    """Periyodik gelirler (recurring_incomes) — gelecek için forecast."""
    rec_inc_q = await db.execute(select(RecurringIncome).where(RecurringIncome.user_id == user_id))
    recurring_incomes = rec_inc_q.scalars().all()
    by_month = _empty_month_map()
    for ri in recurring_incomes:
        for m in range(1, 13):
            if _applies_recurring_income_in_month(ri, year, m):
                by_month[m] += Decimal(ri.amount)
    return by_month


async def _planned_by_month(db: AsyncSession, user_id, year: int) -> dict[int, Decimal]:
    """Planlı giderler (planned_expenses, çift sayım filtresi)."""
    pe_q = await db.execute(select(PlannedExpense).where(PlannedExpense.user_id == user_id))
    all_planned = pe_q.scalars().all()
    eligible_planned = [pe for pe in all_planned if pe.credit_card_id is None or not pe.is_paid]
    by_month = _empty_month_map()
    for pe in eligible_planned:
        for m in range(1, 13):
            if _applies_planned_in_month(pe, year, m):
                by_month[m] += Decimal(pe.amount)
    return by_month


def _build_month_row(
    m: int,
    is_past: bool,
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

    # Forecast ölçüler — geçmiş ay için 0 göster (yanıltıcı olmasın)
    if is_past:
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
    year: int = Query(..., ge=2020, le=2100),
):
    """Yıllık nakit akış projeksiyonu (12 ay)."""
    today = datetime.now(_ISTANBUL).date()
    current_year = today.year
    current_month = today.month
    uid = current_user.id

    actual_income = await _actual_income_by_month(db, uid, year)
    actual_expense = await _actual_expense_by_month(db, uid, year)
    statement = await _statement_by_month(db, uid, year)
    installment = await _installment_by_month(db, uid, year)
    recurring_income = await _recurring_income_by_month(db, uid, year)
    planned = await _planned_by_month(db, uid, year)

    # Aylık birleştirme: actual = geçmiş+bu ay; forecast = gelecek aylar.
    months_out: list[CashFlowMonth] = []
    total_income = Decimal(0)
    total_expense = Decimal(0)
    for m in range(1, 13):
        is_past = (year < current_year) or (year == current_year and m <= current_month)
        row = _build_month_row(
            m,
            is_past,
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
    year: int = Query(..., ge=2020, le=2100),
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
    year: int = Query(..., ge=2020, le=2100),
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
