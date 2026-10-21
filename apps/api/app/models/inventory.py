import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InventoryCategory(Base):
    """Grouping for inventory items, e.g. 教材 / 文具."""

    __tablename__ = "inventory_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    items = relationship("InventoryItem", back_populates="category")


class InventoryItem(Base):
    """A sellable/stockable physical item (教材, 文具, …). Stock is tracked per location."""

    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sku_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    sale_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    avg_cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    category = relationship("InventoryCategory", back_populates="items")
    stocks = relationship("InventoryStock", back_populates="item")
    movements = relationship("InventoryMovement", back_populates="item")


class InventoryStock(Base):
    """Current on-hand quantity of one item at one location."""

    __tablename__ = "inventory_stocks"
    __table_args__ = (UniqueConstraint("item_id", "location_id", name="uq_inventory_stocks_item_location"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    item = relationship("InventoryItem", back_populates="stocks")
    location = relationship("Location")

    @property
    def available(self) -> int:
        return self.quantity - self.reserved


class InventoryMovement(Base):
    """Append-only ledger entry. Rows are never updated or deleted;

    the stock quantity is always reproducible from these rows via balance_after.
    """

    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index("ix_inventory_movements_item_loc_created", "item_id", "location_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    item = relationship("InventoryItem", back_populates="movements")
    location = relationship("Location")


class InventoryStocktake(Base):
    """A stocktake (盤點) session for one location.

    draft → applied (adjust movements written) or cancelled.
    """

    __tablename__ = "inventory_stocktakes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    location = relationship("Location")
    lines = relationship("InventoryStocktakeLine", back_populates="stocktake", cascade="all, delete-orphan")


class InventoryStocktakeLine(Base):
    """One counted item within a stocktake; system_qty is the snapshot at creation."""

    __tablename__ = "inventory_stocktake_lines"
    __table_args__ = (UniqueConstraint("stocktake_id", "item_id", name="uq_stocktake_lines_take_item"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stocktake_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_stocktakes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    system_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stocktake = relationship("InventoryStocktake", back_populates="lines")
    item = relationship("InventoryItem")
