import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    location_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    business_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    main_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detail_photos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    attendance_events = relationship("AttendanceEvent", back_populates="location_ref")
    registered_products = relationship(
        "Product",
        foreign_keys="Product.registered_location_id",
        back_populates="registered_location",
    )
    last_event_products = relationship(
        "Product",
        foreign_keys="Product.last_event_location_id",
        back_populates="last_event_location_ref",
    )
    attendance_summaries = relationship("AttendanceSummary", back_populates="location", cascade="all, delete-orphan")
