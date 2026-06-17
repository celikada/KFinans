"""Kredi kartı CRUD endpoint'leri: tanım + dönem içi borç + ekstre + taksit."""

import calendar
import logging
import re
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.core.upload_validation import validate_pdf_upload
from app.models.credit_card import CreditCard, CreditCardInstallment, CreditCardStatement
from app.models.user import User
from app.schemas.credit_card import (
    CardDetailOut,
    CreditCardCreate,
    CreditCardOut,
    CreditCardRemindersResponse,
    CreditCardSummaryOut,
    CreditCardUpdate,
    DuePaymentItem,
    InstallmentCreate,
    InstallmentOut,
    InstallmentUpdate,
    PendingStatementCard,
    StatementCreate,
    StatementOut,
    StatementPayIn,
    StatementUpdate,
)
from app.schemas.statement_import import (
    ParsedInstallmentOut,
    ParsedStatementOut,
    StatementImportCommitIn,
)
from app.services import currency as currency_svc
from app.services import display_currency as display_svc
from app.services.audit import AuditAction, log_audit
from app.services.statement_import import detect_parser, extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credit-cards", tags=["credit-cards"])

_CARD_NOT_FOUND = "Kart bulunamadı"
_STATEMENT_NOT_FOUND = "Ekstre bulunamadı"
_ISTANBUL = ZoneInfo("Europe/Istanbul")
# Son ödeme tarihi bu kadar gün içindeyse "yaklaşıyor" sayılır (girişte hatırlat).
_DUE_SOON_DAYS = 5


def _last_passed_cutoff(today: date_type, statement_day: int) -> tuple[int, int, date_type]:
    """En son hesap kesim tarihi <= today olan dönemi (year, month, cutoff_date) döner.

    statement_day ayın son gününden büyükse o ayın son gününe çekilir."""

    def _cutoff(y: int, mo: int) -> date_type:
        day = min(statement_day, calendar.monthrange(y, mo)[1])
        return date_type(y, mo, day)

    cur = _cutoff(today.year, today.month)
    if cur <= today:
        return today.year, today.month, cur
    # Bu ayın kesim günü henüz gelmedi → önceki ayın kesim dönemi
    if today.month == 1:
        py, pm = today.year - 1, 12
    else:
        py, pm = today.year, today.month - 1
    return py, pm, _cutoff(py, pm)


def _enrich_card(
    card: CreditCard,
    rates: dict[str, Decimal] | None = None,
    display_ccy: str = "TRY",
) -> CreditCardOut:
    """Bir kart için hesaplanmış alanları doldur ve CreditCardOut döner.

    `rates` verilirse (güncel kur haritası) borç TL + görüntüleme-birimi karşılıkları
    da hesaplanır (Faz B — borç cari/tahmin → güncel kur). Kart para birimi == display
    ise dönüşüm yapılmaz (tutar aynen)."""
    card_currency = (getattr(card, "currency", None) or "TRY").upper()
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

    rate_map = rates or {}
    period_debt_tl = currency_svc.convert_to_tl(period_debt, card_currency, rate_map)
    total_debt_tl = currency_svc.convert_to_tl(total_debt, card_currency, rate_map)
    period_debt_display = display_svc.convert_forecast(period_debt, card_currency, display_ccy, rate_map)
    total_debt_display = display_svc.convert_forecast(total_debt, card_currency, display_ccy, rate_map)

    return CreditCardOut(
        id=card.id,
        name=card.name,
        bank_name=card.bank_name,
        last_4=card.last_4,
        credit_limit=card.credit_limit,
        statement_day=card.statement_day,
        payment_due_day=card.payment_due_day,
        current_period_debt=current_period,
        currency=card_currency,
        notes=card.notes,
        created_at=card.created_at,
        updated_at=card.updated_at,
        unpaid_statement_total=unpaid_total,
        unpaid_statement_count=unpaid_count,
        future_installment_total=future_total,
        period_debt=period_debt,
        total_debt=total_debt,
        total_debt_tl=total_debt_tl,
        period_debt_tl=period_debt_tl,
        display_currency=display_ccy,
        period_debt_display=period_debt_display,
        total_debt_display=total_debt_display,
    )


