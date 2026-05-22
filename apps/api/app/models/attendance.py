"""
Attendance event model.

Tracks check-in / check-out events for products (staff, students, etc.).

The event_type (check_in / check_out) is derived from the product's current
`attendance_status` — each scan toggles it.  The same QR token can therefore
be re-scanned to perform both check-in and check-out without rotating the
code.  Admins may insert manual corrections with event_type =
"manual_correction".

Replay / double-tap protection is handled in the scan service by a short
debounce window (same product scanned twice within a few seconds returns
the original event).  `qr_jti` is recorded for audit but is no longer
globally unique.
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
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    qr_jti: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    client_device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    product = relationship("Product", foreign_keys=[product_id], back_populates="attendance_events")
    recorded_by = relationship("User", foreign_keys=[recorded_by_user_id])
