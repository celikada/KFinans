from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.core.security import encrypt_secret
from app.models.integration import Integration
from app.models.user import User
from app.schemas.integration import IntegrationCreate, IntegrationOut

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Integration).where(Integration.user_id == current_user.id))
    return result.scalars().all()


@router.post("", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
async def add_integration(
    payload: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.provider == payload.provider,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.encrypted_key = encrypt_secret(payload.api_key)
        existing.encrypted_secret = encrypt_secret(payload.api_secret) if payload.api_secret else None
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    integration = Integration(
        user_id=current_user.id,
        provider=payload.provider,
        encrypted_key=encrypt_secret(payload.api_key),
        encrypted_secret=encrypt_secret(payload.api_secret) if payload.api_secret else None,
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    return integration


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_integration(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.provider == provider,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entegrasyon bulunamadı")
    await db.delete(integration)
    await db.commit()


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_integrations(current_user: User = Depends(get_current_user)):
    # TODO: arka planda senkronizasyon görevi başlat
    return {"detail": "Senkronizasyon başlatıldı"}
