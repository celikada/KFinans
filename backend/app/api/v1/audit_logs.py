"""Audit log endpoint'i (FAZ C6).

Kullanici sadece **kendi** audit log'larini gorebilir (IDOR korumasi).
Filtre: action prefix (orn. "auth.", "wallet."), tarih araligi, limit.
"""
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit-logs", tags=["audit"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


class AuditLogOut(BaseModel):
    id: UUID
    action: str
    resource: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    extra: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    current_user: CurrentUser,
    db: DB,
    action_prefix: Optional[str] = Query(
        None, description="Filtrelemek icin action prefix (orn. 'auth.', 'wallet.')",
    ),
    limit: int = Query(100, ge=1, le=500),
):
    """Kullanicinin kendi audit log'larini en yeniden eskiye dondurur."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    if action_prefix:
        stmt = stmt.where(AuditLog.action.startswith(action_prefix))
    result = await db.execute(stmt)
    return result.scalars().all()
