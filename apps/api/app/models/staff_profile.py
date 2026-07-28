import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.unit import Unit


class StaffProfile(Base):
    """Staff-specific profile data linked to a unit."""

    __tablename__ = "staff_profiles"

    id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)

    # Employment information
    employee_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    employment_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Compensation (basic info, details in separate payroll system)
    salary_grade: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Pay rates for slot-based payroll (1 slot = 15 min = 0.25h)
    pay_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # hourly / monthly
    hourly_rate: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    monthly_salary: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    ot_multiplier: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True, default=1.5)

    # Work information
    work_schedule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id"), nullable=True)

    # Notes
    employment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    unit: Mapped["Unit"] = relationship(
        "Unit", back_populates="staff_profile", foreign_keys=[id]
    )
    supervisor: Mapped["Unit"] = relationship("Unit", foreign_keys=[supervisor_id])
