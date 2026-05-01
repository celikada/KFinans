import io
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.bes import BesHolding as BesHoldingModel
from app.models.user import User
from app.schemas.bes import BesHolding

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio/bes", tags=["bes"])


@router.get("/holdings", response_model=list[BesHolding])
async def get_bes_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BesHoldingModel).where(BesHoldingModel.user_id == current_user.id)
    )
    rows = result.scalars().all()
    return [BesHolding(plan_name=r.plan_name, total_value_tl=r.total_value_tl) for r in rows]


@router.put("/holdings", response_model=list[BesHolding])
async def save_bes_holdings(
    holdings: list[BesHolding],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(BesHoldingModel).where(BesHoldingModel.user_id == current_user.id))
    for h in holdings:
        db.add(BesHoldingModel(
            user_id=current_user.id,
            plan_name=h.plan_name.strip(),
            total_value_tl=h.total_value_tl,
        ))
    await db.commit()
    return holdings


@router.get("/export")
async def export_bes_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    result = await db.execute(
        select(BesHoldingModel).where(BesHoldingModel.user_id == current_user.id)
    )
    rows = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "BES Holdingleri"
    headers = ["Plan Adı", "Toplam Değer (₺)"]
    header_fill = PatternFill("solid", fgColor="047857")
    header_font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, holding in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=holding.plan_name)
        ws.cell(row=row_idx, column=2, value=float(holding.total_value_tl))

    for col, width in zip("AB", [42, 20]):
        ws.column_dimensions[col].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bes-holdingleri.xlsx"},
    )


@router.post("/import", response_model=list[BesHolding])
async def import_bes_holdings(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from openpyxl import load_workbook

    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sadece .xlsx dosyası kabul edilir",
        )

    content = await file.read()
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dosya okunamadı",
        )

    parsed: list[BesHolding] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        plan_name = str(row[0]).strip() if row[0] else ""
        value_raw = row[1] if len(row) > 1 else None
        if not plan_name or plan_name.lower() == "none":
            continue
        try:
            value = Decimal(str(value_raw))
        except (TypeError, ValueError, ArithmeticError):
            continue
        if value < 0:
            continue
        parsed.append(BesHolding(plan_name=plan_name, total_value_tl=value))

    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Geçerli BES kaydı bulunamadı",
        )

    await db.execute(delete(BesHoldingModel).where(BesHoldingModel.user_id == current_user.id))
    for h in parsed:
        db.add(BesHoldingModel(
            user_id=current_user.id,
            plan_name=h.plan_name,
            total_value_tl=h.total_value_tl,
        ))
    await db.commit()
    return parsed
