"""Kredi kartı CRUD endpoint'leri: tanım + dönem içi borç + ekstre + taksit."""

from datetime import date as date_type
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.credit_card import CreditCard, CreditCardInstallment, CreditCardStatement
from app.models.user import User
from app.schemas.credit_card import (
    CardDetailOut,
    CreditCardCreate,
    CreditCardOut,
    CreditCardSummaryOut,
    CreditCardUpdate,
    InstallmentCreate,
    InstallmentOut,
    InstallmentUpdate,
    StatementCreate,
    StatementOut,
    StatementUpdate,
)

router = APIRouter(prefix="/credit-cards", tags=["credit-cards"])


def _enrich_card(card: CreditCard) -> CreditCardOut:
    """Bir kart için 5 hesaplanmış alanı doldur ve CreditCardOut döner."""
    unpaid = [s for s in (card.statements or []) if s.paid_at is None]
    unpaid_total = sum((Decimal(s.statement_amount) for s in unpaid), Decimal(0))
    unpaid_count = len(unpaid)

    future_total = Decimal(0)
    for inst in card.installments or []:
        if inst.installments_remaining > 0:
            future_total += Decimal(inst.monthly_amount) * Decimal(inst.installments_remaining)

    current_period = Decimal(card.current_period_debt)
    period_debt = unpaid_total + current_period
    total_debt = period_debt + future_total

    return CreditCardOut(
        id=card.id,
        name=card.name,
        bank_name=card.bank_name,
        last_4=card.last_4,
        credit_limit=card.credit_limit,
        statement_day=card.statement_day,
        payment_due_day=card.payment_due_day,
        current_period_debt=current_period,
        notes=card.notes,
        created_at=card.created_at,
        updated_at=card.updated_at,
        unpaid_statement_total=unpaid_total,
        unpaid_statement_count=unpaid_count,
        future_installment_total=future_total,
        period_debt=period_debt,
        total_debt=total_debt,
    )


