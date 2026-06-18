import io
import logging
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.limiter import limiter
from app.core.upload_validation import validate_excel_upload
from app.models.tefas import TefasHolding as TefasHoldingModel
from app.models.user import User
from app.schemas.tefas import TefasHolding, TefasPositionOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio/tefas", tags=["tefas"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/holdings", response_model=list[TefasHolding])
async def get_tefas_holdings(
    current_user: CurrentUser,
    db: DbSession,
):
    result = await db.execute(select(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
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
    current_user: CurrentUser,
    db: DbSession,
):
    await db.execute(delete(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    for h in holdings:
        db.add(
            TefasHoldingModel(
                user_id=current_user.id,
                code=h.code.upper(),
                quantity=h.quantity,
                name=h.name,
                avg_cost_tl=h.avg_cost_tl,
                distributor=h.distributor,
            )
        )
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


def _build_tefas_position(h: TefasHolding, a) -> TefasPositionOut:
    """Bir TEFAS holding + fiyatlanmış asset'ten pozisyon çıktısı üretir.

    Preview endpoint (body-tabanlı) ve compute_tefas_positions (user/DB-tabanlı,
    live cache) ortak kullanır — cost-basis hesabı tek yerde.
    """
    qty = a.liquid_quantity
    total_value_tl = (qty * a.unit_price_tl).quantize(Decimal("0.01"))
    avg_cost_raw = h.avg_cost_tl
    avg_cost_dec = Decimal(str(avg_cost_raw)) if avg_cost_raw is not None else None
    cost_basis, gain_loss, gain_loss_pct = _calc_gain_loss(total_value_tl, qty, avg_cost_raw)
    return TefasPositionOut(
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
    )


async def compute_tefas_positions(user_id, db: AsyncSession) -> list[TefasPositionOut]:
    """Kullanıcının DB'deki TEFAS holding'lerini canlı fiyatlarla pozisyona çevirir.

    Live cache refresh servisi kullanır. Preview endpoint'i (body-tabanlı,
    cost-basis önizleme için) ayrıdır; bu fonksiyon DB kayıtlarını fiyatlar.
    TEFAS fetch zaten Faz 1 timeout + last-known-good cache ile bounded.
    """
    from app.services.tefas import TefasService

    result = await db.execute(select(TefasHoldingModel).where(TefasHoldingModel.user_id == user_id))
    rows = result.scalars().all()
    if not rows:
        return []

    holdings = [
        TefasHolding(
            code=r.code,
            quantity=float(r.quantity),
            name=r.name,
            avg_cost_tl=float(r.avg_cost_tl) if r.avg_cost_tl is not None else None,
            distributor=r.distributor,
        )
        for r in rows
    ]
    svc = TefasService([{"code": h.code, "quantity": h.quantity, "name": h.name} for h in holdings])
    # skip_missing: tek fiyatsız fon (ör. AFO geçici 0 portföy değerli) tüm kartı
    # çökertmesin — fiyatlananlar pozisyon olur, fiyatlanamayan price_available=False.
    assets = await svc.fetch(skip_missing=True)
    asset_by_code = {a.symbol: a for a in assets}
    positions: list[TefasPositionOut] = []
    for h in holdings:
        asset = asset_by_code.get(h.code.upper())
        if asset is not None:
            positions.append(_build_tefas_position(h, asset))
        else:
            positions.append(_build_unpriced_tefas_position(h))
    return positions


def _build_unpriced_tefas_position(h: TefasHolding) -> TefasPositionOut:
    """TEFAS'ta o an fiyatlanamayan fon için 0-değerli pozisyon (price_available=False).

    Holding listede görünür (kullanıcı sahip olduğunu görür) ama toplam'ı etkilemez."""
    return TefasPositionOut(
        code=h.code.upper(),
        name=h.name or h.code.upper(),
        quantity=Decimal(str(h.quantity)),
        unit_price_tl=Decimal("0"),
        total_value_tl=Decimal("0"),
        avg_cost_tl=Decimal(str(h.avg_cost_tl)) if h.avg_cost_tl is not None else None,
        distributor=h.distributor,
        price_available=False,
    )


@router.post("/preview", response_model=list[TefasPositionOut])
@limiter.limit("30/minute")
async def tefas_preview(
    request: Request,
    holdings: list[TefasHolding],
    _: Annotated[User, Depends(get_current_user)],
):
    from app.services.tefas import TefasService

    svc = TefasService([{"code": h.code, "quantity": h.quantity, "name": h.name} for h in holdings])
    try:
        assets = await svc.fetch()
    except ValueError as e:
        # SEC-007 (FAZ H): TefasService ValueError yalnizca "TEFAS'ta fon bulunamadı: <code>"
        # mesaji icin raise edilir (services/tefas.py:56). User input echo'su — guvenli.
        # Yeni leak kaynagi olusursa burada da sanitize gerekir.
        logger.info("TEFAS validation failed: %s", e)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # Koda göre eşleştir (sıra varsayımına güvenme — fetch davranışı değişse bile
    # yanlış fon-miktar eşleşmesi olmaz). skip_missing=False olduğundan tüm holding'ler
    # fiyatlı; yine de defansif map.
    asset_by_code = {a.symbol: a for a in assets}
    return [_build_tefas_position(h, asset_by_code[h.code.upper()]) for h in holdings]


async def _fetch_tefas_prices(rows) -> dict[str, Decimal]:
    """Holding'ler için canlı TEFAS fiyatlarını çeker; hata olursa boş dict."""
    if not rows:
        return {}
    from app.services.tefas import TefasService

    try:
        svc = TefasService([{"code": r.code, "quantity": float(r.quantity), "name": r.name} for r in rows])
        assets = await svc.fetch()
        return {a.symbol: a.unit_price_tl for a in assets}
    except Exception:
        logger.warning("TEFAS export: canlı fiyat alınamadı")
        return {}


def _write_tefas_export_row(ws, row_idx: int, holding, prices: dict[str, Decimal]) -> None:
    """Tek bir holding satırını export worksheet'ine yazar."""
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


@router.get("/export")
async def export_tefas_holdings(
    current_user: CurrentUser,
    db: DbSession,
):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    result = await db.execute(select(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    rows = result.scalars().all()

    prices = await _fetch_tefas_prices(rows)

    wb = Workbook()
    ws = wb.active
    ws.title = "TEFAS Holdingleri"
    headers = [
        "Fon Kodu",
        "Adet",
        "İsim",
        "Birim Fiyat (₺)",
        "Toplam Değer (₺)",
        "Ort. Maliyet (₺)",
        "Kâr/Zarar (₺)",
        "Kurum",
    ]
    header_fill = PatternFill("solid", fgColor="1D4ED8")
    header_font = Font(bold=True, color="FFFFFF")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, holding in enumerate(rows, 2):
        _write_tefas_export_row(ws, row_idx, holding, prices)

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


def _find_mkk_header_row(sh) -> int:
    """MKK sheet'inde 'Üye' başlık satırını bulur; yoksa 422 fırlatır."""
    for r in range(min(sh.nrows, 20)):
        first = str(sh.cell_value(r, 0)).strip()
        if first.lower() == "üye":
            return r
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="MKK formatı tanınmadı: 'Üye' başlık satırı bulunamadı",
    )


def _parse_mkk_fund_row(sh, r: int) -> TefasHolding | None:
    """MKK satırından TEFAS fon kaydı üretir; fon değilse/geçersizse None."""
    kind = str(sh.cell_value(r, 2)).strip()
    if kind.lower() != "fon":
        return None
    code_raw = sh.cell_value(r, 3)
    code = str(code_raw).strip().upper() if code_raw else ""
    if not code:
        return None
    name_raw = sh.cell_value(r, 4)
    name = str(name_raw).strip() if name_raw else ""
    try:
        qty = float(sh.cell_value(r, 7))
        price = float(sh.cell_value(r, 8))
    except (TypeError, ValueError):
        return None
    if qty <= 0:
        return None
    member = str(sh.cell_value(r, 0)).strip() or None
    if member:
        member = member[:50]
    return TefasHolding(
        code=code,
        quantity=qty,
        name=name,
        avg_cost_tl=price if price > 0 else None,
        distributor=member,
    )


@router.post("/import-mkk", response_model=list[TefasHolding])
async def import_tefas_mkk(
    file: Annotated[UploadFile, File()],
    current_user: CurrentUser,
    db: DbSession,
):
    """MKK e-Yatırımcı 'Tüm Kıymetler' raporundan TEFAS fonlarını içe aktarır.

    Beklenen format (.xls binary, xlrd 1.2.0):
      Header satırı: Üye, Hesap, Kıymet Sınıfı, Menkul Kıymet Kodu, Kıymet Adı,
                     Ek Tanım, Alt Hesap, Adet, Fiyat (TL), ...
      Sadece "Kıymet Sınıfı = Fon" satırları işlenir.
    """
    import xlrd

    # SEC-009 (FAZ H): magic-byte + boyut + extension dogrulamasi
    content = await validate_excel_upload(file)
    try:
        wb = xlrd.open_workbook(file_contents=content)
        sh = wb.sheet_by_index(0)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MKK Excel dosyası okunamadı (.xls binary formatında olmalı)",
        ) from exc

    header_row = _find_mkk_header_row(sh)

    parsed: list[TefasHolding] = []
    for r in range(header_row + 1, sh.nrows):
        holding = _parse_mkk_fund_row(sh, r)
        if holding is not None:
            parsed.append(holding)

    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dosyada 'Fon' kıymet sınıfında geçerli kayıt bulunamadı",
        )

    await db.execute(delete(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    for h in parsed:
        db.add(
            TefasHoldingModel(
                user_id=current_user.id,
                code=h.code,
                quantity=h.quantity,
                name=h.name,
                avg_cost_tl=h.avg_cost_tl,
                distributor=h.distributor,
            )
        )
    await db.commit()

    # Snapshot tetikle ki Finansal Hedef + History güncel kalsın
    try:
        from app.services.snapshot import compute_and_save_snapshot

        await compute_and_save_snapshot(current_user.id, db)
    except Exception as exc:
        logger.warning("MKK TEFAS import sonrası snapshot alınamadı: %s", exc)

    return parsed


def _parse_avg_cost(avg_cost_raw) -> float | None:
    """Ortalama maliyeti float'a çevirir; geçersiz veya <=0 ise None."""
    if avg_cost_raw is None:
        return None
    try:
        avg_cost_tl = float(avg_cost_raw)
    except (TypeError, ValueError):
        return None
    return avg_cost_tl if avg_cost_tl > 0 else None


def _parse_tefas_import_row(row: tuple) -> TefasHolding | None:
    """Export-template Excel satırından TEFAS holding üretir; geçersizse None."""
    code = str(row[0]).strip().upper() if row[0] else ""
    if not code or code == "NONE":
        return None
    try:
        qty = float(row[1])
    except (TypeError, ValueError):
        return None
    if qty <= 0:
        return None

    name = str(row[2]).strip() if len(row) > 2 and row[2] else ""
    avg_cost_raw = row[3] if len(row) > 3 else None
    # Export sırası: Adet(B), İsim(C), Birim(D), Toplam(E), Ort.Maliyet(F), Kâr/Zarar(G), Kurum(H)
    # Import sırası: aynı template + son sütun Kurum (H, index 7)
    distributor_raw = row[7] if len(row) > 7 else None
    distributor = str(distributor_raw).strip()[:50] or None if distributor_raw else None

    return TefasHolding(
        code=code,
        quantity=qty,
        name=name,
        avg_cost_tl=_parse_avg_cost(avg_cost_raw),
        distributor=distributor,
    )


@router.post("/import", response_model=list[TefasHolding])
async def import_tefas_holdings(
    file: Annotated[UploadFile, File()],
    current_user: CurrentUser,
    db: DbSession,
):
    from openpyxl import load_workbook

    # SEC-009 (FAZ H): magic-byte + boyut + extension dogrulamasi
    content = await validate_excel_upload(file)
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dosya okunamadı") from exc

    parsed: list[TefasHolding] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        holding = _parse_tefas_import_row(row)
        if holding is not None:
            parsed.append(holding)

    if not parsed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Geçerli holding bulunamadı")

    await db.execute(delete(TefasHoldingModel).where(TefasHoldingModel.user_id == current_user.id))
    for h in parsed:
        db.add(
            TefasHoldingModel(
                user_id=current_user.id,
                code=h.code,
                quantity=h.quantity,
                name=h.name,
                avg_cost_tl=h.avg_cost_tl,
            )
        )
    await db.commit()
    return parsed
