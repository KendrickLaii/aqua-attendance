import enum
import json
import logging
import uuid
from contextvars import ContextVar
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# (ip_address, user_agent, request_id) of the in-flight HTTP request, set by middleware
# so every log_audit call records them without each router passing `request`.
_request_context: ContextVar[tuple[str | None, str | None, str | None]] = ContextVar(
    "audit_request_context", default=(None, None, None)
)


def set_request_context(request: Request) -> None:
    _request_context.set(
        (
            _extract_client_ip(request),
            (request.headers.get("user-agent") or "")[:1000] or None,
            (request.headers.get("x-request-id") or "")[:100] or None,
        )
    )


class _JSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, enum.Enum):
            return obj.value
        if isinstance(obj, (set, frozenset)):
            return sorted(obj, key=str)
        # An audit entry must never fail the request, so stringify unknown types.
        return str(obj)


def _json_safe(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    # Round-trip through JSON to ensure serializable
    return json.loads(json.dumps(data, cls=_JSONEncoder))


def _build_audit_log(
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
    ctx_ip, ctx_agent, ctx_request_id = _request_context.get()
    ip_address, user_agent = ctx_ip, ctx_agent
    if request is not None:
        ip_address = _extract_client_ip(request)
        user_agent = request.headers.get("user-agent")

    return AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=_json_safe(old_values),
        new_values=_json_safe(new_values),
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id or ctx_request_id,
        batch_operation=batch_operation,
        created_at=datetime.now(timezone.utc),
    )


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
) -> AuditLog | None:
    """Write a single audit log entry. Call this after the primary transaction commits.

    Never raises: the business change is already committed, so a failed audit write
    is logged and swallowed rather than turning a successful request into a 500.
    """
    try:
        log = _build_audit_log(
            user_id=user_id,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
            description=description,
            request=request,
            request_id=request_id,
            batch_operation=batch_operation,
        )
        # SAVEPOINT: a bad insert rolls back only the audit row. A full session
        # rollback would expire the caller's ORM objects and break its response.
        async with db.begin_nested():
            db.add(log)
        await db.commit()
    except Exception:
        logger.exception("Failed to write audit log: %s %s %s", action, table_name, record_id)
        return None

    return log


async def log_audit_many(
    db: AsyncSession,
    entries: list[dict[str, Any]],
) -> list[AuditLog] | None:
    """Batch-write multiple audit rows in one transaction.

    Each entry is a keyword-argument dict accepted by `_build_audit_log`.
    Returns the written logs or None if the batch failed (all-or-nothing).
    """
    try:
        logs = [_build_audit_log(**entry) for entry in entries]
        async with db.begin_nested():
            for log in logs:
                db.add(log)
        await db.commit()
    except Exception:
        logger.exception("Failed to write %s audit logs", len(entries))
        return None

    return logs


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
