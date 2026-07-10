from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any



from bson import ObjectId
from pymongo import ASCENDING

from pymongo.collection import Collection
from pymongo.database import Database

from lps.core.config import get_settings
from lps.shared.db.mongo import get_mongo_db

logger = logging.getLogger(__name__)

# Avoid spamming the log with repeated Mongo index warnings during import/startup
_mongo_index_warned = False


COLLECTIONS = {
    "products": "products",
    "ingredients": "ingredients",
    "ingredient_aliases": "ingredient_aliases",
    "regulations": "regulations",
    "regulatory_sources": "regulatory_sources",
    "product_reports": "product_reports",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_barcode(barcode: str) -> str:
    if barcode is None:
        return ""
    b = str(barcode).strip()
    # allow digits only (UPC/EAN are numeric)
    if not b:
        return ""
    return "".join(ch for ch in b if ch.isdigit())


class ProductCatalogRepository:
    def __init__(self, db: Database | None = None):
        self._mongo_disabled = os.getenv("LPS_DISABLE_MONGODB_FOR_TESTS", "").lower() in {"1", "true", "yes"}
        if self._mongo_disabled:
            self.db = None
            self.products = None
            self.ingredients = None
            self.ingredient_aliases = None
            self.regulations = None
            self.regulatory_sources = None
            self.product_reports = None
            return

        self.db = db or get_mongo_db()

        self.products: Collection = self.db[COLLECTIONS["products"]]
        self.ingredients: Collection = self.db[COLLECTIONS["ingredients"]]
        self.ingredient_aliases: Collection = self.db[COLLECTIONS["ingredient_aliases"]]
        self.regulations: Collection = self.db[COLLECTIONS["regulations"]]
        self.regulatory_sources: Collection = self.db[COLLECTIONS["regulatory_sources"]]
        self.product_reports: Collection = self.db[COLLECTIONS["product_reports"]]

        # During tests we must not require a running MongoDB.
        # Index creation triggers network writes. Skip if disabled.
        if os.getenv("LPS_DISABLE_MONGODB_FOR_TESTS", "").lower() in {"1", "true", "yes"}:
            return

        # Pre-check MongoDB connectivity and avoid attempting index creation
        # if the server is unreachable. This prevents repeated noisy warnings
        # during startup when MongoDB isn't available (e.g., local dev without Docker).
        try:
            # ping the server to confirm availability
            self.db.client.admin.command("ping")
        except Exception as exc:
            global _mongo_index_warned
            if not _mongo_index_warned:
                logger.warning("MongoDB not reachable (%s) — skipping index creation: %s", os.getenv("MONGODB_URL", "mongodb://localhost:27017"), exc)
                _mongo_index_warned = True
            return

        self._ensure_indexes()




    def _ensure_indexes(self) -> None:
        try:
            self.products.create_index([("barcode", ASCENDING)], unique=True, sparse=True, name="idx_products_barcode_unique")
            self.products.create_index([("name", ASCENDING)], name="idx_products_name")
            self.products.create_index([("brand", ASCENDING)], name="idx_products_brand")
            self.products.create_index([("category", ASCENDING)], name="idx_products_category")
            self.products.create_index([("last_updated", ASCENDING)], name="idx_products_last_updated")
            self.products.create_index(
                [("name", ASCENDING), ("brand", ASCENDING)],
                name="idx_products_name_brand",
            )
        except Exception as exc:
            global _mongo_index_warned
            if not _mongo_index_warned:
                logger.warning("MongoDB index creation skipped (catalog will use external sources): %s", exc)
                _mongo_index_warned = True
            else:
                logger.debug("MongoDB index creation previously skipped: %s", exc)

    def _pack_product_for_store(self, product: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow()
        base: dict[str, Any] = {
            "barcode": product.get("barcode", ""),
            "name": product.get("name", ""),
            "brand": product.get("brand", ""),
            "category": product.get("category", ""),
            "ingredients": product.get("ingredients", []),
            "nutrition": product.get("nutrition", {}),
            "allergens": product.get("allergens", []),
            "additives": product.get("additives", []),
            "tags": product.get("tags", []),
            "source": product.get("source", "local"),
            "source_url": product.get("source_url", ""),
            "source_version": product.get("source_version", ""),
            "last_verified": product.get("last_verified"),
            "last_updated": product.get("last_updated"),
            "version": int(product.get("version", 1)),
            "created_at": product.get("created_at", now),
            "updated_at": product.get("updated_at", now),
        }

        # Ensure timestamps
        if not base.get("created_at"):
            base["created_at"] = now
        if not base.get("updated_at"):
            base["updated_at"] = now
        if not base.get("last_updated"):
            base["last_updated"] = now

        return base

    def get_product_by_id(self, product_id: str) -> dict[str, Any] | None:
        if self._mongo_disabled:
            return None
        try:
            oid = ObjectId(product_id)
        except Exception:
            return None
        doc = self.products.find_one({"_id": oid})
        return doc

    def get_product_by_barcode(self, barcode: str) -> dict[str, Any] | None:
        if self._mongo_disabled:
            return None
        norm = _normalize_barcode(barcode)
        if not norm:
            return None
        return self.products.find_one({"barcode": norm})

    def search_products(self, q: str, page: int = 1, limit: int = 20) -> tuple[list[dict[str, Any]], int]:
        if self._mongo_disabled:
            return [], 0
        query = (q or "").strip()
        if not query:
            return [], 0

        page = max(1, int(page))
        limit = max(1, min(100, int(limit)))
        skip = (page - 1) * limit

        # Deterministic prefix search for now (indexed fields)
        # Later phases may switch to text index; keep deterministic contract.
        regex = f"^{query}.*"
        cursor = (
            self.products.find({"$or": [{"name": {"$regex": regex, "$options": "i"}}, {"brand": {"$regex": regex, "$options": "i"}}]})
            .sort("last_updated", -1)
            .skip(skip)
            .limit(limit)
        )
        items = list(cursor)

        total = self.products.count_documents({"$or": [{"name": {"$regex": regex, "$options": "i"}}, {"brand": {"$regex": regex, "$options": "i"}}]})
        return items, total

    def upsert_product(
        self,
        *,
        barcode: str,
        payload: dict[str, Any],
        source: str,
        source_url: str = "",
        source_version: str = "",
        last_verified: datetime | None = None,
    ) -> dict[str, Any]:
        if self._mongo_disabled:
            norm = _normalize_barcode(barcode)
            payload = dict(payload)
            payload["barcode"] = norm
            payload["source"] = source
            return payload

        if not norm:
            raise ValueError("Invalid barcode")

        now = _utcnow()
        base_payload = dict(payload)
        base_payload["barcode"] = norm
        base_payload["source"] = source
        base_payload["source_url"] = source_url
        base_payload["source_version"] = source_version

        if last_verified is not None:
            base_payload["last_verified"] = last_verified
        base_payload["last_updated"] = now
        base_payload.setdefault("version", 1)
        base_payload.setdefault("ingredients", [])
        base_payload.setdefault("nutrition", {})
        base_payload.setdefault("allergens", [])
        base_payload.setdefault("additives", [])
        base_payload.setdefault("tags", [])

        stored = self._pack_product_for_store(base_payload)

        # versioning strategy: increment if doc exists
        existing = self.products.find_one({"barcode": norm}, projection={"version": 1})
        if existing and isinstance(existing.get("version"), int):
            stored["version"] = int(existing["version"]) + 1

        update = {
            "$set": stored,
            "$setOnInsert": {
                "created_at": stored["created_at"],
            },
        }

        self.products.update_one({"barcode": norm}, update, upsert=True)

        doc = self.products.find_one({"barcode": norm})
        return doc or stored

