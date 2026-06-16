"""Abonelik (fatura/utility) endpoint'leri.

Elektrik/doğalgaz/internet/telefon faturalarının abone no ile manuel takibi.
3 durumlu yaşam döngüsü: budget (implicit) → issued (fatura geldi) → paid (ödendi).
Ödeme şekli (nakit | kredi kartı) oluşturulan ``Expense``'in ``credit_card_id``'sini
belirler → mevcut çift-sayım kuralı kartla ödenen faturayı gider toplamından çıkarır.
"""

import logging
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.credit_card import CreditCard
from app.models.expense import Expense
from app.models.subscription import Subscription, SubscriptionBill
from app.models.user import User
from app.schemas.subscription import (
    PROVIDERS,
    ProviderOut,
    SubscriptionBillIssue,
    SubscriptionBillOut,
    SubscriptionBillPay,
    SubscriptionCreate,
    SubscriptionDuePayment,
    SubscriptionOut,
    SubscriptionPendingBill,
    SubscriptionPeriodOut,
    SubscriptionRemindersOut,
    SubscriptionSummaryOut,
    SubscriptionUpdate,
    provider_catalog,
)
from app.services import currency as currency_svc
from app.services import display_currency as display_svc
from app.services.audit import AuditAction, log_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

_ISTANBUL = ZoneInfo("Europe/Istanbul")
_SUB_NOT_FOUND = "Abonelik bulunamadı"
_BILL_NOT_FOUND = "Fatura bulunamadı"
_DUE_SOON_DAYS = 5


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _provider_or_422(code: str) -> tuple[str, str]:
    """Provider kodunu doğrula → (görünen ad, kategori). Bilinmiyorsa 422."""
    meta = PROVIDERS.get(code)
    if meta is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Bilinmeyen kurum: {code}")
    return meta


def _today() -> date_type:
    return datetime.now(_ISTANBUL).date()


def _bill_status(bill: SubscriptionBill) -> str:
    return "paid" if bill.paid_at is not None else "issued"


def _bill_out(bill: SubscriptionBill) -> SubscriptionBillOut:
    out = SubscriptionBillOut.model_validate(bill)
    out.status = _bill_status(bill)
    return out


def _sub_out(sub: Subscription, *, status_: str, amount: Decimal, bill_id: Optional[int]) -> SubscriptionOut:
    out = SubscriptionOut.model_validate(sub)
    out.provider_name = PROVIDERS.get(sub.provider_code, (sub.provider_code, sub.category))[0]
    out.current_status = status_  # type: ignore[assignment]
    out.current_amount = amount
    out.current_bill_id = bill_id
    return out


def _forecast_amount(sub: Subscription, bill: Optional[SubscriptionBill]) -> tuple[str, Decimal, Optional[int]]:
    """Bir abonelik + (o aya ait) fatura için (durum, tutar, bill_id).

    - fatura yok → budget, budget_amount
    - fatura var, ödenmemiş → issued, bill_amount
    - fatura var, ödenmiş → paid, bill_amount (forecast'ta sayılmaz; actual'da)
    """
    if bill is None:
        return "budget", Decimal(sub.budget_amount), None
    if bill.paid_at is None:
        return "issued", Decimal(bill.bill_amount), bill.id
    return "paid", Decimal(bill.bill_amount), bill.id


async def _get_sub(db: AsyncSession, user_id, sub_id: int) -> Subscription:
    q = await db.execute(select(Subscription).where(Subscription.id == sub_id, Subscription.user_id == user_id))
    sub = q.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_SUB_NOT_FOUND)
    return sub


async def _get_bill(db: AsyncSession, sub: Subscription, bill_id: int) -> SubscriptionBill:
    q = await db.execute(
        select(SubscriptionBill).where(
            SubscriptionBill.id == bill_id,
            SubscriptionBill.subscription_id == sub.id,
        )
    )
    bill = q.scalar_one_or_none()
    if bill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_BILL_NOT_FOUND)
    return bill


# --------------------------------------------------------------------------- #
# Katalog
# --------------------------------------------------------------------------- #
@router.get("/providers", response_model=list[ProviderOut])
async def list_providers() -> list[ProviderOut]:
    return provider_catalog()


