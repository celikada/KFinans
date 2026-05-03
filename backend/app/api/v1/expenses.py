import calendar
import io
import logging
from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import (
    EXPENSE_CATEGORIES,
    CategoryBreakdown,
    ExpenseCreate,
    ExpenseOut,
    ExpenseSummary,
    ExpenseUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/expenses", tags=["expenses"])

# Türkçe label -> İngilizce key haritası (import için)
LABEL_TO_KEY: dict[str, str] = {
    "yiyecek": "food", "market": "groceries", "ulaşım": "transport",
    "faturalar": "bills", "sağlık": "health", "eğlence": "entertainment",
    "giyim": "clothing", "ev": "home", "vergi": "tax", "diğer": "other",
    "food": "food", "groceries": "groceries", "transport": "transport",
    "bills": "bills", "health": "health", "entertainment": "entertainment",
    "clothing": "clothing", "home": "home", "tax": "tax", "other": "other",
}


@router.get("", response_model=list[ExpenseOut])
async def list_expenses(
    year: int | None = Query(default=None, ge=2020, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Harcama listesi — opsiyonel year/month/category filtresi.

    En son tarihliden eskiye sirayla doner; ayni gun icindekiler en son
    eklenen ust sirada.
    """
    stmt = select(Expense).where(Expense.user_id == current_user.id)
    if year is not None and month is not None:
        first_day = date_type(year, month, 1)
        last_day = date_type(year, month, calendar.monthrange(year, month)[1])
        stmt = stmt.where(Expense.date >= first_day, Expense.date <= last_day)
    if category:
        if category not in EXPENSE_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Geçersiz kategori: {category}",
            )
        stmt = stmt.where(Expense.category == category)
    stmt = stmt.order_by(desc(Expense.date), desc(Expense.created_at))

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    expense = Expense(
        user_id=current_user.id,
        amount=payload.amount,
        category=payload.category,
        date=payload.date,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense


@router.put("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == current_user.id,
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Harcama bulunamadı")

    if payload.amount is not None:
        expense.amount = payload.amount
    if payload.category is not None:
        expense.category = payload.category
    if payload.date is not None:
        expense.date = payload.date
    if payload.description is not None:
        expense.description = payload.description.strip() or None

    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == current_user.id,
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Harcama bulunamadı")

    await db.delete(expense)
    await db.commit()


@router.get("/summary", response_model=ExpenseSummary)
async def get_expense_summary(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Belirli ay icin toplam + kategori bazinda kirilim."""
    first_day = date_type(year, month, 1)
    last_day = date_type(year, month, calendar.monthrange(year, month)[1])

    # Toplam ve adet
    total_q = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.id))
        .where(
            Expense.user_id == current_user.id,
            Expense.date >= first_day,
            Expense.date <= last_day,
        )
    )
    total, count = total_q.one()

    # Kategori kirilimi
    cat_q = await db.execute(
        select(
            Expense.category,
            func.sum(Expense.amount),
            func.count(Expense.id),
        )
        .where(
            Expense.user_id == current_user.id,
            Expense.date >= first_day,
            Expense.date <= last_day,
        )
        .group_by(Expense.category)
        .order_by(desc(func.sum(Expense.amount)))
    )
    breakdown = [
        CategoryBreakdown(category=cat, total=Decimal(amt), count=cnt)
        for cat, amt, cnt in cat_q.all()
    ]

    return ExpenseSummary(
        year=year,
        month=month,
        total=Decimal(total),
        count=count,
        by_category=breakdown,
    )


@router.get("/export")
async def export_expenses(
    year: int | None = Query(default=None, ge=2020, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Harcamaları Excel dosyası olarak indir."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl kütüphanesi bulunamadı")

    stmt = select(Expense).where(Expense.user_id == current_user.id)
    if year is not None and month is not None:
        first_day = date_type(year, month, 1)
        last_day = date_type(year, month, calendar.monthrange(year, month)[1])
        stmt = stmt.where(Expense.date >= first_day, Expense.date <= last_day)
    stmt = stmt.order_by(Expense.date, Expense.created_at)

    result = await db.execute(stmt)
    expenses = result.scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Harcamalar"

    # Başlık satırı: kırmızı arka plan, beyaz bold
    header_fill = PatternFill(start_color="DC2626", end_color="DC2626", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    headers = ["Tarih", "Kategori", "Tutar (₺)", "Açıklama"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Veri satırları
    for row_idx, exp in enumerate(expenses, start=2):
        ws.cell(row=row_idx, column=1, value=str(exp.date))
        ws.cell(row=row_idx, column=2, value=exp.category)
        ws.cell(row=row_idx, column=3, value=float(exp.amount))
        ws.cell(row=row_idx, column=4, value=exp.description or "")

    # Kolon genişliği
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 40

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=harcamalar.xlsx"},
    )


@router.post("/import", response_model=list[ExpenseOut], status_code=status.HTTP_201_CREATED)
async def import_expenses(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Excel dosyasından harcama içe aktar (append — mevcut kayıtlar silinmez)."""
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl kütüphanesi bulunamadı")

    content = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz Excel dosyası")

    ws = wb.active
    added: list[Expense] = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or all(v is None for v in row):
            continue
        n = len(row)
        date_val, cat_val, amount_val, desc_val = (
            row[i] if i < n else None for i in range(4)
        )

        # Tarih parse
        if isinstance(date_val, date_type):
            parsed_date = date_val
        elif isinstance(date_val, str):
            try:
                parsed_date = date_type.fromisoformat(date_val.strip())
            except ValueError:
                continue
        else:
            # Excel numeric date
            try:
                from openpyxl.utils.datetime import from_excel
                parsed_date = from_excel(date_val).date() if date_val is not None else None
                if parsed_date is None:
                    continue
            except Exception:
                continue

        # Kategori normalize
        cat_str = str(cat_val).strip().lower() if cat_val is not None else ""
        category = LABEL_TO_KEY.get(cat_str)
        if not category:
            continue

        # Tutar
        try:
            amount = Decimal(str(amount_val)).quantize(Decimal("0.01"))
            if amount <= 0:
                continue
        except (InvalidOperation, TypeError):
            continue

        description = str(desc_val).strip() if desc_val else None

        exp = Expense(
            user_id=current_user.id,
            amount=amount,
            category=category,
            date=parsed_date,
            description=description or None,
        )
        db.add(exp)
        added.append(exp)

    await db.commit()
    for exp in added:
        await db.refresh(exp)

    return added
