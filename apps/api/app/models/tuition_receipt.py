import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, JSON, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TuitionReceiptStatus(str, enum.Enum):
    posted = "posted"
    void = "void"


class TuitionReceipt(Base):
    """One recorded payment that can settle one or more issued invoices."""

    __tablename__ = "tuition_receipts"
    __table_args__ = (
        UniqueConstraint("location_id", "receipt_no", name="uq_tuition_receipts_location_receipt_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paid_by: Mapped[str] = mapped_column(String(100), nullable=False)
    receipt_no: Mapped[str] = mapped_column(String(50), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TuitionReceiptStatus.posted.value)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjustments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    primary_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    location = relationship("Location")
    unit = relationship("Unit")
    invoices = relationship(
        "TuitionReceiptInvoice",
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="TuitionReceiptInvoice.created_at",
    )


class TuitionReceiptInvoice(Base):
    """Which invoice a posted receipt fully settles."""

    __tablename__ = "tuition_receipt_invoices"
    __table_args__ = (
        Index(
            "uq_tuition_receipt_invoices_posted_invoice",
            "invoice_id",
            unique=True,
            postgresql_where=text("is_posted"),
            sqlite_where=text("is_posted"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tuition_receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tuition_invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_posted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    receipt = relationship("TuitionReceipt", back_populates="invoices")
    invoice = relationship("TuitionInvoice")
