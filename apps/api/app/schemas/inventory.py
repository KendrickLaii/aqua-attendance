from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MovementType = Literal["in", "out", "adjust"]
MovementTypeOut = Literal["in", "out", "adjust", "transfer_in", "transfer_out"]

InReasonCode = Literal["opening", "sales_return", "other"]
OutReasonCode = Literal[
    "damage", "loss", "gift", "sample", "internal_use", "supplier_return", "sale", "other"
]

StocktakeStatus = Literal["draft", "applied", "cancelled"]


def _required_text(value: str) -> str:
    if not isinstance(value, str):
        return value
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


def _optional_text(value: str | None) -> str | None:
    if value is None or not isinstance(value, str):
        return value
    return value.strip() or None


class InventoryWarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=50)
    location_id: uuid.UUID | None = None
    is_active: bool = True

    @field_validator("code", "name_zh", mode="before")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("name_en", "address", "phone", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)


class InventoryWarehouseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=50)
    location_id: uuid.UUID | None = None
    is_active: bool | None = None

    @field_validator("code", "name_zh", mode="before")
    @classmethod
    def _strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _required_text(value)

    @field_validator("name_en", "address", "phone", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)


class InventoryWarehouseOut(BaseModel):
    id: uuid.UUID
    code: str
    name_zh: str
    name_en: str | None = None
    address: str | None = None
    phone: str | None = None
    location_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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


def _clean_sub_image_urls(value: list | None) -> list | None:
    if value is None:
        return None
    return [url for url in (entry.strip() if isinstance(entry, str) else entry for entry in value) if url]


def _clean_barcode(value: str | None) -> str | None:
    if not isinstance(value, str):
        return value
    return value.strip() or None


class InventoryItemCreate(BaseModel):
    sku_code: str = Field(min_length=1, max_length=100)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None
    unit_of_measure: str | None = Field(default=None, max_length=50)
    barcode: str | None = Field(default=None, max_length=100)
    cost_price: float | None = Field(default=None, ge=0)
    other_cost: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    reorder_level: int = Field(default=0, ge=0)
    is_active: bool = True
    image_url: str | None = Field(default=None, max_length=500)
    sub_image_urls: list[str] | None = Field(default=None, max_length=2)

    @field_validator("barcode", mode="before")
    @classmethod
    def _strip_barcode(cls, value: str | None) -> str | None:
        return _clean_barcode(value)

    @field_validator("sub_image_urls", mode="before")
    @classmethod
    def _strip_sub_image_urls(cls, value: list | None) -> list | None:
        cleaned = _clean_sub_image_urls(value)
        if cleaned is not None:
            for url in cleaned:
                if not isinstance(url, str) or not (1 <= len(url) <= 500):
                    raise ValueError("Each sub image URL must be 1-500 characters")
        return cleaned


class InventoryItemUpdate(BaseModel):
    sku_code: str | None = Field(default=None, min_length=1, max_length=100)
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None
    unit_of_measure: str | None = Field(default=None, max_length=50)
    barcode: str | None = Field(default=None, max_length=100)
    cost_price: float | None = Field(default=None, ge=0)
    other_cost: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    reorder_level: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    image_url: str | None = Field(default=None, max_length=500)
    sub_image_urls: list[str] | None = Field(default=None, max_length=2)

    @field_validator("barcode", mode="before")
    @classmethod
    def _strip_barcode(cls, value: str | None) -> str | None:
        return _clean_barcode(value)

    @field_validator("sub_image_urls", mode="before")
    @classmethod
    def _strip_sub_image_urls(cls, value: list | None) -> list | None:
        cleaned = _clean_sub_image_urls(value)
        if cleaned is not None:
            for url in cleaned:
                if not isinstance(url, str) or not (1 <= len(url) <= 500):
                    raise ValueError("Each sub image URL must be 1-500 characters")
        return cleaned


class InventoryItemOut(BaseModel):
    id: uuid.UUID
    sku_code: str
    name_zh: str
    name_en: str | None = None
    category_id: uuid.UUID | None = None
    unit_of_measure: str | None = None
    barcode: str | None = None
    cost_price: float | None = None
    other_cost: float | None = None
    sale_price: float | None = None
    reorder_level: int
    avg_cost: float
    is_active: bool
    image_url: str | None = None
    sub_image_urls: list[str] = []
    created_at: datetime
    updated_at: datetime

    @field_validator("sub_image_urls", mode="before")
    @classmethod
    def _none_sub_image_urls(cls, value: list | None) -> list:
        return value or []

    model_config = {"from_attributes": True}


class InventoryStockOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: int
    reserved: int
    available: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryMovementCreate(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    type: MovementType
    quantity: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=500)
    reason_code: str | None = Field(default=None, max_length=30)
    reference: str | None = Field(default=None, max_length=255)


class InventoryMovementOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
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
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    quantity: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)


class InventoryTransferOut(BaseModel):
    transfer_id: uuid.UUID
    out_movement: InventoryMovementOut
    in_movement: InventoryMovementOut


class InventoryReserveBody(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: int = Field(gt=0)


class InventoryStocktakeCreate(BaseModel):
    warehouse_id: uuid.UUID
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
    warehouse_id: uuid.UUID
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
