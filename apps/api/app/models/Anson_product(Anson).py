import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Table, Text, Uuid, Column, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

#SPU > SKU
class Product(Base):
    """A managed entity (staff member, student, etc.) that can check in/out."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    spu_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True) #AQUA-C8123

    product_name: Mapped[str] = mapped_column(String(255), nullable=False) #default name 
    
    other_names: Mapped[list[str]] = mapped_column(JSON, nullable=True) #other names, became JSON {"en": "Text book", "zh": "中文"}

    product_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) #can change to ENUM

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ProductStatus.active.value)

    photo_url: Mapped[list[str]] = mapped_column(JSON, nullable=True) #["x64base64string","x64base64string2"], store an array, max_size

    enrollment_date: Mapped[date | None] = mapped_column(Date, nullable=True) #on shelf

    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True) #off shelf

    sku: Mapped[list[str]] = mapped_column(JSON, nullable=True)

    #[
    #-------------slice 1----------------
    # {"sku_code": "AQUA-C8123-001"
    # "sku_name": "Text book RED",
    # "sku_other_names": ["Text book RED", "Text book RED"],
    # "sku_photo_url": ["x64base64string","x64base64string2"],
    # "sku_type": "textbook",
    #"sku_price": 200,
    #},
    #-------------slice 2----------------
    # {"sku_code": "AQUA-C8123-002"
    # "sku_name": "Text book BLUE",
    # "sku_other_names": ["Text book RED", "Text book RED"],
    # "sku_photo_url": ["x64base64string","x64base64string2"],
    # "sku_type": "textbook",
    #"sku_price": 50,
    #},
    #]

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Polymorphic relationships to profile tables
    student_profile = relationship(
        "StudentProfile",
        back_populates="product",
        cascade="all, delete-orphan",
        uselist=False,
    )
    staff_profile = relationship(
        "StaffProfile",
        back_populates="product",
        cascade="all, delete-orphan",
        uselist=False,
        foreign_keys="StaffProfile.id",
    )
    
    # Additional relationships
    notifications = relationship("Notification", back_populates="product", cascade="all, delete-orphan")
    attendance_summaries = relationship("AttendanceSummary", back_populates="product", cascade="all, delete-orphan")
    payroll_records = relationship("PayrollRecord", back_populates="product", cascade="all, delete-orphan")
