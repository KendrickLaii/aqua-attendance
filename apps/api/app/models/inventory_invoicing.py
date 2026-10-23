import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InventoryInvoice(Base):
    __tablename__ = "inventory_invoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_no: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    so_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    buyer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    so = relationship("SalesOrder")
    customer = relationship("Customer")
    location = relationship("Location")
    lines = relationship("InventoryInvoiceLine", back_populates="invoice", cascade="all, delete-orphan")


class InventoryInvoiceLine(Base):
    __tablename__ = "inventory_invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    so_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_order_lines.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sku_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    credited_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    delivered_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    invoice = relationship("InventoryInvoice", back_populates="lines")
    so_line = relationship("SalesOrderLine")
    item = relationship("InventoryItem")


class InventoryReceipt(Base):
    __tablename__ = "inventory_receipts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    receipt_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_by: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="posted", server_default="posted"
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    invoice = relationship("InventoryInvoice")
    customer = relationship("Customer")
    location = relationship("Location")


class InventoryCreditNote(Base):
    __tablename__ = "inventory_credit_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scn_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    credit_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    invoice = relationship("InventoryInvoice")
    customer = relationship("Customer")
    location = relationship("Location")
    lines = relationship("InventoryCreditNoteLine", back_populates="scn", cascade="all, delete-orphan")


class InventoryCreditNoteLine(Base):
    __tablename__ = "inventory_credit_note_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scn_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_credit_notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_invoice_lines.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    restock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())

    scn = relationship("InventoryCreditNote", back_populates="lines")
    invoice_line = relationship("InventoryInvoiceLine")
    item = relationship("InventoryItem")
