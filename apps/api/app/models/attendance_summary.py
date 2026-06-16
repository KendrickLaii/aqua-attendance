import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.location import Location


class AttendanceSummary(Base):
    """Pre-calculated daily attendance summaries for reporting and payroll."""
    
    __tablename__ = "attendance_summaries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    
    # Primary keys
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Attendance data
    first_check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_work_minutes: Mapped[int] = mapped_column(Integer, default=0)  # Regular work hours
    total_overtime_minutes: Mapped[int] = mapped_column(Integer, default=0)  # OT hours
    total_break_minutes: Mapped[int] = mapped_column(Integer, default=0)  # Break/lunch time
    
    # Status flags
    is_complete: Mapped[bool] = mapped_column(default=False)  # Has complete check-in/out cycle
    is_holiday: Mapped[bool] = mapped_column(default=False)
    is_weekend: Mapped[bool] = mapped_column(default=False)
    
    # Payroll calculations
    regular_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=0)  # Hours for regular pay
    overtime_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=0)  # Hours for OT pay
    holiday_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=0)  # Holiday hours
    
    # Notes and metadata
    attendance_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    calculation_method: Mapped[str] = mapped_column(String(50), default="standard")  # Calculation method used
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    
    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="attendance_summaries")
    location: Mapped["Location"] = relationship("Location", back_populates="attendance_summaries")