# --------------------------------------------------------------------------- #
# Abonelik CRUD
# --------------------------------------------------------------------------- #
@router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SubscriptionOut]:
    today = _today()
    q = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id).options(selectinload(Subscription.bills)).order_by(Subscription.created_at)
    )
    subs = q.scalars().all()
    result: list[SubscriptionOut] = []
    for sub in subs:
        bill = next(
            (b for b in sub.bills if b.period_year == today.year and b.period_month == today.month),
            None,
        )
        status_, amount, bill_id = _forecast_amount(sub, bill)
        result.append(_sub_out(sub, status_=status_, amount=amount, bill_id=bill_id))
    return result


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: SubscriptionCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionOut:
    _name, category = _provider_or_422(payload.provider_code)
    sub = Subscription(
        user_id=current_user.id,
        provider_code=payload.provider_code,
        category=category,
        subscriber_no=payload.subscriber_no.strip(),
        label=payload.label.strip() if payload.label else None,
        budget_amount=payload.budget_amount,
        currency=payload.currency or current_user.default_currency or "TRY",
        billing_day=payload.billing_day,
        due_day=payload.due_day,
        active=payload.active,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(sub)
    await log_audit(
        db,
        request,
        action=AuditAction.SUBSCRIPTION_ADD,
        user_id=current_user.id,
        resource=payload.provider_code,
    )
    await db.commit()
    await db.refresh(sub)
    return _sub_out(sub, status_="budget", amount=Decimal(sub.budget_amount), bill_id=None)


@router.put("/{sub_id}", response_model=SubscriptionOut)
async def update_subscription(
    sub_id: int,
    payload: SubscriptionUpdate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionOut:
    sub = await _get_sub(db, current_user.id, sub_id)
    data = payload.model_dump(exclude_unset=True)
    if "provider_code" in data and data["provider_code"]:
        _name, category = _provider_or_422(data["provider_code"])
        sub.category = category
    for field in ("provider_code", "subscriber_no", "label", "budget_amount", "currency", "billing_day", "due_day", "active", "notes"):
        if field in data:
            value = data[field]
            if isinstance(value, str):
                value = value.strip() or None if field in ("label", "notes") else value.strip()
            setattr(sub, field, value)
    sub.updated_at = datetime.now(_ISTANBUL)
    await log_audit(db, request, action=AuditAction.SUBSCRIPTION_UPDATE, user_id=current_user.id, resource=str(sub_id))
    await db.commit()
    await db.refresh(sub)
    today = _today()
    bill_q = await db.execute(
        select(SubscriptionBill).where(
            SubscriptionBill.subscription_id == sub.id,
            SubscriptionBill.period_year == today.year,
            SubscriptionBill.period_month == today.month,
        )
    )
    status_, amount, bill_id = _forecast_amount(sub, bill_q.scalar_one_or_none())
    return _sub_out(sub, status_=status_, amount=amount, bill_id=bill_id)


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    sub_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    sub = await _get_sub(db, current_user.id, sub_id)
    await db.delete(sub)
    await log_audit(db, request, action=AuditAction.SUBSCRIPTION_DELETE, user_id=current_user.id, resource=str(sub_id))
    await db.commit()


# --------------------------------------------------------------------------- #
# Özet (dashboard Giderler kartı + yıl sonu beklenti)
# --------------------------------------------------------------------------- #
@router.get("/summary", response_model=SubscriptionSummaryOut)
async def subscription_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    display: Annotated[Optional[str], Query()] = None,
) -> SubscriptionSummaryOut:
    display_ccy = display_svc.normalize_display(display, current_user.default_currency)
    today = _today()
    q = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id, Subscription.active.is_(True)).options(selectinload(Subscription.bills))
    )
    subs = q.scalars().all()
    rates = await currency_svc.fetch_rates() if subs else {}

    this_month = Decimal(0)
    remaining = Decimal(0)
    for sub in subs:
        bills_by_month = {(b.period_year, b.period_month): b for b in sub.bills}
        for month in range(today.month, 13):
            bill = bills_by_month.get((today.year, month))
            status_, amount, _bid = _forecast_amount(sub, bill)
            if status_ == "paid":
                continue  # gerçekleşmiş → actual'da sayılır
            value = display_svc.convert_forecast(amount, sub.currency, display_ccy, rates)
            remaining += value
            if month == today.month:
                this_month += value

    return SubscriptionSummaryOut(
        display_currency=display_ccy,
        this_month_estimate=display_svc.quantize_tl(this_month),
        remaining_year_estimate=display_svc.quantize_tl(remaining),
        active_count=len(subs),
    )