@router.get("", response_model=CreditCardSummaryOut)
async def list_credit_cards(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    display: Annotated[str | None, Query()] = None,
):
    """Tüm kartları + toplam dönem içi borç + toplam borç özeti.

    `display` (Faz B): borç/ekstre cari/tahmin olduğu için **güncel** kurla seçili
    görüntüleme birimine çevrilir (statement_date tarihsel anchor Faz B+ kapsamı).
    display==TRY → *_display == *_tl (regresyon yok)."""
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
    display_ccy = display_svc.normalize_display(display, current_user.default_currency)
    # Kart borçları kendi para biriminde — güncel kurla TL + display'e çevrilir.
    rates = await currency_svc.fetch_rates() if cards else {}

    enriched = [_enrich_card(c, rates, display_ccy) for c in cards]
    total_period = sum((c.period_debt for c in enriched), Decimal(0))
    total = sum((c.total_debt for c in enriched), Decimal(0))
    total_current = sum((c.current_period_debt for c in enriched), Decimal(0))
    total_period_display = sum((c.period_debt_display for c in enriched), Decimal(0))
    total_display = sum((c.total_debt_display for c in enriched), Decimal(0))
    return CreditCardSummaryOut(
        cards=enriched,
        total_period_debt=total_period,
        total_debt=total,
        total_current_period_debt=total_current,  # legacy field
        display_currency=display_ccy,
        total_period_debt_display=display_svc.quantize_tl(total_period_display),
        total_debt_display=display_svc.quantize_tl(total_display),
    )


