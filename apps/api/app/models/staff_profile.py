import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


class StaffProfile(Base):
    """Staff-specific profile data linked to a product."""
    
    __tablename__ = "staff_profiles"

    id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    
    # Employment information
    employee_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Employment dates
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Compensation (basic info, details in separate payroll system)
    salary_grade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Work information
    work_schedule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    
    # Notes
    employment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="staff_profile")
    supervisor: Mapped["Product"] = relationship("Product", foreign_keys=[supervisor_id])