# --------------------------------------------------------------------------- #
# Fatura dönemleri (lifecycle)
# --------------------------------------------------------------------------- #
@router.get("/{sub_id}/bills", response_model=list[SubscriptionPeriodOut])
async def list_bills(
    sub_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SubscriptionPeriodOut]:
    sub = await _get_sub(db, current_user.id, sub_id)
    q = await db.execute(
        select(SubscriptionBill)
        .where(SubscriptionBill.subscription_id == sub.id)
        .order_by(SubscriptionBill.period_year.desc(), SubscriptionBill.period_month.desc())
    )
    bills = q.scalars().all()
    periods: list[SubscriptionPeriodOut] = []
    today = _today()
    has_current = any(b.period_year == today.year and b.period_month == today.month for b in bills)
    if not has_current:
        # Bu ay henüz fatura girilmemiş → sentezlenmiş "budget" dönemi (en üstte)
        periods.append(
            SubscriptionPeriodOut(
                period_year=today.year,
                period_month=today.month,
                status="budget",
                amount=Decimal(sub.budget_amount),
                currency=sub.currency,
            )
        )
    for b in bills:
        periods.append(
            SubscriptionPeriodOut(
                period_year=b.period_year,
                period_month=b.period_month,
                status=_bill_status(b),  # type: ignore[arg-type]
                amount=Decimal(b.bill_amount),
                currency=b.currency,
                bill_id=b.id,
                bill_date=b.bill_date,
                due_date=b.due_date,
                paid_at=b.paid_at,
                payment_method=b.payment_method,
            )
        )
    return periods


