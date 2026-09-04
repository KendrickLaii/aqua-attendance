import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EnrollmentStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class CourseEnrollment(Base):
    """Links a student unit to a course SKU they are (or were) enrolled in."""

    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("unit_id", "sku_id", name="uq_course_enrollment_unit_sku"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_skus.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=EnrollmentStatus.active.value)
    enrolled_at: Mapped[date] = mapped_column(Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # One-time purchased session count for per_session (堂費) SKUs. Billed
    # once as a flat charge, not derived from attendance. Ignored for
    # monthly (月費) SKUs.
    purchased_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    unit = relationship("Unit", back_populates="course_enrollments")
    sku = relationship("CourseSku", back_populates="enrollments")
