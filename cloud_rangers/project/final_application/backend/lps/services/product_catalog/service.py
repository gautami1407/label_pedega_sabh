from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lps.services.product_catalog.repository import ProductCatalogRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProductCatalogService:
    def __init__(self, repo: ProductCatalogRepository | None = None):
        self.repo = repo or ProductCatalogRepository()

    def get_by_barcode(self, barcode: str) -> dict[str, Any] | None:
        return self.repo.get_product_by_barcode(barcode)

    def search(self, q: str, page: int = 1, limit: int = 20) -> tuple[list[dict[str, Any]], int]:
        return self.repo.search_products(q=q, page=page, limit=limit)

    def get_by_id(self, product_id: str) -> dict[str, Any] | None:
        return self.repo.get_product_by_id(product_id)

    def ingest_from_source(
        self,
        *,
        barcode: str,
        source: str,
        payload: dict[str, Any],
        source_url: str = "",
        source_version: str = "",
        last_verified: datetime | None = None,
    ) -> dict[str, Any]:
        return self.repo.upsert_product(
            barcode=barcode,
            payload=payload,
            source=source,
            source_url=source_url,
            source_version=source_version,
            last_verified=last_verified,
        )

