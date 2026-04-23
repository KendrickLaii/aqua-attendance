"""
Attendance event model.

Design decision — replay / idempotency:
  We use an **idempotent** approach keyed on the QR token's `jti` (JWT ID).
  Each QR token can be scanned exactly once.  If the same `jti` arrives a
  second time the server returns the original event (HTTP 200) instead of
  creating a duplicate.  This prevents accidental double-scans while keeping
  audit integrity — every row maps 1-to-1 to a verified QR presentation.

  The event_type (check_in / check_out) is derived automatically: the first
  scan of the day is check_in; subsequent scans toggle.  Admins may insert
  manual corrections with event_type = "manual_correction".
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EventType(str, enum.Enum):
    check_in = "check_in"
    check_out = "check_out"
    manual_correction = "manual_correction"


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    qr_jti: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)

    scanner_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    client_device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="attendance_events")
    scanner = relationship("User", foreign_keys=[scanner_user_id])