@router.get("/reminders", response_model=CreditCardRemindersResponse)
async def get_reminders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Girişte gösterilecek kredi kartı hatırlatmaları:

    1. **pending_statements:** hesap kesim tarihi geçmiş ama o dönemin ekstresi
       henüz yüklenmemiş kartlar (ekstre yükleme hatırlatması).
    2. **due_payments:** son ödeme tarihi <= bugün + 7 gün olan, henüz ödenmemiş
       (paid_at IS NULL) ekstreler (ödeme hatırlatması; gecikmiş + yaklaşan)."""
    today = datetime.now(_ISTANBUL).date()

    result = await db.execute(
        select(CreditCard).where(CreditCard.user_id == current_user.id).options(selectinload(CreditCard.statements)).order_by(CreditCard.name)
    )
    cards = result.scalars().all()

    pending: list[PendingStatementCard] = []
    due: list[DuePaymentItem] = []

    for card in cards:
        # 1) Ekstre yükleme hatırlatması
        py, pm, cutoff = _last_passed_cutoff(today, card.statement_day)
        has_stmt = any(s.period_year == py and s.period_month == pm for s in (card.statements or []))
        if not has_stmt:
            pending.append(
                PendingStatementCard(
                    card_id=card.id,
                    name=card.name,
                    bank_name=card.bank_name,
                    last_4=card.last_4,
                    period_year=py,
                    period_month=pm,
                    cutoff_date=cutoff,
                )
            )
        # 2) Ödeme hatırlatması — ödenmemiş + son ödeme tarihi yaklaşan/geçmiş
        for s in card.statements or []:
            if s.paid_at is not None or s.due_date is None:
                continue
            days = (s.due_date - today).days
            if days <= _DUE_SOON_DAYS:
                due.append(
                    DuePaymentItem(
                        card_id=card.id,
                        card_name=card.name,
                        bank_name=card.bank_name,
                        statement_id=s.id,
                        period_year=s.period_year,
                        period_month=s.period_month,
                        due_date=s.due_date,
                        statement_amount=Decimal(s.statement_amount),
                        days_until_due=days,
                    )
                )

    due.sort(key=lambda d: d.due_date)
    return CreditCardRemindersResponse(pending_statements=pending, due_payments=due)


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
        currency=payload.currency or current_user.default_currency or "TRY",
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_CARD_NOT_FOUND)

    for attr in (
        "name",
        "bank_name",
        "last_4",
        "credit_limit",
        "statement_day",
        "payment_due_day",
        "current_period_debt",
        "currency",
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_CARD_NOT_FOUND)
    await db.delete(card)
    await db.commit()


# ---------------------------------------------------------------------------
# Yardımcı: kullanıcının sahibi olduğu kartı getir (IDOR koruması)
# ---------------------------------------------------------------------------
async def _get_owned_card(card_id: int, user: User, db: AsyncSession) -> CreditCard:
    result = await db.execute(select(CreditCard).where(CreditCard.id == card_id, CreditCard.user_id == user.id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_CARD_NOT_FOUND)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_CARD_NOT_FOUND)

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
    card = await _get_owned_card(card_id, current_user, db)
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
        # currency verilmezse kartın para birimini devral (TRY-dışı kartta cash
        # flow'un TRY varsayıp ~kur kat yanlış saymasını önler).
        currency=payload.currency or card.currency or "TRY",
    )
    db.add(stmt)
    # Elle eklenen ekstre de dönemine kadarki taksit dilimlerini kapsar → uzlaştır.
    await _reconcile_card_installments(db, card_id, payload.due_date)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_STATEMENT_NOT_FOUND)
    for attr in ("statement_amount", "statement_date", "due_date", "paid_at", "paid_amount", "notes", "currency"):
        v = getattr(payload, attr)
        if v is not None:
            setattr(stmt, attr, v)
    await db.commit()
    await db.refresh(stmt)
    return stmt


@router.post("/{card_id}/statements/{statement_id}/pay", response_model=StatementOut)
async def pay_statement(
    card_id: int,
    statement_id: int,
    payload: StatementPayIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Ekstreyi ödendi işaretle (tam veya kısmi).

    Kısmi ödemede (paid_amount < statement_amount) kalan, kartın dönem-içi borcuna
    (`current_period_debt`) eklenir → sonraki ekstreye taşınır. Carry yalnız İLK
    ödemede uygulanır (paid_at null→set); tekrar çağrıda çift eklenmez.
    """
    card = await _get_owned_card(card_id, current_user, db)
    result = await db.execute(
        select(CreditCardStatement).where(
            CreditCardStatement.id == statement_id,
            CreditCardStatement.card_id == card_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_STATEMENT_NOT_FOUND)
    if payload.paid_amount > Decimal(stmt.statement_amount):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ödenen tutar ekstre tutarından büyük olamaz",
        )
    already_paid = stmt.paid_at is not None
    stmt.paid_at = payload.paid_at or datetime.now(_ISTANBUL)
    stmt.paid_amount = payload.paid_amount
    # Kısmi ödeme: kalanı dönem-içi borca taşı — yalnız ilk ödemede (çift-carry önle).
    if not already_paid:
        remainder = Decimal(stmt.statement_amount) - Decimal(payload.paid_amount)
        if remainder > 0:
            card.current_period_debt = Decimal(card.current_period_debt) + remainder
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_STATEMENT_NOT_FOUND)
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


def _add_months(d: date_type, n: int) -> date_type:
    """d'ye n ay ekler, gün=1 (ay başı). Negatif n geriye gider."""
    total = (d.year * 12 + (d.month - 1)) + n
    y, m = divmod(total, 12)
    return date_type(y, m + 1, 1)


