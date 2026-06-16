import uuid
from datetime import date, datetime

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import DB, SuperAdminOnly
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


def _log_to_out(log: AuditLog) -> AuditLogOut:
    out = AuditLogOut.model_validate(log)
    if log.user:
        out.username = log.user.username
        out.user_full_name = log.user.full_name
    return out


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    _admin: SuperAdminOnly,
    db: DB,
    response: Response,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    table_name: str | None = None,
    record_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AuditLogOut]:
    """Query audit logs. Superadmin only."""
    q = select(AuditLog).options(selectinload(AuditLog.user))
    count_q = select(func.count()).select_from(AuditLog)

    clauses = []
    if user_id:
        clauses.append(AuditLog.user_id == user_id)
    if action:
        clauses.append(AuditLog.action == action)
    if table_name:
        clauses.append(AuditLog.table_name == table_name)
    if record_id:
        clauses.append(AuditLog.record_id == record_id)
    if date_from:
        clauses.append(AuditLog.created_at >= date_from)
    if date_to:
        clauses.append(AuditLog.created_at <= date_to)

    if clauses:
        q = q.where(*clauses)
        count_q = count_q.where(*clauses)

    total = (await db.execute(count_q)).scalar_one()
    q = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [_log_to_out(log) for log in result.scalars().all()]
