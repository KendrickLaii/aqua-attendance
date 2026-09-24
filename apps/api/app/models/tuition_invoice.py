import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TuitionInvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    paid = "paid"
    void = "void"


class TuitionInvoice(Base):
    """One student tuition bill for a calendar month."""

    __tablename__ = "tuition_invoices"
    __table_args__ = (
        # One invoice per student per billing period — for generated tuition
        # invoices only. Manual invoices set period_start == period_end ==
        # issue date, so they must be exempt or a student could never get two
        # manual invoices on the same day (e.g. re-bill after a void).
        Index(
            "uq_tuition_invoices_unit_period",
            "unit_id",
            "period_start",
            "period_end",
            unique=True,
            postgresql_where=text("kind = 'tuition'"),
            sqlite_where=text("kind = 'tuition'"),
        ),
        UniqueConstraint("location_id", "invoice_no", name="uq_tuition_invoices_location_invoice_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), nullable=True, index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TuitionInvoiceStatus.draft.value)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="tuition")
    manual_student_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Invoice-level 開單人 — the staff/teacher who opened the invoice, for
    # commission records. Lines keep their own class-teacher snapshot.
    staff_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payable_to_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    unit = relationship("Unit", back_populates="tuition_invoices")
    location = relationship("Location")
    lines = relationship(
        "TuitionInvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="TuitionInvoiceLine.created_at",
    )


class TuitionInvoiceLine(Base):
    """Frozen class fee line on a tuition invoice."""

    __tablename__ = "tuition_invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tuition_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("course_enrollments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("course_skus.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sku_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=1)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    month_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Teacher snapshot — copied from the SKU's staff at line creation so
    # old invoices keep the name even if the class's teacher changes.
    staff_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    invoice = relationship("TuitionInvoice", back_populates="lines")
    sku = relationship("CourseSku")