# Taksit açıklamasındaki dilim göstergeleri — saklanan açıklamadan ve plan-eşleştirme
# anahtarından çıkarılır. Kayıt zaten KALAN dilimleri temsil ettiği için "(1/4)" / "01.Tak"
# / "2. Taksit" gibi işaretler yanıltıcıdır; geriye temiz satıcı adı kalır
# (ör. "01/06 IYZICO/HOYA TURKEY 01.Tak İSTANBUL (1/4)" → "01/06 IYZICO/HOYA TURKEY İSTANBUL").
# Bounded quantifiers (sınırsız `*`/`+` yok) ReDoS hotspot'unu kaynağında kaldırır.
_INSTALLMENT_SUFFIX_RE = re.compile(r"\s{0,4}\(\d{1,3}\s{0,4}/\s{0,4}\d{1,3}\)\s{0,4}$")
# "01.Tak", "2. Taksit", "4/4 Taksidi", "Sonradan Taksit" gibi gömülü dilim işaretleri.
_INSTALLMENT_MARKER_RE = re.compile(
    r"\s{0,4}(?:\d{1,3}\s{0,2}\.\s{0,2}Tak(?:sit|sidi|\.)?|Sonradan\s{1,2}Taksit)\b\.?",
    re.IGNORECASE,
)
_MULTISPACE_RE = re.compile(r"\s{2,}")


def _norm_installment_desc(desc: str) -> str:
    """Taksit açıklamasını temizler: "(k/n)" eki + dilim göstergeleri ("N.Tak",
    "N. Taksit", "Sonradan Taksit") çıkarılır, fazla boşluk sadeleşir.

    Hem SAKLANAN açıklama hem de aynı planın aylar-arası EŞLEŞTİRME anahtarı bu
    temiz biçimi kullanır (idempotent — zaten temiz metni tekrar temizlemek no-op;
    ham ve temiz kayıtlar re-import'ta doğru eşleşir). Tüm bankalarda + manuel
    girişte aynı şekilde çalışır."""
    s = _INSTALLMENT_SUFFIX_RE.sub("", desc)
    s = _INSTALLMENT_MARKER_RE.sub(" ", s)
    s = _MULTISPACE_RE.sub(" ", s)
    return s.strip(" .-").strip()