@router.post("/{sub_id}/bills/issue", response_model=SubscriptionBillOut)
async def issue_bill(
    sub_id: int,
    payload: SubscriptionBillIssue,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionBillOut:
    """budget → issued: fatura geldi (tutar + tarihler). Aynı dönem varsa günceller."""
    sub = await _get_sub(db, current_user.id, sub_id)
    existing_q = await db.execute(
        select(SubscriptionBill).where(
            SubscriptionBill.subscription_id == sub.id,
            SubscriptionBill.period_year == payload.period_year,
            SubscriptionBill.period_month == payload.period_month,
        )
    )
    bill = existing_q.scalar_one_or_none()
    if bill is None:
        bill = SubscriptionBill(
            subscription_id=sub.id,
            period_year=payload.period_year,
            period_month=payload.period_month,
            currency=sub.currency,
        )
        db.add(bill)
    bill.bill_amount = payload.bill_amount
    bill.bill_date = payload.bill_date
    bill.due_date = payload.due_date
    bill.notes = payload.notes.strip() if payload.notes else None
    await log_audit(
        db,
        request,
        action=AuditAction.SUBSCRIPTION_BILL_ISSUE,
        user_id=current_user.id,
        resource=str(sub_id),
        extra={"period": f"{payload.period_year}-{payload.period_month:02d}"},
    )
    await db.commit()
    await db.refresh(bill)
    return _bill_out(bill)


async def _create_expense_for_bill(
    db: AsyncSession,
    sub: Subscription,
    bill: SubscriptionBill,
    payload: SubscriptionBillPay,
    user_id,
) -> int:
    """Ödenen fatura için gerçek Expense kaydı üret (amount_tl ödeme-anı kuruyla sabit)."""
    ccy = bill.currency or "TRY"
    if ccy.upper() == "TRY":
        amount_tl, exchange_rate = Decimal(bill.bill_amount), Decimal("1")
    else:
        rates = await currency_svc.fetch_rates()
        amount_tl = currency_svc.convert_to_tl(Decimal(bill.bill_amount), ccy, rates)
        exchange_rate = rates.get(ccy.upper())
    paid_date = (payload.paid_at or datetime.now(_ISTANBUL)).date()
    provider_name = PROVIDERS.get(sub.provider_code, (sub.provider_code, sub.category))[0]
    cc_id = payload.credit_card_id if payload.payment_method == "credit_card" else None
    exp = Expense(
        user_id=user_id,
        amount=bill.bill_amount,
        currency=ccy,
        amount_tl=amount_tl,
        exchange_rate=exchange_rate,
        category="bills",
        date=paid_date,
        description=f"{provider_name} faturası {bill.period_year}-{bill.period_month:02d}",
        credit_card_id=cc_id,
        is_paid=True,
    )
    db.add(exp)
    await db.flush()
    return exp.id


@router.post("/{sub_id}/bills/{bill_id}/pay", response_model=SubscriptionBillOut)
async def pay_bill(
    sub_id: int,
    bill_id: int,
    payload: SubscriptionBillPay,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionBillOut:
    """issued → paid: gerçek gider üret. Ödeme şekli credit_card_id'yi belirler."""
    sub = await _get_sub(db, current_user.id, sub_id)
    bill = await _get_bill(db, sub, bill_id)
    if bill.paid_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Fatura zaten ödenmiş")
    # Kredi kartı sahipliği doğrula (IDOR)
    if payload.payment_method == "credit_card":
        if payload.credit_card_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Kredi kartı seçilmeli")
        card_q = await db.execute(
            select(CreditCard.id).where(
                CreditCard.id == payload.credit_card_id,
                CreditCard.user_id == current_user.id,
            )
        )
        if card_q.scalar_one_or_none() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Kart bulunamadı")

    expense_id = await _create_expense_for_bill(db, sub, bill, payload, current_user.id)
    bill.paid_at = payload.paid_at or datetime.now(_ISTANBUL)
    bill.payment_method = payload.payment_method
    bill.credit_card_id = payload.credit_card_id if payload.payment_method == "credit_card" else None
    bill.expense_id = expense_id
    await log_audit(
        db,
        request,
        action=AuditAction.SUBSCRIPTION_BILL_PAY,
        user_id=current_user.id,
        resource=str(sub_id),
        extra={"method": payload.payment_method, "bill_id": bill_id},
    )
    await db.commit()
    await db.refresh(bill)
    return _bill_out(bill)


@router.post("/{sub_id}/bills/{bill_id}/unpay", response_model=SubscriptionBillOut)
async def unpay_bill(
    sub_id: int,
    bill_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionBillOut:
    """paid → issued: ödemeyi geri al, bağlı Expense'i sil (idempotent)."""
    sub = await _get_sub(db, current_user.id, sub_id)
    bill = await _get_bill(db, sub, bill_id)
    if bill.expense_id is not None:
        exp_q = await db.execute(select(Expense).where(Expense.id == bill.expense_id))
        exp = exp_q.scalar_one_or_none()
        if exp is not None:
            await db.delete(exp)
    bill.paid_at = None
    bill.payment_method = None
    bill.credit_card_id = None
    bill.expense_id = None
    await log_audit(
        db,
        request,
        action=AuditAction.SUBSCRIPTION_BILL_UNPAY,
        user_id=current_user.id,
        resource=str(sub_id),
        extra={"bill_id": bill_id},
    )
    await db.commit()
    await db.refresh(bill)
    return _bill_out(bill)


@router.delete("/{sub_id}/bills/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bill(
    sub_id: int,
    bill_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """issued → budget: fatura kaydını sil (dönem implicit budget'a döner).

    Ödenmiş faturada önce unpay gerekir (bağlı gider kaybolmasın).
    """
    sub = await _get_sub(db, current_user.id, sub_id)
    bill = await _get_bill(db, sub, bill_id)
    if bill.paid_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Ödenmiş fatura silinemez — önce ödemeyi geri alın",
        )
    await db.delete(bill)
    await db.commit()


# --------------------------------------------------------------------------- #
# Hatırlatmalar (girişte popup + cron push/e-posta)
# --------------------------------------------------------------------------- #
@router.get("/reminders", response_model=SubscriptionRemindersOut)
async def subscription_reminders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRemindersOut:
    today = _today()
    q = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id, Subscription.active.is_(True)).options(selectinload(Subscription.bills))
    )
    subs = q.scalars().all()
    due_payments: list[SubscriptionDuePayment] = []
    pending_bills: list[SubscriptionPendingBill] = []
    for sub in subs:
        provider_name = PROVIDERS.get(sub.provider_code, (sub.provider_code, sub.category))[0]
        _collect_due_payments(sub, provider_name, today, due_payments)
        _collect_pending_bill(sub, provider_name, today, pending_bills)
    due_payments.sort(key=lambda d: d.due_date)
    return SubscriptionRemindersOut(due_payments=due_payments, pending_bills=pending_bills)


def _collect_due_payments(
    sub: Subscription,
    provider_name: str,
    today: date_type,
    out: list[SubscriptionDuePayment],
) -> None:
    """issued (ödenmemiş) + son ödeme ≤ today+5 olan faturalar."""
    for bill in sub.bills:
        if bill.paid_at is not None:
            continue
        days = (bill.due_date - today).days
        if days <= _DUE_SOON_DAYS:
            out.append(
                SubscriptionDuePayment(
                    subscription_id=sub.id,
                    bill_id=bill.id,
                    provider_name=provider_name,
                    label=sub.label,
                    bill_amount=Decimal(bill.bill_amount),
                    currency=bill.currency,
                    due_date=bill.due_date,
                    days_until_due=days,
                )
            )


def _collect_pending_bill(
    sub: Subscription,
    provider_name: str,
    today: date_type,
    out: list[SubscriptionPendingBill],
) -> None:
    """Tahmini kesim günü geçmiş ama bu ay fatura girilmemiş → 'fatura gir' hatırlatması."""
    if sub.billing_day is None or today.day < sub.billing_day:
        return
    has_current = any(b.period_year == today.year and b.period_month == today.month for b in sub.bills)
    if not has_current:
        out.append(
            SubscriptionPendingBill(
                subscription_id=sub.id,
                provider_name=provider_name,
                label=sub.label,
                period_year=today.year,
                period_month=today.month,
            )
        )
