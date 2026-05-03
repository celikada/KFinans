import io
import logging
from decimal import Decimal
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
    return [
        TefasHolding(
            code=r.code,
            quantity=float(r.quantity),
            name=r.name,
            avg_cost_tl=float(r.avg_cost_tl) if r.avg_cost_tl is not None else None,
            distributor=r.distributor,
        )
        for r in rows
    ]


@router.put("/holdings", response_model=list[TefasHolding])
async def save_tefas_holdings(
    holdings: list[TefasHolding],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    for h in holdings:
        db.add(TefasHoldingModel(
            user_id=current_user.id,
            code=h.code.upper(),
            quantity=h.quantity,
            name=h.name,
            avg_cost_tl=h.avg_cost_tl,
            distributor=h.distributor,
        ))
    await db.commit()
    return holdings


def _calc_gain_loss(
    total_value_tl: Decimal,
    qty: Decimal,
    avg_cost_tl: float | None,
) -> tuple[Decimal | None, Decimal | None, float | None]:
    """Kâr/zarar hesaplar. (cost_basis, gain_loss_tl, gain_loss_pct) döner."""
    if avg_cost_tl is None:
        return None, None, None
    avg_cost = Decimal(str(avg_cost_tl))
    cost_basis = (qty * avg_cost).quantize(Decimal("0.01"))
    gain_loss = (total_value_tl - cost_basis).quantize(Decimal("0.01"))
    gain_loss_pct = float(gain_loss / cost_basis * 100) if cost_basis > 0 else None
    return cost_basis, gain_loss, gain_loss_pct


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

    # Servis holdings sırasını koruyarak asset döndürür → zip ile eşleştir
    out = []
    for h, a in zip(holdings, assets):
        qty = a.liquid_quantity
        total_value_tl = (qty * a.unit_price_tl).quantize(Decimal("0.01"))
        avg_cost_raw = h.avg_cost_tl
        avg_cost_dec = Decimal(str(avg_cost_raw)) if avg_cost_raw is not None else None
        cost_basis, gain_loss, gain_loss_pct = _calc_gain_loss(total_value_tl, qty, avg_cost_raw)

        out.append(TefasPositionOut(
            code=a.symbol,
            name=a.name,
            quantity=qty,
            unit_price_tl=a.unit_price_tl,
            total_value_tl=total_value_tl,
            avg_cost_tl=avg_cost_dec,
            cost_basis_tl=cost_basis,
            gain_loss_tl=gain_loss,
            gain_loss_pct=gain_loss_pct,
            distributor=h.distributor,
        ))
    return out


@router.get("/export")
async def export_tefas_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    headers = ["Fon Kodu", "Adet", "İsim", "Birim Fiyat (₺)", "Toplam Değer (₺)", "Ort. Maliyet (₺)", "Kâr/Zarar (₺)", "Kurum"]
    header_fill = PatternFill("solid", fgColor="1D4ED8")
    header_font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, holding in enumerate(rows, 2):
        unit_price = prices.get(holding.code, Decimal("0"))
        total = float(holding.quantity) * float(unit_price) if unit_price else None
        avg_cost = float(holding.avg_cost_tl) if holding.avg_cost_tl is not None else None
        gain_loss = None
        if total is not None and avg_cost is not None:
            cost_basis = float(holding.quantity) * avg_cost
            gain_loss = round(total - cost_basis, 2)
        ws.cell(row=row_idx, column=1, value=holding.code)
        ws.cell(row=row_idx, column=2, value=float(holding.quantity))
        ws.cell(row=row_idx, column=3, value=holding.name)
        ws.cell(row=row_idx, column=4, value=float(unit_price) if unit_price else "")
        ws.cell(row=row_idx, column=5, value=total if total is not None else "")
        ws.cell(row=row_idx, column=6, value=avg_cost if avg_cost is not None else "")
        ws.cell(row=row_idx, column=7, value=gain_loss if gain_loss is not None else "")
        ws.cell(row=row_idx, column=8, value=holding.distributor or "")

    for col, width in zip("ABCDEFGH", [12, 14, 30, 18, 18, 18, 18, 20]):
        ws.column_dimensions[col].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=tefas-holdingleri.xlsx"},
    )