@router.post("/{card_id}/installments", response_model=InstallmentOut, status_code=status.HTTP_201_CREATED)
async def create_installment(
    card_id: int,
    payload: InstallmentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    card = await _get_owned_card(card_id, current_user, db)
    # Parser gerçek plan toplamını verdiyse onu kullan (monthly×n yerine — son
    # dilim küsuratında kayma olmaz); yoksa monthly×n.
    total = payload.total_amount or _calc_total(payload.monthly_amount, payload.installments_total)
    # Invariant: installments_remaining = GELECEK taksit sayısı, first_due_date =
    # ilk GELECEK taksit ayı. Geçmişte başlamış planda first_due'yu ileri çek
    # (cash_flow/_enrich_card kalanı first_due'dan itibaren projekte eder).
    remaining = _calc_remaining(payload.first_due_date, payload.installments_total)
    first_due = _add_months(payload.first_due_date, payload.installments_total - remaining)
    inst = CreditCardInstallment(
        card_id=card_id,
        description=payload.description,
        total_amount=total,
        monthly_amount=payload.monthly_amount,
        installments_total=payload.installments_total,
        installments_remaining=remaining,
        first_due_date=first_due,
        notes=payload.notes,
        currency=payload.currency or card.currency or "TRY",
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
    for attr in ("description", "monthly_amount", "installments_total", "first_due_date", "notes", "currency"):
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


async def _upsert_statement(db: AsyncSession, card_id: int, s: StatementCreate, currency: str = "TRY") -> None:
    """Ekstreyi (card_id, period) unique'ine göre güncelle ya da ekle."""
    ccy = s.currency or currency or "TRY"
    existing_q = await db.execute(
        select(CreditCardStatement).where(
            CreditCardStatement.card_id == card_id,
            CreditCardStatement.period_year == s.period_year,
            CreditCardStatement.period_month == s.period_month,
        )
    )
    stmt = existing_q.scalar_one_or_none()
    if stmt is not None:
        stmt.statement_amount = s.statement_amount
        stmt.statement_date = s.statement_date
        stmt.due_date = s.due_date
        stmt.currency = ccy
        if s.paid_at is not None:
            stmt.paid_at = s.paid_at
        if s.notes is not None:
            stmt.notes = s.notes
        return
    db.add(
        CreditCardStatement(
            card_id=card_id,
            period_year=s.period_year,
            period_month=s.period_month,
            statement_amount=s.statement_amount,
            statement_date=s.statement_date,
            due_date=s.due_date,
            paid_at=s.paid_at,
            notes=s.notes,
            currency=ccy,
        )
    )


async def _reconcile_card_installments(db: AsyncSession, card_id: int, due_date: date_type) -> int:
    """Bir ekstre kaydedilince kartın TÜM taksitlerini ekstre dönemine göre uzlaştırır.

    Ekstre TOPLAMI, dilimi due_date ayına **veya öncesine** düşen taksitleri zaten
    içerir → bu dilimler "kapsanmış" sayılıp projeksiyondan düşülür. Böylece parser'ın
    (değişken format nedeniyle) ekstreden çıkaramadığı taksitler bile stale kalmaz:
    first_due ≤ ekstre ayı olan her taksit ilerletilir (`first_due = ekstre ayı + 1`),
    kapsanan dilim kadar `installments_remaining` azaltılır, ≤0 olan silinir.
    `_upsert_installments`'tan ÖNCE çağrılır (parser-listeli olanları o kesin set eder).
    Dokunulan kayıt sayısını döner.
    """
    m_year, m_month = due_date.year, due_date.month
    next_first_due = _add_months(date_type(m_year, m_month, 1), 1)
    existing = (await db.execute(select(CreditCardInstallment).where(CreditCardInstallment.card_id == card_id))).scalars().all()
    touched = 0
    for inst in existing:
        fd = inst.first_due_date
        if (fd.year, fd.month) > (m_year, m_month):
            continue  # tüm dilimler gelecekte → ekstre kapsamaz
        covered = min((m_year - fd.year) * 12 + (m_month - fd.month) + 1, inst.installments_remaining)
        new_remaining = inst.installments_remaining - covered
        if new_remaining <= 0:
            await db.delete(inst)
        else:
            inst.installments_remaining = new_remaining
            inst.first_due_date = next_first_due
        touched += 1
    return touched


async def _upsert_installments(
    db: AsyncSession,
    card_id: int,
    due_date: date_type,
    installments: list[InstallmentCreate],
    default_currency: str = "TRY",
) -> int:
    """Ekstre import'undan taksitleri **çift sayımsız** kalıcılaştırır.

    Çekirdek kural: bir ekstrenin TOPLAMI o ayın taksit dilimini (k/n'deki k)
    zaten içerir → taksit kaydı yalnızca **GELECEK** dilimleri temsil etmeli.
    Bu yüzden her `(k/n)` için:
      - `installments_remaining = n - k` (sadece sonraki taksitler),
      - `first_due_date = due_date ayı + 1` (ekstre nakit-akışına due_date ayına
        yazılır; gelecek taksitler bir sonraki aydan başlar → çift sayım yok),
      - aynı plan (kart + normalize açıklama + n + total + currency) varsa
        **MUTLAK set** (idempotent — aynı ekstre 2 kez import edilse de bozulmaz),
        yoksa oluştur; `n - k <= 0` (son dilim) → varsa sil, yoksa atla.
    Eklenen/güncellenen kayıt sayısını döner.
    """
    first_due = _add_months(date_type(due_date.year, due_date.month, 1), 1)

    existing = (await db.execute(select(CreditCardInstallment).where(CreditCardInstallment.card_id == card_id))).scalars().all()

    touched = 0
    for inst_in in installments:
        n = inst_in.installments_total
        # k: ekstrede görünen taksit sırası; yoksa (eski/elle veri) 1 varsay.
        k = inst_in.installments_paid or 1
        remaining = n - k
        total = _calc_total(inst_in.monthly_amount, n)
        currency = inst_in.currency or default_currency or "TRY"
        norm = _norm_installment_desc(inst_in.description)

        # Aynı planı bul (ay-bağımsız anahtar: monthly DEĞİL — küsurat dengesi kayar).
        match = next(
            (
                e
                for e in existing
                if _norm_installment_desc(e.description) == norm
                and e.installments_total == n
                and Decimal(e.total_amount) == total
                and (e.currency or "TRY") == currency
            ),
            None,
        )

        if remaining <= 0:
            # Son dilim — gelecek yok. Önceki projeksiyon varsa kaldır.
            if match is not None:
                await db.delete(match)
                touched += 1
            continue

        if match is not None:
            match.description = norm
            match.total_amount = total
            match.monthly_amount = inst_in.monthly_amount
            match.installments_remaining = remaining
            match.first_due_date = first_due
            match.currency = currency
        else:
            db.add(
                CreditCardInstallment(
                    card_id=card_id,
                    description=norm,
                    currency=currency,
                    total_amount=total,
                    monthly_amount=inst_in.monthly_amount,
                    installments_total=n,
                    installments_remaining=remaining,
                    first_due_date=first_due,
                    notes=inst_in.notes,
                )
            )
        touched += 1
    return touched


# ---------------------------------------------------------------------------
# Ekstre (PDF) import — Faz 3
#
# İki adımlı, fail-safe akış:
#  - preview: PDF yüklenir → banka tanınır → veri ayıklanır → DB'ye YAZILMADAN
#    önizleme döner. Banka tanınmazsa veya format değişmişse 422 (kayıt yok).
#  - commit: kullanıcının onayladığı/düzelttiği veri kalıcılaştırılır.
# ---------------------------------------------------------------------------
@router.post("/import-statement/preview", response_model=ParsedStatementOut)
@limiter.limit("10/hour")
async def preview_statement_import(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
):
    """PDF ekstreyi parse edip önizleme döner (DB'ye yazmaz).

    Banka tanınmazsa veya bilinen bankanın formatı değişmişse 422 verir ve
    hiçbir tahmini veri üretmez (fail-safe — kullanıcı uyarılır)."""
    content = await validate_pdf_upload(file)

    try:
        text = extract_text(content)
    except Exception:
        logger.exception("Ekstre PDF metin çıkarma hatası")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF okunamadı. Şifreli/bozuk bir dosya olabilir.",
        )

    parser = detect_parser(text)
    if parser is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Ekstre formatı tanınmadı. Bu banka henüz desteklenmiyor olabilir; "
                "kart bilgilerini elle girebilir veya örnek ekstreyi geliştiriciye iletebilirsiniz."
            ),
        )

    try:
        parsed = parser.parse(text)
    except (ValueError, InvalidOperation) as exc:
        # Banka tanındı ama beklenen alanlar yok / tutar ayrıştırılamadı → format
        # değişmiş olabilir. InvalidOperation (ArithmeticError) ValueError'a düşmez,
        # ayrıca yakalanmalı (yoksa generic 500). Ham PDF parçası içeren `exc`
        # kullanıcıya YANSITILMAZ (PII/iç detay sızıntısı) — yalnız log'a.
        logger.warning("Ekstre parse başarısız (bank=%s): %s", parser.bank_key, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ekstre okunamadı; banka formatı değişmiş olabilir.",
        )

    matched_card_id: int | None = None
    if parsed.last_4:
        match_q = await db.execute(
            select(CreditCard.id).where(
                CreditCard.user_id == current_user.id,
                CreditCard.last_4 == parsed.last_4,
            )
        )
        matched_card_id = match_q.scalars().first()

    return ParsedStatementOut(
        bank_name=parsed.bank_name,
        last_4=parsed.last_4,
        credit_limit=parsed.credit_limit,
        statement_day=parsed.statement_day,
        payment_due_day=parsed.payment_due_day,
        period_year=parsed.period_year,
        period_month=parsed.period_month,
        statement_amount=parsed.statement_amount,
        statement_date=parsed.statement_date,
        due_date=parsed.due_date,
        installments=[
            ParsedInstallmentOut(
                # Temiz satıcı adı (dilim göstergeleri çıkarılmış) — önizleme,
                # kaydedilecek değerle birebir aynı olsun. "k/n" bilgisi ayrı
                # installments_total/paid alanlarında korunur.
                description=_norm_installment_desc(i.description),
                total_amount=i.total_amount,
                monthly_amount=i.monthly_amount,
                installments_total=i.installments_total,
                installments_paid=i.installments_paid,
                first_due_date=i.first_due_date,
            )
            for i in parsed.installments
        ],
        matched_card_id=matched_card_id,
        warnings=parsed.warnings,
    )


