"""
Product resolver: cache -> MongoDB -> Open Food Facts -> USDA -> store.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from analyzer import Analyzer
from lps.services.product_catalog.service import ProductCatalogService
from lps.shared.cache.product_cache import ProductCache

logger = logging.getLogger(__name__)


class ProductResolver:
    def __init__(self) -> None:
        self.catalog = ProductCatalogService()
        self.cache = ProductCache()
        self._analyzer = Analyzer()

    def resolve(self, barcode: str) -> dict[str, Any]:
        normalized = "".join(ch for ch in barcode if ch.isdigit())
        if not normalized:
            return {"found": False, "source": None, "product": None, "message": "Invalid barcode"}

        cached = self.cache.get(normalized, "resolved_product")
        if cached:
            return {"found": True, "source": cached.get("source", "cache"), "product": cached, "cached": True}

        local = self.catalog.get_by_barcode(normalized)
        if local:
            payload = self._normalize_mongo_product(local)
            self.cache.set(normalized, "resolved_product", payload)
            return {"found": True, "source": "local", "product": payload, "cached": False}

        off_data = self._analyzer.fetcher.fetch_from_open_food_facts(normalized)
        if off_data:
            payload = self._normalize_off_product(normalized, off_data)
            self.catalog.ingest_from_source(
                barcode=normalized,
                source="off",
                payload=payload,
                source_url=f"https://world.openfoodfacts.org/product/{normalized}",
            )
            self.cache.set(normalized, "resolved_product", payload)
            return {"found": True, "source": "off", "product": payload, "cached": False}

        usda_data = self._analyzer.fetcher.fetch_from_usda(normalized)
        if usda_data:
            payload = self._normalize_usda_product(normalized, usda_data)
            self.catalog.ingest_from_source(
                barcode=normalized,
                source="usda",
                payload=payload,
                source_url="https://fdc.nal.usda.gov/",
            )
            self.cache.set(normalized, "resolved_product", payload)
            return {"found": True, "source": "usda", "product": payload, "cached": False}

        return {
            "found": False,
            "source": None,
            "product": None,
            "message": "Data unavailable from verified sources.",
        }

    def _normalize_mongo_product(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "barcode": doc.get("barcode", ""),
            "name": doc.get("name", "Unknown Product"),
            "brand": doc.get("brand", ""),
            "category": doc.get("category", ""),
            "ingredients": doc.get("ingredients", []),
            "nutrition": doc.get("nutrition", {}),
            "allergens": doc.get("allergens", []),
            "source": doc.get("source", "local"),
            "source_url": doc.get("source_url", ""),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "confidence": doc.get("confidence", "high"),
        }

    def _normalize_off_product(self, barcode: str, off_data: dict[str, Any]) -> dict[str, Any]:
        product = off_data.get("product", {})
        ingredients_text = product.get("ingredients_text", "")
        ingredients = [i.strip() for i in ingredients_text.split(",") if i.strip()] if ingredients_text else []
        return {
            "barcode": barcode,
            "name": product.get("product_name", "Unknown Product"),
            "brand": product.get("brands", ""),
            "category": (product.get("categories_tags") or ["unknown"])[0].replace("en:", ""),
            "ingredients": ingredients,
            "ingredients_text": ingredients_text,
            "nutrition": product.get("nutriments", {}),
            "allergens": product.get("allergens_tags", []),
            "images": {"front": product.get("image_url", "")},
            "source": "off",
            "source_url": f"https://world.openfoodfacts.org/product/{barcode}",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "confidence": "high" if ingredients_text else "medium",
        }

    def _normalize_usda_product(self, barcode: str, usda_data: dict[str, Any]) -> dict[str, Any]:
        detail = usda_data.get("detail", {})
        return {
            "barcode": barcode,
            "name": detail.get("description", "Unknown Product"),
            "brand": detail.get("brandOwner", ""),
            "category": detail.get("foodCategory", ""),
            "ingredients": [detail.get("ingredients", "")] if detail.get("ingredients") else [],
            "nutrition": detail.get("foodNutrients", {}),
            "allergens": [],
            "source": "usda",
            "source_url": "https://fdc.nal.usda.gov/",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "confidence": "medium",
        }
