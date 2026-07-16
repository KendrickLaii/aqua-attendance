import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON

from app.database import Base

product_scan_locations = Table(
    "product_scan_locations",
    Base.metadata,
    Column("product_id", Uuid, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("location_id", Uuid, ForeignKey("locations.id", ondelete="RESTRICT"), primary_key=True),
)


class AttendanceStatus(str, enum.Enum):
    """Current presence of a product (separate from account status)."""

    checked_in = "checked_in"
    checked_out = "checked_out"


class EmploymentType(str, enum.Enum):
    part_time = "part_time"
    full_time = "full_time"


class ProductStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    graduated = "graduated"
    terminated = "terminated"
    suspended = "suspended"


if TYPE_CHECKING:
    from app.models.product import Product


class Student(Base):
    """Student-specific profile data linked to a product."""
    
    __tablename__ = "student"

    id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
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

    attendance_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AttendanceStatus.checked_out.value
    )

    qr_token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    registered_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("locations.id"), nullable=True, index=True
    )
    last_event_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attendance_events = relationship("AttendanceEvent", back_populates="product", lazy="select")
    registered_location = relationship(
        "Location", foreign_keys=[registered_location_id], back_populates="registered_products"
    )
    scan_locations = relationship(
        "Location",
        secondary=product_scan_locations,
        lazy="selectin",
    )
    last_event_location_ref = relationship(
        "Location",
        foreign_keys=[last_event_location_id],
        back_populates="last_event_products",
    )


    