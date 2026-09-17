import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid
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
    # Session counts for per_session (堂費) SKUs live on EnrollmentPurchase —
    # the enrollment itself stores no quantity, so there is one source of
    # truth for what was bought and what has been billed.
    # Per-student price override (e.g. 私補 variable pricing). When set,
    # billing uses this instead of the SKU price — lets price-less classes
    # still be billed.
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    unit = relationship("Unit", back_populates="course_enrollments")
    sku = relationship("CourseSku", back_populates="enrollments")
    purchases = relationship(
        "EnrollmentPurchase",
        back_populates="enrollment",
        order_by="EnrollmentPurchase.purchased_at",
        cascade="all, delete-orphan",
    )


class EnrollmentPurchase(Base):
    """A single purchase / top-up for a per_session enrollment."""

    __tablename__ = "enrollment_purchases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_enrollments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purchased_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL = price decided at invoice time (私補: enroll sessions first, set
    # the price on the manual invoice line that bills this purchase).
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    purchased_at: Mapped[date] = mapped_column(Date, nullable=False)
    billed_invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tuition_invoice_lines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    enrollment = relationship("CourseEnrollment", back_populates="purchases")
    billed_invoice_line = relationship("TuitionInvoiceLine")
