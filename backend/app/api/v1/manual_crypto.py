"""API'siz borsa hesapları için manuel kripto holding CRUD + Excel + preview."""
from decimal import Decimal
from io import BytesIO
from typing import Annotated

import openpyxl
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.manual_crypto import ManualCryptoHolding
from app.models.user import User
from app.schemas.manual_crypto import (
    ManualCryptoCreate,
    ManualCryptoOut,
    ManualCryptoPositionOut,
    ManualCryptoSummaryOut,
    ManualCryptoUpdate,
)
from app.services.aggregator import fetch_spot_prices, fetch_usd_to_tl, lookup_usd_price

router = APIRouter(prefix="/manual-crypto", tags=["manual-crypto"])


def _calc_gain_loss(
    quantity: Decimal, total_tl: Decimal, avg_cost_tl: Decimal | None
) -> tuple[Decimal | None, Decimal | None, float | None]:
    """Avg cost varsa: cost_basis, gain_loss, gain_loss_pct döner; yoksa None'lar."""
    if avg_cost_tl is None or avg_cost_tl <= 0:
        return None, None, None
    cost_basis = (quantity * avg_cost_tl).quantize(Decimal("0.01"))
    gain_loss = (total_tl - cost_basis).quantize(Decimal("0.01"))
    pct = float(gain_loss / cost_basis * 100) if cost_basis > 0 else None
    return cost_basis, gain_loss, pct


async def _enrich_positions(
    holdings: list[ManualCryptoHolding],
) -> ManualCryptoSummaryOut:
    """Holdings listesini anlık fiyatlarla zenginleştirir (Binance USDT pariteleri)."""
    if not holdings:
        return ManualCryptoSummaryOut(positions=[], total_value_tl=Decimal(0), unknown_symbols=[])

    unique_symbols = list({h.symbol for h in holdings})
    prices, usd_tl = await _fetch_prices_safe(unique_symbols)

    positions: list[ManualCryptoPositionOut] = []
    total_tl = Decimal(0)
    unknown: list[str] = []
    for h in holdings:
        usd = lookup_usd_price(h.symbol, prices)
        unit_tl = (usd * usd_tl).quantize(Decimal("0.0001")) if usd > 0 else Decimal(0)
        value_tl = (h.quantity * unit_tl).quantize(Decimal("0.01"))
        total_tl += value_tl
        if usd <= 0:
            unknown.append(h.symbol)
        cost_basis, gain_loss, gain_loss_pct = _calc_gain_loss(
            h.quantity, value_tl, h.avg_cost_tl
        )
        positions.append(ManualCryptoPositionOut(
            id=h.id,
            exchange=h.exchange,
            label=h.label,
            symbol=h.symbol,
            quantity=h.quantity,
            avg_cost_tl=h.avg_cost_tl,
            unit_price_usd=usd,
            unit_price_tl=unit_tl,
            total_value_tl=value_tl,
            cost_basis_tl=cost_basis,
            gain_loss_tl=gain_loss,
            gain_loss_pct=gain_loss_pct,
            notes=h.notes,
        ))
    return ManualCryptoSummaryOut(
        positions=positions,
        total_value_tl=total_tl.quantize(Decimal("0.01")),
        unknown_symbols=sorted(set(unknown)),
    )


async def _fetch_prices_safe(symbols: list[str]) -> tuple[dict[str, Decimal], Decimal]:
    """Binance + USD/TL — hata durumunda boş dict + 0 dönmek yerine 503."""
    try:
        prices = await fetch_spot_prices(symbols)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Binance fiyatları çekilemedi: {e}",
        )
    try:
        usd_tl = await fetch_usd_to_tl()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"USD/TL kuru çekilemedi: {e}",
        )
    return prices, usd_tl


