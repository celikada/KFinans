from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.models.integration import WalletAddress
from app.models.user import User
from app.schemas.integration import WalletCreate, WalletOut

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.get("", response_model=list[WalletOut])
async def list_wallets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WalletAddress).where(WalletAddress.user_id == current_user.id, WalletAddress.is_active == True)
    )
    return result.scalars().all()


@router.post("", response_model=WalletOut, status_code=status.HTTP_201_CREATED)
async def add_wallet(
    payload: WalletCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wallet = WalletAddress(
        user_id=current_user.id,
        chain=payload.chain,
        address=payload.address,
        label=payload.label,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)
    return wallet


@router.delete("/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wallet(
    wallet_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    result = await db.execute(
        select(WalletAddress).where(
            WalletAddress.id == uuid.UUID(wallet_id),
            WalletAddress.user_id == current_user.id,
        )
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cüzdan bulunamadı")
    await db.delete(wallet)
    await db.commit()


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_wallets(current_user: User = Depends(get_current_user)):
    # TODO: arka planda blockchain sorgusu başlat
    return {"detail": "Blockchain senkronizasyonu başlatıldı"}
