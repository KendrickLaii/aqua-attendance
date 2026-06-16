import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class _JSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _json_safe(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    # Round-trip through JSON to ensure serializable
    return json.loads(json.dumps(data, cls=_JSONEncoder))


async def log_audit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    table_name: str,
    record_id: uuid.UUID | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    description: str | None = None,
    request: Request | None = None,
    request_id: str | None = None,
    batch_operation: bool = False,
) -> AuditLog:
    """Write an audit log entry. Call this after the primary transaction commits."""
    ip_address = None
    user_agent = None
    if request is not None:
        ip_address = _extract_client_ip(request)
        user_agent = request.headers.get("user-agent")

    log = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=_json_safe(old_values),
        new_values=_json_safe(new_values),
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        batch_operation=batch_operation,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()
    return log


def _extract_client_ip(request: Request) -> str | None:
    """Best-effort client IP extraction from headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return None