@router.get("", response_model=CreditCardSummaryOut)
async def list_credit_cards(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tüm kartları + toplam dönem içi borç + toplam borç özeti."""
    result = await db.execute(
        select(CreditCard)
        .where(CreditCard.user_id == current_user.id)
        .options(
            selectinload(CreditCard.statements),
            selectinload(CreditCard.installments),
        )
        .order_by(CreditCard.name)
    )
    cards = result.scalars().all()
    enriched = [_enrich_card(c) for c in cards]
    total_period = sum((c.period_debt for c in enriched), Decimal(0))
    total = sum((c.total_debt for c in enriched), Decimal(0))
    total_current = sum((c.current_period_debt for c in enriched), Decimal(0))
    return CreditCardSummaryOut(
        cards=enriched,
        total_period_debt=total_period,
        total_debt=total,
        total_current_period_debt=total_current,  # legacy field
    )


@router.post("", response_model=CreditCardOut, status_code=status.HTTP_201_CREATED)
async def create_credit_card(
    payload: CreditCardCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    card = CreditCard(
        user_id=current_user.id,
        name=payload.name,
        bank_name=payload.bank_name,
        last_4=payload.last_4,
        credit_limit=payload.credit_limit,
        statement_day=payload.statement_day,
        payment_due_day=payload.payment_due_day,
        current_period_debt=payload.current_period_debt,
        notes=payload.notes,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.put("/{card_id}", response_model=CreditCardOut)
async def update_credit_card(
    card_id: int,
    payload: CreditCardUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(CreditCard).where(
            CreditCard.id == card_id,
            CreditCard.user_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kart bulunamadı")

    for attr in (
        "name",
        "bank_name",
        "last_4",
        "credit_limit",
        "statement_day",
        "payment_due_day",
        "current_period_debt",
        "notes",
    ):
        v = getattr(payload, attr)
        if v is not None:
            setattr(card, attr, v)

    await db.commit()
    await db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credit_card(
    card_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(CreditCard).where(
            CreditCard.id == card_id,
            CreditCard.user_id == current_user.id,
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kart bulunamadı")
    await db.delete(card)
    await db.commit()


# ---------------------------------------------------------------------------
# Yardımcı: kullanıcının sahibi olduğu kartı getir (IDOR koruması)
# ---------------------------------------------------------------------------
async def _get_owned_card(card_id: int, user: User, db: AsyncSession) -> CreditCard:
    result = await db.execute(select(CreditCard).where(CreditCard.id == card_id, CreditCard.user_id == user.id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kart bulunamadı")
    return card


# ---------------------------------------------------------------------------
# Detay endpoint (kart + ekstreler + taksitler)
# ---------------------------------------------------------------------------
@router.get("/{card_id}", response_model=CardDetailOut)
async def get_credit_card_detail(
    card_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Kart bilgisi + tüm ekstre ve taksitleri tek seferde döner."""
    result = await db.execute(
        select(CreditCard)
        .where(CreditCard.id == card_id, CreditCard.user_id == current_user.id)
        .options(
            selectinload(CreditCard.statements),
            selectinload(CreditCard.installments),
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kart bulunamadı")

    # Statements en yeni dönemler önce, installments first_due_date'e göre
    sorted_statements = sorted(
        card.statements,
        key=lambda s: (s.period_year, s.period_month),
        reverse=True,
    )
    sorted_installments = sorted(card.installments, key=lambda i: i.first_due_date)

    return CardDetailOut(
        card=_enrich_card(card),
        statements=sorted_statements,
        installments=sorted_installments,
    )


# ---------------------------------------------------------------------------
# Ekstre endpoint'leri
# ---------------------------------------------------------------------------
@router.post("/{card_id}/statements", response_model=StatementOut, status_code=status.HTTP_201_CREATED)
async def create_statement(
    card_id: int,
    payload: StatementCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_owned_card(card_id, current_user, db)
    # Aynı dönem var mı? unique constraint zaten tutar ama net mesaj için
    existing_q = await db.execute(
        select(CreditCardStatement).where(
            CreditCardStatement.card_id == card_id,
            CreditCardStatement.period_year == payload.period_year,
            CreditCardStatement.period_month == payload.period_month,
        )
    )
    if existing_q.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{payload.period_year}-{payload.period_month:02d} için zaten ekstre kaydı var (güncellemek için PUT kullanın)",
        )
    stmt = CreditCardStatement(
        card_id=card_id,
        period_year=payload.period_year,
        period_month=payload.period_month,
        statement_amount=payload.statement_amount,
        statement_date=payload.statement_date,
        due_date=payload.due_date,
        paid_at=payload.paid_at,
        notes=payload.notes,
    )
    db.add(stmt)
    await db.commit()
    await db.refresh(stmt)
    return stmt


@router.put("/{card_id}/statements/{statement_id}", response_model=StatementOut)
async def update_statement(
    card_id: int,
    statement_id: int,
    payload: StatementUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_owned_card(card_id, current_user, db)
    result = await db.execute(
        select(CreditCardStatement).where(
            CreditCardStatement.id == statement_id,
            CreditCardStatement.card_id == card_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ekstre bulunamadı")
    for attr in ("statement_amount", "statement_date", "due_date", "paid_at", "notes"):
        v = getattr(payload, attr)
        if v is not None:
            setattr(stmt, attr, v)
    await db.commit()
    await db.refresh(stmt)
    return stmt


@router.delete("/{card_id}/statements/{statement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_statement(
    card_id: int,
    statement_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_owned_card(card_id, current_user, db)
    result = await db.execute(
        select(CreditCardStatement).where(
            CreditCardStatement.id == statement_id,
            CreditCardStatement.card_id == card_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ekstre bulunamadı")
    await db.delete(stmt)
    await db.commit()


# ---------------------------------------------------------------------------
# Taksit endpoint'leri
# ---------------------------------------------------------------------------
def _calc_total(monthly: Decimal, count: int) -> Decimal:
    """monthly × count → 2 ondalık."""
    return (monthly * Decimal(count)).quantize(Decimal("0.01"))


def _calc_remaining(first_due: date_type, total_count: int) -> int:
    """first_due'dan bugüne kaç taksit geçti, kalan = total - geçen.
    Bugün < first_due ise hepsi kalan; geçmiş > total ise 0."""
    from datetime import datetime as _dt

    from app.api.v1.income import _ISTANBUL  # Istanbul tz reuse

    today = _dt.now(_ISTANBUL).date()
    if today < first_due:
        return total_count
    months_passed = (today.year - first_due.year) * 12 + (today.month - first_due.month) + 1
    return max(0, total_count - months_passed)


@router.post("/{card_id}/installments", response_model=InstallmentOut, status_code=status.HTTP_201_CREATED)
async def create_installment(
    card_id: int,
    payload: InstallmentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_owned_card(card_id, current_user, db)
    total = _calc_total(payload.monthly_amount, payload.installments_total)
    remaining = _calc_remaining(payload.first_due_date, payload.installments_total)
    inst = CreditCardInstallment(
        card_id=card_id,
        description=payload.description,
        total_amount=total,
        monthly_amount=payload.monthly_amount,
        installments_total=payload.installments_total,
        installments_remaining=remaining,
        first_due_date=payload.first_due_date,
        notes=payload.notes,
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    return inst


@router.put("/{card_id}/installments/{installment_id}", response_model=InstallmentOut)
async def update_installment(
    card_id: int,
    installment_id: int,
    payload: InstallmentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_owned_card(card_id, current_user, db)
    result = await db.execute(
        select(CreditCardInstallment).where(
            CreditCardInstallment.id == installment_id,
            CreditCardInstallment.card_id == card_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taksit bulunamadı")
    for attr in ("description", "monthly_amount", "installments_total", "first_due_date", "notes"):
        v = getattr(payload, attr)
        if v is not None:
            setattr(inst, attr, v)
    # Otomatik hesaplama: total = monthly × count, remaining = first_due'den geçen ay
    inst.total_amount = _calc_total(Decimal(inst.monthly_amount), inst.installments_total)
    inst.installments_remaining = _calc_remaining(inst.first_due_date, inst.installments_total)
    await db.commit()
    await db.refresh(inst)
    return inst


@router.delete("/{card_id}/installments/{installment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_installment(
    card_id: int,
    installment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_owned_card(card_id, current_user, db)
    result = await db.execute(
        select(CreditCardInstallment).where(
            CreditCardInstallment.id == installment_id,
            CreditCardInstallment.card_id == card_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taksit bulunamadı")
    await db.delete(inst)
    await db.commit()
