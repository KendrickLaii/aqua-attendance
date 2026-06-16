import enum
import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


class PayrollStatus(str, enum.Enum):
    draft = "draft"
    calculated = "calculated"
    approved = "approved"
    paid = "paid"
    cancelled = "cancelled"


class PayrollRecord(Base):
    """Payroll calculation records for individual products."""
    
    __tablename__ = "payroll_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    
    # Primary keys
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    payroll_period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    payroll_period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Work hours summary
    total_regular_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    total_overtime_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    total_holiday_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    total_work_days: Mapped[int] = mapped_column(default=0)
    total_leave_days: Mapped[int] = mapped_column(default=0)
    
    # Compensation calculations
    base_salary: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    overtime_pay: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    holiday_pay: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    allowance: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    deduction: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    bonus: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    
    # Totals
    gross_pay: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    net_pay: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    
    # Status and metadata
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PayrollStatus.draft.value)
    calculation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    approval_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Notes and references
    payroll_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculation_method: Mapped[str] = mapped_column(String(50), default="standard")
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    
    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="payroll_records")
    approved_by: Mapped["User"] = relationship("User", foreign_keys=[approved_by_user_id])
