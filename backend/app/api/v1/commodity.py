"""Kıymetli maden (altın/gümüş) CRUD endpoint'leri."""
import io
import logging
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.upload_validation import validate_excel_upload
from app.models.commodity import CommodityHolding
from app.models.user import User
from app.schemas.commodity import (
    CommodityCreate,
    CommodityOut,
    CommodityPositionOut,
    CommoditySummaryOut,
    CommodityUpdate,
)
from app.services.commodity import (
    BIGA_GRAM_WEIGHTS,
    BIGA_METAL,
    COIN_GRAM_WEIGHTS,
    calculate_holding_value,
    fetch_metal_prices,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio/commodities", tags=["commodities"])


@router.get("", response_model=CommoditySummaryOut)
async def list_commodities(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommoditySummaryOut:
    """Kullanıcının tüm kıymetli maden varlıklarını anlık fiyatlarla döndürür."""
    result = await db.execute(
        select(CommodityHolding)
        .where(CommodityHolding.user_id == current_user.id)
        .order_by(CommodityHolding.created_at)
    )
    holdings = result.scalars().all()

    prices = await fetch_metal_prices()
    gold_price = prices["gold"]
    silver_price = prices["silver"]
    gold_price_available = gold_price > 0
    silver_price_available = silver_price > 0

    positions: list[CommodityPositionOut] = []
    total_gold_gram = Decimal("0")
    total_silver_gram = Decimal("0")
    total_value_tl = Decimal("0")

    for h in holdings:
        try:
            val = calculate_holding_value(h, gold_price, silver_price)
        except ValueError as exc:
            logger.error("Holding %d değer hesaplanamadı: %s", h.id, exc)
            continue

        gram_eq = val["gram_equivalent"]
        value_tl = val["total_value_tl"]

        if h.metal == "gold":
            total_gold_gram += gram_eq
        else:
            total_silver_gram += gram_eq
        total_value_tl += value_tl

        positions.append(
            CommodityPositionOut(
                id=h.id,
                unit_type=h.unit_type,
                metal=h.metal,
                biga_code=h.biga_code,
                coin_type=h.coin_type,
                quantity=h.quantity,
                notes=h.notes,
                created_at=h.created_at,
                gram_equivalent=gram_eq,
                total_value_tl=value_tl,
                gold_price_tl=gold_price,
                silver_price_tl=silver_price,
            )
        )

    return CommoditySummaryOut(
        positions=positions,
        total_gold_gram=total_gold_gram.quantize(Decimal("0.0001")),
        total_silver_gram=total_silver_gram.quantize(Decimal("0.0001")),
        total_value_tl=total_value_tl.quantize(Decimal("0.01")),
        gold_price_tl=gold_price,
        silver_price_tl=silver_price,
        gold_price_available=gold_price_available,
        silver_price_available=silver_price_available,
    )


@router.post("", response_model=CommodityOut, status_code=status.HTTP_201_CREATED)
async def create_commodity(
    payload: CommodityCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommodityHolding:
    """Yeni kıymetli maden varlığı ekler."""
    holding = CommodityHolding(
        user_id=current_user.id,
        unit_type=payload.unit_type,
        metal=payload.metal,
        biga_code=payload.biga_code,
        coin_type=payload.coin_type,
        quantity=payload.quantity,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


@router.put("/{holding_id}", response_model=CommodityOut)
async def update_commodity(
    holding_id: int,
    payload: CommodityUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommodityHolding:
    """Kıymetli maden varlığının miktar ve notunu günceller."""
    result = await db.execute(
        select(CommodityHolding).where(
            CommodityHolding.id == holding_id,
            CommodityHolding.user_id == current_user.id,
        )
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")

    if payload.quantity is not None:
        holding.quantity = payload.quantity
    if payload.notes is not None:
        holding.notes = payload.notes.strip() or None

    await db.commit()
    await db.refresh(holding)
    return holding


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commodity(
    holding_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Kıymetli maden varlığını siler."""
    result = await db.execute(
        select(CommodityHolding).where(
            CommodityHolding.id == holding_id,
            CommodityHolding.user_id == current_user.id,
        )
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")
    await db.delete(holding)
    await db.commit()


@router.get("/export")
async def export_commodities(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Kıymetli maden varlıklarını Excel dosyası olarak indir."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl kütüphanesi bulunamadı")

    result = await db.execute(
        select(CommodityHolding)
        .where(CommodityHolding.user_id == current_user.id)
        .order_by(CommodityHolding.created_at)
    )
    holdings = result.scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Altın-Gümüş"

    # Başlık satırı: altın sarısı arka plan, beyaz bold
    header_fill = PatternFill(start_color="D97706", end_color="D97706", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    headers = ["Tür", "Metal", "BiGA Kodu", "Sikke Türü", "Miktar", "Not", "Oluşturma Tarihi"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, h in enumerate(holdings, start=2):
        ws.cell(row=row_idx, column=1, value=h.unit_type)
        ws.cell(row=row_idx, column=2, value=h.metal)
        ws.cell(row=row_idx, column=3, value=h.biga_code or "")
        ws.cell(row=row_idx, column=4, value=h.coin_type or "")
        ws.cell(row=row_idx, column=5, value=float(h.quantity))
        ws.cell(row=row_idx, column=6, value=h.notes or "")
        ws.cell(row=row_idx, column=7, value=str(h.created_at.date()))

    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 36
    ws.column_dimensions["G"].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=altin-gumus.xlsx"},
    )


@router.post("/import", response_model=list[CommodityOut], status_code=status.HTTP_201_CREATED)
async def import_commodities(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Excel dosyasından kıymetli maden varlığı içe aktar (append — mevcut kayıtlar silinmez)."""
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl kütüphanesi bulunamadı")

    # SEC-009 (FAZ H): magic-byte + boyut + extension dogrulamasi
    content = await validate_excel_upload(file)
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz Excel dosyası")

    ws = wb.active
    valid_unit_types = {"gram", "biga", "coin"}
    valid_metals = {"gold", "silver"}
    valid_biga = frozenset(BIGA_GRAM_WEIGHTS.keys())
    valid_coin = frozenset(COIN_GRAM_WEIGHTS.keys())

    added: list[CommodityHolding] = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or all(v is None for v in row):
            continue

        unit_type_val = str(row[0]).strip().lower() if row[0] is not None else ""
        metal_val = str(row[1]).strip().lower() if len(row) > 1 and row[1] is not None else "gold"
        biga_code_val = str(row[2]).strip().upper() if len(row) > 2 and row[2] else None
        coin_type_val = str(row[3]).strip().lower() if len(row) > 3 and row[3] else None
        quantity_val = row[4] if len(row) > 4 else None
        notes_val = str(row[5]).strip() if len(row) > 5 and row[5] else None

        # unit_type doğrulama
        if unit_type_val not in valid_unit_types:
            continue

        # metal doğrulama
        if metal_val not in valid_metals:
            metal_val = "gold"

        # Miktar
        try:
            quantity = Decimal(str(quantity_val)).quantize(Decimal("0.0001"))
            if quantity <= 0:
                continue
        except (InvalidOperation, TypeError):
            continue

        # Tür bazlı doğrulama
        resolved_metal = metal_val
        resolved_biga: str | None = None
        resolved_coin: str | None = None

        if unit_type_val == "biga":
            if not biga_code_val or biga_code_val not in valid_biga:
                continue
            resolved_biga = biga_code_val
            resolved_metal = BIGA_METAL[biga_code_val]
        elif unit_type_val == "coin":
            if not coin_type_val or coin_type_val not in valid_coin:
                continue
            resolved_coin = coin_type_val
            resolved_metal = "gold"

        holding = CommodityHolding(
            user_id=current_user.id,
            unit_type=unit_type_val,
            metal=resolved_metal,
            biga_code=resolved_biga,
            coin_type=resolved_coin,
            quantity=quantity,
            notes=notes_val or None,
        )
        db.add(holding)
        added.append(holding)

    await db.commit()
    for h in added:
        await db.refresh(h)

    return added
