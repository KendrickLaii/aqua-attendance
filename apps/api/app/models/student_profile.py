import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


class StudentProfile(Base):
    """Student-specific profile data linked to a product."""
    
    __tablename__ = "student_profiles"

    id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    
    # Academic information
    school_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    student_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    
    # Guardian information (structured JSON)
    guardians: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Academic dates
    enrollment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    graduation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Notes
    academic_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationship back to product
    product: Mapped["Product"] = relationship("Product", back_populates="student_profile")
