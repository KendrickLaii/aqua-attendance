import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AttendanceStatus(str, enum.Enum):
    """Current presence of a product (separate from account status)."""

    checked_in = "checked_in"
    checked_out = "checked_out"


class Product(Base):
    """A managed entity (staff member, student, etc.) that can check in/out."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    english_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    attendance_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AttendanceStatus.checked_out.value
    )
    qr_token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    school_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    guardian1_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian1_relationship: Mapped[str | None] = mapped_column(String(100), nullable=True)
    guardian1_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardian2_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian2_relationship: Mapped[str | None] = mapped_column(String(100), nullable=True)
    guardian2_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    attendance_events = relationship("AttendanceEvent", back_populates="product", lazy="selectin")