@router.get("", response_model=ManualCryptoSummaryOut)
async def list_manual_crypto(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tüm manuel kripto pozisyonları + anlık fiyatla TL değer + kâr/zarar."""
    rows = (await db.execute(
        select(ManualCryptoHolding)
        .where(ManualCryptoHolding.user_id == current_user.id)
        .order_by(ManualCryptoHolding.exchange, ManualCryptoHolding.symbol)
    )).scalars().all()
    return await _enrich_positions(list(rows))


@router.post("", response_model=ManualCryptoOut, status_code=status.HTTP_201_CREATED)
async def create_manual_crypto(
    payload: ManualCryptoCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    holding = ManualCryptoHolding(
        user_id=current_user.id,
        exchange=payload.exchange,
        label=payload.label,
        symbol=payload.symbol,
        quantity=payload.quantity,
        avg_cost_tl=payload.avg_cost_tl,
        notes=payload.notes,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


@router.put("/{holding_id}", response_model=ManualCryptoOut)
async def update_manual_crypto(
    holding_id: int,
    payload: ManualCryptoUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    holding = (await db.execute(
        select(ManualCryptoHolding).where(
            ManualCryptoHolding.id == holding_id,
            ManualCryptoHolding.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=404, detail="Manuel kripto kaydı bulunamadı")
    if payload.exchange is not None:
        holding.exchange = payload.exchange
    if payload.label is not None:
        holding.label = payload.label
    if payload.symbol is not None:
        holding.symbol = payload.symbol
    if payload.quantity is not None:
        holding.quantity = payload.quantity
    if payload.avg_cost_tl is not None:
        holding.avg_cost_tl = payload.avg_cost_tl
    if payload.notes is not None:
        holding.notes = payload.notes
    await db.commit()
    await db.refresh(holding)
    return holding


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manual_crypto(
    holding_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        delete(ManualCryptoHolding).where(
            ManualCryptoHolding.id == holding_id,
            ManualCryptoHolding.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Manuel kripto kaydı bulunamadı")
    await db.commit()


@router.get("/export")
async def export_manual_crypto(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Excel export — kullanıcı dosyayı düzenleyip import edebilir."""
    rows = (await db.execute(
        select(ManualCryptoHolding)
        .where(ManualCryptoHolding.user_id == current_user.id)
        .order_by(ManualCryptoHolding.exchange, ManualCryptoHolding.symbol)
    )).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Manuel Kripto"
    headers = ["Borsa", "Etiket", "Sembol", "Miktar", "Ort. Maliyet (TL)", "Notlar"]
    ws.append(headers)
    # Header stilini biraz belirginleştir
    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        cell.fill = openpyxl.styles.PatternFill(start_color="F59E0B", end_color="F59E0B", fill_type="solid")

    for r in rows:
        ws.append([
            r.exchange,
            r.label or "",
            r.symbol,
            float(r.quantity),
            float(r.avg_cost_tl) if r.avg_cost_tl else "",
            r.notes or "",
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=manuel_kripto.xlsx"},
    )


@router.post("/import")
async def import_manual_crypto(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Excel import. Mevcut tüm manuel kayıtlar SİLİNİP yenisi yüklenir
    (replace-all semantik — expenses/income import ile aynı pattern)."""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lütfen .xlsx veya .xls dosyası yükleyin.",
        )

    content = await file.read()
    try:
        wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Excel okunamadı: {e}",
        )
    ws = wb.active
    if ws.max_row < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Boş dosya — en az 1 satır veri gerekli.",
        )

    new_rows: list[ManualCryptoHolding] = []
    errors: list[str] = []
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or all(v in (None, "") for v in row):
            continue
        try:
            exchange = str(row[0]).strip() if row[0] else ""
            label = str(row[1]).strip() if row[1] else None
            symbol = str(row[2]).strip().upper() if row[2] else ""
            qty_raw = row[3]
            avg_cost_raw = row[4] if len(row) > 4 else None
            notes = str(row[5]).strip() if len(row) > 5 and row[5] else None

            if not exchange or not symbol or qty_raw in (None, ""):
                errors.append(f"Satır {idx}: Borsa, Sembol ve Miktar zorunlu")
                continue
            quantity = Decimal(str(qty_raw))
            if quantity <= 0:
                errors.append(f"Satır {idx}: Miktar pozitif olmalı")
                continue
            avg_cost = None
            if avg_cost_raw not in (None, ""):
                avg_cost = Decimal(str(avg_cost_raw))
                if avg_cost <= 0:
                    avg_cost = None
            new_rows.append(ManualCryptoHolding(
                user_id=current_user.id,
                exchange=exchange[:40],
                label=label[:100] if label else None,
                symbol=symbol[:20],
                quantity=quantity,
                avg_cost_tl=avg_cost,
                notes=notes[:500] if notes else None,
            ))
        except Exception as e:
            errors.append(f"Satır {idx}: {e}")

    if errors and not new_rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hiçbir satır işlenemedi: " + "; ".join(errors[:5]),
        )

    # Replace-all — mevcut kayıtları sil, yenilerini ekle
    await db.execute(
        delete(ManualCryptoHolding).where(ManualCryptoHolding.user_id == current_user.id)
    )
    db.add_all(new_rows)
    await db.commit()
    return {"imported": len(new_rows), "errors": errors}
