import io
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.models.tefas import TefasHolding as TefasHoldingModel
from app.models.user import User
from app.schemas.tefas import TefasHolding, TefasPositionOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio/tefas", tags=["tefas"])


@router.get("/holdings", response_model=list[TefasHolding])
async def get_tefas_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id)
    )
    rows = result.scalars().all()
    return [TefasHolding(code=r.code, quantity=float(r.quantity), name=r.name) for r in rows]


@router.put("/holdings", response_model=list[TefasHolding])
async def save_tefas_holdings(
    holdings: list[TefasHolding],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    for h in holdings:
        db.add(TefasHoldingModel(user_id=current_user.id, code=h.code.upper(), quantity=h.quantity, name=h.name))
    await db.commit()
    return holdings


@router.post("/preview", response_model=list[TefasPositionOut])
async def tefas_preview(
    holdings: list[TefasHolding],
    _: Annotated[User, Depends(get_current_user)],
):
    from app.services.tefas import TefasService
    svc = TefasService([{"code": h.code, "quantity": h.quantity, "name": h.name} for h in holdings])
    try:
        assets = await svc.fetch()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return [
        TefasPositionOut(
            code=a.symbol,
            name=a.name,
            quantity=a.liquid_quantity,
            unit_price_tl=a.unit_price_tl,
            total_value_tl=a.liquid_quantity * a.unit_price_tl,
        )
        for a in assets
    ]


@router.get("/export")
async def export_tefas_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from decimal import Decimal
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from app.services.tefas import TefasService

    result = await db.execute(
        select(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id)
    )
    rows = result.scalars().all()

    prices: dict[str, Decimal] = {}
    if rows:
        try:
            svc = TefasService([{"code": r.code, "quantity": float(r.quantity), "name": r.name} for r in rows])
            assets = await svc.fetch()
            prices = {a.symbol: a.unit_price_tl for a in assets}
        except Exception:
            logger.warning("TEFAS export: canlı fiyat alınamadı")

    wb = Workbook()
    ws = wb.active
    ws.title = "TEFAS Holdingleri"
    headers = ["Fon Kodu", "Adet", "İsim", "Birim Fiyat (₺)", "Toplam Değer (₺)"]
    header_fill = PatternFill("solid", fgColor="1D4ED8")
    header_font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, holding in enumerate(rows, 2):
        unit_price = prices.get(holding.code, Decimal("0"))
        total = float(holding.quantity) * float(unit_price)
        ws.cell(row=row_idx, column=1, value=holding.code)
        ws.cell(row=row_idx, column=2, value=float(holding.quantity))
        ws.cell(row=row_idx, column=3, value=holding.name)
        ws.cell(row=row_idx, column=4, value=float(unit_price) if unit_price else "")
        ws.cell(row=row_idx, column=5, value=total if unit_price else "")

    for col, width in zip("ABCDE", [12, 14, 30, 18, 18]):
        ws.column_dimensions[col].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=tefas-holdingleri.xlsx"},
    )


@router.post("/import", response_model=list[TefasHolding])
async def import_tefas_holdings(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from openpyxl import load_workbook

    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sadece .xlsx dosyası kabul edilir")

    content = await file.read()
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dosya okunamadı")

    parsed: list[TefasHolding] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        code = str(row[0]).strip().upper() if row[0] else ""
        qty_raw = row[1]
        name = str(row[2]).strip() if len(row) > 2 and row[2] else ""
        if not code or code == "NONE":
            continue
        try:
            qty = float(qty_raw)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        parsed.append(TefasHolding(code=code, quantity=qty, name=name))

    if not parsed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Geçerli holding bulunamadı")

    await db.execute(delete(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    for h in parsed:
        db.add(TefasHoldingModel(user_id=current_user.id, code=h.code, quantity=h.quantity, name=h.name))
    await db.commit()
    return parsed