@router.post(
    "/import-statement/commit",
    response_model=CardDetailOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/hour")
async def commit_statement_import(
    request: Request,
    payload: StatementImportCommitIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Önizlemeden onaylanan ekstre verisini kalıcılaştırır (tek transaction).

    Kart yoksa oluşturur (çoklu kart tek hesapta toplanır); ekstre dönemi varsa
    günceller (upsert); taksitleri ekler (aynı taksit zaten varsa atlar)."""
    # 1) Hedef kart: mevcut (IDOR korumalı) ya da yeni oluştur.
    if payload.target_card_id is not None:
        card = await _get_owned_card(payload.target_card_id, current_user, db)
        if payload.bank_name is not None:
            card.bank_name = payload.bank_name
        if payload.credit_limit is not None:
            card.credit_limit = payload.credit_limit
        if payload.last_4:
            card.last_4 = payload.last_4
        card.statement_day = payload.statement_day
        card.payment_due_day = payload.payment_due_day
        if payload.currency:
            card.currency = payload.currency
    else:
        card = CreditCard(
            user_id=current_user.id,
            name=payload.name,
            bank_name=payload.bank_name,
            last_4=payload.last_4,
            credit_limit=payload.credit_limit,
            statement_day=payload.statement_day,
            payment_due_day=payload.payment_due_day,
            currency=payload.currency or "TRY",
        )
        db.add(card)
        await db.flush()  # card.id gerekli

    # 2) Ekstre upsert + 3) taksitler (çift sayımsız upsert: gelecek dilimler +
    #    plan eşleştir-ilerlet; due_date ayı + 1'den başlar) — helper'lara delege.
    #    Kart para birimi ekstre + taksitlere devredilir (cash flow doğru çevirir).
    card_currency = card.currency or "TRY"
    s = payload.statement
    await _upsert_statement(db, card.id, s, card_currency)
    # Önce TÜM taksitleri ekstre dönemine göre uzlaştır (parser çıkaramayan stale
    # dilimleri de temizler) — sonra parser-listelenenleri kesin set et.
    await _reconcile_card_installments(db, card.id, s.due_date)
    added_installments = await _upsert_installments(db, card.id, s.due_date, payload.installments, card_currency)

    # 4) Audit (best-effort, flush) + tek commit.
    await log_audit(
        db,
        request,
        action=AuditAction.CREDIT_STATEMENT_IMPORT,
        user_id=current_user.id,
        resource=f"card:{card.id}",
        extra={
            "period": f"{s.period_year}-{s.period_month:02d}",
            "installments_added": added_installments,
            "new_card": payload.target_card_id is None,
        },
    )
    await db.commit()

    # 5) Güncel detayı döndür (ekstreler + taksitler ile).
    detail_q = await db.execute(
        select(CreditCard)
        .where(CreditCard.id == card.id, CreditCard.user_id == current_user.id)
        .options(
            selectinload(CreditCard.statements),
            selectinload(CreditCard.installments),
        )
    )
    card = detail_q.scalar_one()
    sorted_statements = sorted(card.statements, key=lambda x: (x.period_year, x.period_month), reverse=True)
    sorted_installments = sorted(card.installments, key=lambda i: i.first_due_date)
    return CardDetailOut(
        card=_enrich_card(card),
        statements=sorted_statements,
        installments=sorted_installments,
    )
