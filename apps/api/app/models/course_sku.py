import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CourseSku(Base):
    """A concrete, enrollable class offering (SKU — Stock Keeping Unit).

    Belongs to one CourseSpu (subject). Carries the variable attributes a
    student actually picks: level, schedule, location, capacity, price,
    and billing_unit (monthly 月費 or per_session 堂費).
    """

    __tablename__ = "course_skus"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    spu_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_spus.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schedule_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    billing_unit: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly", server_default="monthly"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    spu = relationship("CourseSpu", back_populates="skus")
    location = relationship("Location")
    enrollments = relationship("CourseEnrollment", back_populates="sku")
