from __future__ import annotations

import math
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MovementType = Literal["in", "out", "adjust"]
MovementTypeOut = Literal["in", "out", "adjust", "transfer_in", "transfer_out"]

InReasonCode = Literal["opening", "sales_return", "other"]
OutReasonCode = Literal[
    "damage", "loss", "gift", "sample", "internal_use", "supplier_return", "sale", "other"
]

MAX_OPTION_COMBINATIONS = 200

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


class InventoryBrandCreate(BaseModel):
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    is_active: bool = True

    @field_validator("name_zh", mode="before")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("name_en", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)


class InventoryBrandUpdate(BaseModel):
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

    @field_validator("name_zh", mode="before")
    @classmethod
    def _strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _required_text(value)

    @field_validator("name_en", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)


class InventoryBrandOut(BaseModel):
    id: uuid.UUID
    name_zh: str
    name_en: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryCategoryCreate(BaseModel):
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    parent_id: uuid.UUID | None = None
    is_active: bool = True

    @field_validator("name_zh", mode="before")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        return _required_text(value)


class InventoryCategoryUpdate(BaseModel):
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    parent_id: uuid.UUID | None = None
    is_active: bool | None = None

    @field_validator("name_zh", mode="before")
    @classmethod
    def _strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _required_text(value)


class InventoryCategoryOut(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
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


def _clean_options(value: dict | None) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("options must be an object")
    if not value:
        return None
    if len(value) > 5:
        raise ValueError("At most 5 options are allowed")
    cleaned: dict[str, list[str]] = {}
    for key, values in value.items():
        name = key.strip() if isinstance(key, str) else key
        if not isinstance(name, str) or not name or len(name) > 50:
            raise ValueError("Option names must be 1-50 characters")
        if name in cleaned:
            raise ValueError(f"Duplicate option name: {name}")
        if not isinstance(values, list) or not values:
            raise ValueError(f"Option {name} needs at least one value")
        if len(values) > 50:
            raise ValueError(f"Option {name} has more than 50 values")
        seen: list[str] = []
        for entry in values:
            text = entry.strip() if isinstance(entry, str) else entry
            if not isinstance(text, str) or not text:
                raise ValueError(f"Option {name} has a blank value")
            if text in seen:
                raise ValueError(f"Option {name} has duplicate value: {text}")
            seen.append(text)
        cleaned[name] = seen
    combinations = math.prod(len(values) for values in cleaned.values())
    if combinations > MAX_OPTION_COMBINATIONS:
        raise ValueError(
            f"Options produce {combinations} combinations; the maximum is {MAX_OPTION_COMBINATIONS}"
        )
    return cleaned


def _clean_variant_attrs(value: dict | None) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("variant_attrs must be an object")
    cleaned: dict[str, str] = {}
    for key, attr in value.items():
        name = key.strip() if isinstance(key, str) else key
        text = attr.strip() if isinstance(attr, str) else attr
        if not isinstance(name, str) or not name or not isinstance(text, str) or not text:
            raise ValueError("variant_attrs keys and values must be non-blank text")
        if name in cleaned:
            raise ValueError(f"Duplicate attribute name: {name}")
        cleaned[name] = text
    return cleaned or None


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
    product_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    variant_attrs: dict[str, str] | None = None

    @field_validator("barcode", mode="before")
    @classmethod
    def _strip_barcode(cls, value: str | None) -> str | None:
        return _clean_barcode(value)

    @field_validator("variant_attrs", mode="before")
    @classmethod
    def _strip_variant_attrs(cls, value: dict | None) -> dict | None:
        return _clean_variant_attrs(value)

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
    product_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    variant_attrs: dict[str, str] | None = None

    @field_validator("barcode", mode="before")
    @classmethod
    def _strip_barcode(cls, value: str | None) -> str | None:
        return _clean_barcode(value)

    @field_validator("variant_attrs", mode="before")
    @classmethod
    def _strip_variant_attrs(cls, value: dict | None) -> dict | None:
        return _clean_variant_attrs(value)

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
    product_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    variant_attrs: dict[str, str] | None = None
    on_hand: int = 0
    created_at: datetime
    updated_at: datetime

    @field_validator("sub_image_urls", mode="before")
    @classmethod
    def _none_sub_image_urls(cls, value: list | None) -> list:
        return value or []

    model_config = {"from_attributes": True}


class InventoryProductSkuInput(BaseModel):
    id: uuid.UUID | None = None
    sku_code: str = Field(min_length=1, max_length=100)
    variant_attrs: dict[str, str]
    sale_price: float | None = Field(default=None, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
    other_cost: float | None = Field(default=None, ge=0)
    barcode: str | None = Field(default=None, max_length=100)
    reorder_level: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("sku_code", mode="before")
    @classmethod
    def _strip_code(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("barcode", mode="before")
    @classmethod
    def _strip_barcode(cls, value: str | None) -> str | None:
        return _clean_barcode(value)

    @field_validator("variant_attrs", mode="before")
    @classmethod
    def _strip_variant_attrs(cls, value: dict | None) -> dict:
        cleaned = _clean_variant_attrs(value)
        if not cleaned:
            raise ValueError("variant_attrs must not be empty")
        return cleaned


class InventoryProductCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name_zh: str = Field(min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    unit_of_measure: str | None = Field(default=None, max_length=50)
    image_url: str | None = Field(default=None, max_length=500)
    options: dict[str, list[str]] | None = None
    is_active: bool = True
    skus: list[InventoryProductSkuInput] | None = Field(default=None, max_length=200)

    @field_validator("code", "name_zh", mode="before")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("name_en", "unit_of_measure", "image_url", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("options", mode="before")
    @classmethod
    def _clean_options_field(cls, value: dict | None) -> dict | None:
        return _clean_options(value)


class InventoryProductUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name_zh: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    unit_of_measure: str | None = Field(default=None, max_length=50)
    image_url: str | None = Field(default=None, max_length=500)
    options: dict[str, list[str]] | None = None
    is_active: bool | None = None
    skus: list[InventoryProductSkuInput] | None = Field(default=None, max_length=200)

    @field_validator("code", "name_zh", mode="before")
    @classmethod
    def _strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _required_text(value)

    @field_validator("name_en", "unit_of_measure", "image_url", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("options", mode="before")
    @classmethod
    def _clean_options_field(cls, value: dict | None) -> dict | None:
        return _clean_options(value)


class InventoryProductOut(BaseModel):
    id: uuid.UUID
    code: str
    name_zh: str
    name_en: str | None = None
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    unit_of_measure: str | None = None
    image_url: str | None = None
    options: dict[str, list[str]] | None = None
    is_active: bool
    skus: list[InventoryItemOut] = []
    sku_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryGenerateSkusRequest(BaseModel):
    sale_price: float | None = Field(default=None, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
    reorder_level: int = Field(default=0, ge=0)


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
    effective_date: date | None = None
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
