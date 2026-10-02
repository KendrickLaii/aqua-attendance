import enum
import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ShiftRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class ShiftRequest(Base):
    """A staff-submitted shift that is not on the official schedule until approved."""

    __tablename__ = "shift_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("shift_templates.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ShiftRequestStatus.pending.value, index=True)
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