@router.post("/import-mkk", response_model=list[TefasHolding])
async def import_tefas_mkk(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """MKK e-Yatırımcı 'Tüm Kıymetler' raporundan TEFAS fonlarını içe aktarır.

    Beklenen format (.xls binary, xlrd 1.2.0):
      Header satırı: Üye, Hesap, Kıymet Sınıfı, Menkul Kıymet Kodu, Kıymet Adı,
                     Ek Tanım, Alt Hesap, Adet, Fiyat (TL), ...
      Sadece "Kıymet Sınıfı = Fon" satırları işlenir.
    """
    import xlrd

    if not file.filename or not file.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sadece .xls veya .xlsx dosyası kabul edilir",
        )
    content = await file.read()
    try:
        wb = xlrd.open_workbook(file_contents=content)
        sh = wb.sheet_by_index(0)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MKK Excel dosyası okunamadı (.xls binary formatında olmalı)",
        )

    # Header satırını "Üye" sütunundan tespit et
    header_row = None
    for r in range(min(sh.nrows, 20)):
        first = str(sh.cell_value(r, 0)).strip()
        if first.lower() == "üye":
            header_row = r
            break
    if header_row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MKK formatı tanınmadı: 'Üye' başlık satırı bulunamadı",
        )

    parsed: list[TefasHolding] = []
    for r in range(header_row + 1, sh.nrows):
        kind = str(sh.cell_value(r, 2)).strip()
        if kind.lower() != "fon":
            continue
        code_raw = sh.cell_value(r, 3)
        code = str(code_raw).strip().upper() if code_raw else ""
        if not code:
            continue
        name_raw = sh.cell_value(r, 4)
        name = str(name_raw).strip() if name_raw else ""
        try:
            qty = float(sh.cell_value(r, 7))
            price = float(sh.cell_value(r, 8))
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        member = str(sh.cell_value(r, 0)).strip() or None
        if member:
            member = member[:50]
        parsed.append(TefasHolding(
            code=code,
            quantity=qty,
            name=name,
            avg_cost_tl=price if price > 0 else None,
            distributor=member,
        ))

    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dosyada 'Fon' kıymet sınıfında geçerli kayıt bulunamadı",
        )

    await db.execute(delete(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    for h in parsed:
        db.add(TefasHoldingModel(
            user_id=current_user.id,
            code=h.code,
            quantity=h.quantity,
            name=h.name,
            avg_cost_tl=h.avg_cost_tl,
            distributor=h.distributor,
        ))
    await db.commit()
    return parsed


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
        avg_cost_raw = row[3] if len(row) > 3 else None
        # Export sırası: Adet(B), İsim(C), Birim(D), Toplam(E), Ort.Maliyet(F), Kâr/Zarar(G), Kurum(H)
        # Import sırası: aynı template + son sütun Kurum (H, index 7)
        distributor_raw = row[7] if len(row) > 7 else None
        if not code or code == "NONE":
            continue
        try:
            qty = float(qty_raw)
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        avg_cost_tl: float | None = None
        if avg_cost_raw is not None:
            try:
                avg_cost_tl = float(avg_cost_raw)
                if avg_cost_tl <= 0:
                    avg_cost_tl = None
            except (TypeError, ValueError):
                avg_cost_tl = None
        distributor: str | None = None
        if distributor_raw:
            distributor = str(distributor_raw).strip()[:50] or None
        parsed.append(TefasHolding(
            code=code, quantity=qty, name=name,
            avg_cost_tl=avg_cost_tl, distributor=distributor,
        ))

    if not parsed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Geçerli holding bulunamadı")

    await db.execute(delete(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    for h in parsed:
        db.add(TefasHoldingModel(
            user_id=current_user.id,
            code=h.code,
            quantity=h.quantity,
            name=h.name,
            avg_cost_tl=h.avg_cost_tl,
        ))
    await db.commit()
    return parsed
