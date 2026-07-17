import enum
import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid
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
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "payroll_period_start",
            "payroll_period_end",
            name="uq_payroll_records_product_period",
        ),
    )

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

    # Slot snapshot (1 slot = 15 min = 0.25h) — source of truth from summaries
    regular_slots: Mapped[int] = mapped_column(Integer, default=0)
    ot_slots: Mapped[int] = mapped_column(Integer, default=0)

    # Pay-rate snapshots (frozen at generation time to prevent historical drift)
    hourly_rate_snapshot: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    ot_multiplier_snapshot: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)

    # Compensation calculations
    base_salary: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    overtime_pay: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    holiday_pay: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    allowance: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    deduction: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    bonus: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    # Manual adjustments
    adjustment_1: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    adjustment_2: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    adjustment_1_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjustment_2_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    
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
