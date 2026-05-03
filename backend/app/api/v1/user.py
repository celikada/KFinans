import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import PasswordChange, ProfileUpdate, UserMeOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/me", response_model=UserMeOut, status_code=status.HTTP_200_OK)
async def get_me(current_user: CurrentUser) -> UserMeOut:
    return UserMeOut.model_validate(current_user)


@router.put("/profile", response_model=UserMeOut, status_code=status.HTTP_200_OK)
async def update_profile(payload: ProfileUpdate, current_user: CurrentUser, db: DB) -> UserMeOut:
    current_user.risk_profile = payload.risk_profile
    await db.commit()
    await db.refresh(current_user)
    logger.info("Risk profili güncellendi: %s → %s", current_user.email, payload.risk_profile)
    return UserMeOut.model_validate(current_user)


@router.put("/password", status_code=status.HTTP_200_OK)
async def change_password(payload: PasswordChange, current_user: CurrentUser, db: DB) -> dict:
    if not verify_password(payload.current_password, current_user.password_hash):
        logger.warning("Yanlış mevcut şifre girişi: %s", current_user.email)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mevcut şifre hatalı")
    current_user.password_hash = hash_password(payload.new_password)
    await db.commit()
    logger.info("Şifre güncellendi: %s", current_user.email)
    return {"detail": "Şifre güncellendi"}


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_me(current_user: CurrentUser, db: DB) -> dict:
    current_user.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()
    logger.info("Hesap silindi (soft-delete): %s", current_user.email)
    return {"detail": "Hesap silindi"}
