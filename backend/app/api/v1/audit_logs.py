"""Audit log endpoint'i (FAZ C6 + PERF-001 pagination).

Kullanici sadece **kendi** audit log'larini gorebilir (IDOR korumasi).
Filtre: action prefix (orn. "auth.", "wallet.").
"""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.pagination import PaginatedResponse

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


@router.get("", response_model=PaginatedResponse[AuditLogOut])
async def list_audit_logs(
    current_user: CurrentUser,
    db: DB,
    action_prefix: Optional[str] = Query(
        None,
        description="Filtrelemek icin action prefix (orn. 'auth.', 'wallet.')",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """PERF-001 (FAZ H): Pagination eklendi — buyuk veri'de yavaslamasin.

    Onceki davranis (limit=100, list) -> yeni PaginatedResponse[T] format
    (items + total_count + has_next + limit + offset). Geriye uyumsuz —
    frontend yeni format'a guncellenmeli (henuz audit_logs frontend yok).

    audit_logs.created_at index sayesinde COUNT + OFFSET/LIMIT hizli.
    365 gunluk retention (COMP-022) sayesinde ust sinir 365K civari kalir.
    """
    base = select(AuditLog).where(AuditLog.user_id == current_user.id)
    if action_prefix:
        base = base.where(AuditLog.action.startswith(action_prefix))

    # Total count (filtrelere uyan tum kayitlar — offset/limit oncesi)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Sayfalanmis satirlar (en yeniden eskiye)
    items_stmt = base.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
    items = (await db.execute(items_stmt)).scalars().all()

    return PaginatedResponse[AuditLogOut](
        items=[AuditLogOut.model_validate(i) for i in items],
        total_count=total,
        limit=limit,
        offset=offset,
        has_next=(offset + len(items)) < total,
    )
