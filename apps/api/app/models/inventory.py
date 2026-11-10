import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InventoryWarehouse(Base):
    """A stock-holding site, independent of attendance centres (``locations``)."""

    __tablename__ = "inventory_warehouses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class InventoryBrand(Base):
    """Brand of an item or product, independent of the category tree."""

    __tablename__ = "inventory_brands"

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


class InventoryCategory(Base):
    """Grouping for inventory items, e.g. 教材 / 文具. Two levels: category > sub-category."""

    __tablename__ = "inventory_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
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


class InventoryProduct(Base):
    """SPU: a product grouping N SKUs (``InventoryItem``) that differ by option values."""

    __tablename__ = "inventory_products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_brands.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    skus = relationship("InventoryItem", back_populates="product", order_by="InventoryItem.sku_code")

    @property
    def sku_count(self) -> int:
        return len(self.skus)


class InventoryItem(Base):
    """A sellable/stockable physical item (教材, 文具, …). Stock is tracked per warehouse."""

    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sku_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    cost_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    other_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    sale_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    avg_cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sub_image_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_products.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_brands.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    variant_attrs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    category = relationship("InventoryCategory", back_populates="items")
    product = relationship("InventoryProduct", back_populates="skus")
    stocks = relationship("InventoryStock", back_populates="item")
    movements = relationship("InventoryMovement", back_populates="item")


class InventoryStock(Base):
    """Current on-hand quantity of one item at one warehouse."""

    __tablename__ = "inventory_stocks"
    __table_args__ = (UniqueConstraint("item_id", "warehouse_id", name="uq_inventory_stocks_item_warehouse"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    item = relationship("InventoryItem", back_populates="stocks")
    warehouse = relationship("InventoryWarehouse")

    @property
    def available(self) -> int:
        return self.quantity - self.reserved


class InventoryMovement(Base):
    """Append-only ledger entry. Rows are never updated or deleted;

    the stock quantity is always reproducible from these rows via balance_after.
    """

    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index("ix_inventory_movements_item_wh_created", "item_id", "warehouse_id", "created_at"),
        Index("ix_inventory_movements_effective_date", "effective_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
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
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    item = relationship("InventoryItem", back_populates="movements")
    warehouse = relationship("InventoryWarehouse")


class InventoryStocktake(Base):
    """A stocktake (盤點) session for one warehouse.

    draft → applied (adjust movements written) or cancelled.
    """

    __tablename__ = "inventory_stocktakes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warehouse = relationship("InventoryWarehouse")
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
