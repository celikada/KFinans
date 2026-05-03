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
from app.models.income import Income
from app.models.user import User
from app.schemas.income import (
    INCOME_CATEGORIES,
    IncomeCategoryBreakdown,
    IncomeCreate,
    IncomeOut,
    IncomeSummary,
    IncomeUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/income", tags=["income"])

# Türkçe label -> İngilizce key haritası (import için)
LABEL_TO_KEY: dict[str, str] = {
    "maaş": "salary", "serbest meslek": "freelance", "kira geliri": "rental",
    "temettü / faiz": "dividend", "temettü": "dividend", "ikramiye / prim": "bonus",
    "ikramiye": "bonus", "varlık satışı": "sale", "diğer": "other",
    "salary": "salary", "freelance": "freelance", "rental": "rental",
    "dividend": "dividend", "bonus": "bonus", "sale": "sale", "other": "other",
}


@router.get("", response_model=list[IncomeOut])
async def list_incomes(
    year: int | None = Query(default=None, ge=2020, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Income).where(Income.user_id == current_user.id)
    if year is not None and month is not None:
        first_day = date_type(year, month, 1)
        last_day = date_type(year, month, calendar.monthrange(year, month)[1])
        stmt = stmt.where(Income.date >= first_day, Income.date <= last_day)
    if category:
        if category not in INCOME_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Geçersiz kategori: {category}",
            )
        stmt = stmt.where(Income.category == category)
    stmt = stmt.order_by(desc(Income.date), desc(Income.created_at))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=IncomeOut, status_code=status.HTTP_201_CREATED)
async def create_income(
    payload: IncomeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inc = Income(
        user_id=current_user.id,
        amount=payload.amount,
        category=payload.category,
        date=payload.date,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(inc)
    await db.commit()
    await db.refresh(inc)
    return inc


@router.put("/{income_id}", response_model=IncomeOut)
async def update_income(
    income_id: int,
    payload: IncomeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Income).where(Income.id == income_id, Income.user_id == current_user.id)
    )
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")

    if payload.amount is not None:
        inc.amount = payload.amount
    if payload.category is not None:
        inc.category = payload.category
    if payload.date is not None:
        inc.date = payload.date
    if payload.description is not None:
        inc.description = payload.description.strip() or None

    await db.commit()
    await db.refresh(inc)
    return inc


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income(
    income_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Income).where(Income.id == income_id, Income.user_id == current_user.id)
    )
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")
    await db.delete(inc)
    await db.commit()


@router.get("/summary", response_model=IncomeSummary)
async def get_income_summary(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    first_day = date_type(year, month, 1)
    last_day = date_type(year, month, calendar.monthrange(year, month)[1])

    total_q = await db.execute(
        select(func.coalesce(func.sum(Income.amount), 0), func.count(Income.id))
        .where(Income.user_id == current_user.id, Income.date >= first_day, Income.date <= last_day)
    )
    total, count = total_q.one()

    cat_q = await db.execute(
        select(Income.category, func.sum(Income.amount), func.count(Income.id))
        .where(Income.user_id == current_user.id, Income.date >= first_day, Income.date <= last_day)
        .group_by(Income.category)
        .order_by(desc(func.sum(Income.amount)))
    )
    breakdown = [
        IncomeCategoryBreakdown(category=cat, total=Decimal(amt), count=cnt)
        for cat, amt, cnt in cat_q.all()
    ]

    return IncomeSummary(
        year=year, month=month,
        total=Decimal(total), count=count,
        by_category=breakdown,
    )


@router.get("/export")
async def export_incomes(
    year: int | None = Query(default=None, ge=2020, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gelirleri Excel dosyası olarak indir."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl kütüphanesi bulunamadı")

    stmt = select(Income).where(Income.user_id == current_user.id)
    if year is not None and month is not None:
        first_day = date_type(year, month, 1)
        last_day = date_type(year, month, calendar.monthrange(year, month)[1])
        stmt = stmt.where(Income.date >= first_day, Income.date <= last_day)
    stmt = stmt.order_by(Income.date, Income.created_at)

    result = await db.execute(stmt)
    incomes = result.scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gelirler"

    # Başlık satırı: yeşil arka plan, beyaz bold
    header_fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    headers = ["Tarih", "Kategori", "Tutar (₺)", "Açıklama"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, inc in enumerate(incomes, start=2):
        ws.cell(row=row_idx, column=1, value=str(inc.date))
        ws.cell(row=row_idx, column=2, value=inc.category)
        ws.cell(row=row_idx, column=3, value=float(inc.amount))
        ws.cell(row=row_idx, column=4, value=inc.description or "")

    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 40

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=gelirler.xlsx"},
    )


@router.post("/import", response_model=list[IncomeOut], status_code=status.HTTP_201_CREATED)
async def import_incomes(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Excel dosyasından gelir içe aktar (append — mevcut kayıtlar silinmez)."""
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
    added: list[Income] = []

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

        inc = Income(
            user_id=current_user.id,
            amount=amount,
            category=category,
            date=parsed_date,
            description=description or None,
        )
        db.add(inc)
        added.append(inc)

    await db.commit()
    for inc in added:
        await db.refresh(inc)

    return added
