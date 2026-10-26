from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MovementType = Literal["in", "out", "adjust"]
MovementTypeOut = Literal["in", "out", "adjust", "transfer_in", "transfer_out"]

InReasonCode = Literal["opening", "sales_return", "other"]
OutReasonCode = Literal[
    "damage", "loss", "gift", "sample", "internal_use", "supplier_return", "sale", "other"
]

StocktakeStatus = Literal["draft", "applied", "cancelled"]


class InventoryCategoryCreate(BaseModel):
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class InventoryCategoryUpdate(BaseModel):
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class InventoryCategoryOut(BaseModel):
    id: uuid.UUID
    name_zh: str
    name_en: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryItemCreate(BaseModel):
    sku_code: str = Field(min_length=1, max_length=100)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None
    unit_of_measure: str | None = Field(default=None, max_length=50)
    cost_price: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    reorder_level: int = Field(default=0, ge=0)
    is_active: bool = True
    image_url: str | None = Field(default=None, max_length=500)


class InventoryItemUpdate(BaseModel):
    sku_code: str | None = Field(default=None, min_length=1, max_length=100)
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None
    unit_of_measure: str | None = Field(default=None, max_length=50)
    cost_price: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    reorder_level: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    image_url: str | None = Field(default=None, max_length=500)


class InventoryItemOut(BaseModel):
    id: uuid.UUID
    sku_code: str
    name_zh: str
    name_en: str | None = None
    category_id: uuid.UUID | None = None
    unit_of_measure: str | None = None
    cost_price: float | None = None
    sale_price: float | None = None
    reorder_level: int
    avg_cost: float
    is_active: bool
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryStockOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    location_id: uuid.UUID
    quantity: int
    reserved: int
    available: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryMovementCreate(BaseModel):
    item_id: uuid.UUID
    location_id: uuid.UUID
    type: MovementType
    quantity: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=500)
    reason_code: str | None = Field(default=None, max_length=30)
    reference: str | None = Field(default=None, max_length=255)


class InventoryMovementOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    location_id: uuid.UUID
    type: MovementTypeOut
    quantity_delta: int
    balance_after: int
    reason: str | None = None
    reason_code: str | None = None
    unit_cost: float | None = None
    reference: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryTransferCreate(BaseModel):
    item_id: uuid.UUID
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    quantity: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)


class InventoryTransferOut(BaseModel):
    transfer_id: uuid.UUID
    out_movement: InventoryMovementOut
    in_movement: InventoryMovementOut


class InventoryReserveBody(BaseModel):
    item_id: uuid.UUID
    location_id: uuid.UUID
    quantity: int = Field(gt=0)


class InventoryStocktakeCreate(BaseModel):
    location_id: uuid.UUID
    item_ids: list[uuid.UUID] | None = None
    note: str | None = Field(default=None, max_length=500)


class InventoryStocktakeLineUpdate(BaseModel):
    item_id: uuid.UUID
    counted_qty: int | None = Field(default=None, ge=0)


class InventoryStocktakeLinesPatch(BaseModel):
    lines: list[InventoryStocktakeLineUpdate]


class InventoryStocktakeLineOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    system_qty: int
    counted_qty: int | None = None

    model_config = {"from_attributes": True}


class InventoryStocktakeOut(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    status: StocktakeStatus
    note: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    applied_at: datetime | None = None

    model_config = {"from_attributes": True}


class InventoryStocktakeDetailOut(InventoryStocktakeOut):
    lines: list[InventoryStocktakeLineOut]


class InventoryImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict] = Field(default_factory=list)
