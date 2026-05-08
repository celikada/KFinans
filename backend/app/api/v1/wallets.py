import io
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.core.masking import mask_address as _mask_address  # BACK-013: central helper
from app.models.integration import WalletAddress
from app.models.user import User
from app.schemas.integration import WalletCreate, WalletOut
from app.services.audit import AuditAction, log_audit

router = APIRouter(prefix="/wallets", tags=["wallets"])

VALID_CHAINS = {
    "sonic", "avalanche_c", "avalanche_p", "ethereum", "bitcoin",
    "solana", "cardano", "algorand", "polkadot", "litecoin",
}


@router.get("", response_model=list[WalletOut])
async def list_wallets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WalletAddress).where(WalletAddress.user_id == current_user.id, WalletAddress.is_active.is_(True))
    )
    return result.scalars().all()


@router.post("", response_model=WalletOut, status_code=status.HTTP_201_CREATED)
async def add_wallet(
    request: Request,
    payload: WalletCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.chain not in VALID_CHAINS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Geçersiz zincir: {payload.chain}",
        )
    wallet = WalletAddress(
        user_id=current_user.id,
        chain=payload.chain,
        address=payload.address,
        label=payload.label,
    )
    db.add(wallet)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu cüzdan zaten kayıtlı",
        )
    await log_audit(
        db, request,
        action=AuditAction.WALLET_ADD,
        user_id=current_user.id,
        resource=f"wallet:{wallet.id}",
        extra={"chain": payload.chain, "label": payload.label},
    )
    await db.commit()
    await db.refresh(wallet)
    return wallet


@router.delete("/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wallet(
    wallet_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WalletAddress).where(
            WalletAddress.id == uuid.UUID(wallet_id),
            WalletAddress.user_id == current_user.id,
        )
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cüzdan bulunamadı")
    deleted_chain = wallet.chain
    await db.delete(wallet)
    await log_audit(
        db, request,
        action=AuditAction.WALLET_DELETE,
        user_id=current_user.id,
        resource=f"wallet:{wallet_id}",
        extra={"chain": deleted_chain},
    )
    await db.commit()


@router.get("/export")
async def export_wallets(
    request: Request,
    include_full_address: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """COMP-024 (FAZ H): Wallet export'ta xpub maskelenir (default).

    Default: adres maskeli (`xpub6C...4D4D` formatinda) — Excel sizmasinda
    blockchain bakiye gecmisi acigi onlenir.

    `?include_full_address=true`: Tam adres dahil edilir (kullanici acik
    onay vermis sayilir). Audit log'da `full=true` extra ile isaretlenir;
    KVKK m.12 ihlal halinde forensic icin kim/ne zaman tam xpub indirdi
    izlenebilir.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    result = await db.execute(
        select(WalletAddress).where(WalletAddress.user_id == current_user.id, WalletAddress.is_active.is_(True))
    )
    rows = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Blockchain Cüzdanları"

    # Guvenlik uyari satiri (row 1) — Excel'in en ustunde gorunur
    warning_text = (
        "GUVENLIK UYARISI: Bu dosya kripto cuzdan adreslerinizi icerir. "
        "xpub/extended public key sizmasi blockchain bakiye gecmisinizi acik "
        "yapar. Bu dosyayi e-postayla paylasmayin, bulut deposunda sifresiz "
        "tutmayin. Tam adres icin ?include_full_address=true ile yeniden indirin."
    )
    warning_cell = ws.cell(row=1, column=1, value=warning_text)
    warning_cell.font = Font(bold=True, color="C53030")
    warning_cell.fill = PatternFill("solid", fgColor="FED7D7")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3)

    headers = ["Zincir", "Adres" + ("" if include_full_address else " (maskeli)"), "Etiket"]
    header_fill = PatternFill("solid", fgColor="7C3AED")
    header_font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, w in enumerate(rows, 3):
        ws.cell(row=row_idx, column=1, value=w.chain)
        addr = w.address if include_full_address else _mask_address(w.address)
        ws.cell(row=row_idx, column=2, value=addr)
        ws.cell(row=row_idx, column=3, value=w.label or "")

    for col, width in zip("ABC", [18, 80 if include_full_address else 30, 20]):
        ws.column_dimensions[col].width = width

    # Audit log — tam xpub indirildi mi izle (forensic icin kritik)
    await log_audit(
        db, request,
        action=AuditAction.WALLET_EXPORT,
        user_id=current_user.id,
        resource="wallet:export.xlsx",
        extra={
            "wallet_count": len(rows),
            "include_full_address": include_full_address,
        },
    )
    await db.commit()

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=blockchain-cüzdanları.xlsx"},
    )


@router.post("/import", response_model=list[WalletOut])
async def import_wallets(
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

    parsed: list[dict] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        chain = str(row[0]).strip().lower() if row[0] else ""
        address = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        label = str(row[2]).strip() if len(row) > 2 and row[2] else None

        if not chain or chain == "none" or chain not in VALID_CHAINS:
            continue
        if not address or address == "none":
            continue
        if label == "none":
            label = None

        parsed.append({"chain": chain, "address": address, "label": label})

    if not parsed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Geçerli cüzdan bulunamadı")

    # Mevcut cüzdanları sil, yenilerini ekle
    existing = await db.execute(
        select(WalletAddress).where(WalletAddress.user_id == current_user.id)
    )
    for w in existing.scalars().all():
        await db.delete(w)

    added = []
    for p in parsed:
        w = WalletAddress(
            user_id=current_user.id,
            chain=p["chain"],
            address=p["address"],
            label=p["label"],
        )
        db.add(w)
        added.append(w)

    await db.commit()
    for w in added:
        await db.refresh(w)
    return added


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_wallets(current_user: User = Depends(get_current_user)):
    return {"detail": "Blockchain senkronizasyonu başlatıldı"}
