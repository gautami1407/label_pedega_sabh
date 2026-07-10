from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceType(BaseModel):
    value: Literal["local", "off", "usda"]


class ProductDocument(BaseModel):
    id: str | None = Field(default=None, alias="_id")

    barcode: str | None = ""
    name: str | None = ""
    brand: str | None = ""
    category: str | None = ""

    ingredients: list[Any] = Field(default_factory=list)
    nutrition: dict[str, Any] = Field(default_factory=dict)

    allergens: list[Any] = Field(default_factory=list)
    additives: list[Any] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    source: Literal["local", "off", "usda"] = "local"
    source_url: str = ""
    source_version: str = ""

    last_verified: datetime | None = None
    last_updated: datetime | None = None

    version: int = 1

    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductSearchResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20


class ProductByBarcodeResponse(BaseModel):
    product: dict[str, Any] = Field(default_factory=dict)
    source: Literal["local", "off", "usda"] = "local"
    cached: bool = False

