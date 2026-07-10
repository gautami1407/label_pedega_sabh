"""
Product comparison service — deterministic factor matrix.
"""
from __future__ import annotations

from typing import Any

from lps.services.product.service import ProductService
from lps.shared.language import MEDICAL_DISCLAIMER


class ComparisonService:
    def __init__(self) -> None:
        self.products = ProductService()

    def compare(
        self,
        barcode_a: str,
        barcode_b: str,
        preferences: dict | None = None,
    ) -> dict[str, Any]:
        result_a = self.products.analyze_barcode(barcode_a, preferences or {})
        result_b = self.products.analyze_barcode(barcode_b, preferences or {})

        if "error" in result_a:
            return {"error": f"Product A not found: {result_a['error']}"}
        if "error" in result_b:
            return {"error": f"Product B not found: {result_b['error']}"}

        factors = [
            self._factor_row("Attention Level", result_a.get("attention_level"), result_b.get("attention_level")),
            self._factor_row("Sugar", self._nutrient_level(result_a, "sugars"), self._nutrient_level(result_b, "sugars")),
            self._factor_row("Sodium", self._nutrient_level(result_a, "sodium"), self._nutrient_level(result_b, "sodium")),
            self._factor_row("Additives", self._additive_count(result_a), self._additive_count(result_b)),
            self._factor_row("Allergens", len(result_a.get("allergens", [])), len(result_b.get("allergens", []))),
        ]

        return {
            "product_a": {"barcode": barcode_a, "name": result_a.get("name"), "brand": result_a.get("brand")},
            "product_b": {"barcode": barcode_b, "name": result_b.get("name"), "brand": result_b.get("brand")},
            "factors": factors,
            "summary": self._build_summary(result_a, result_b),
            "disclaimer": MEDICAL_DISCLAIMER,
        }

    def _factor_row(self, name: str, value_a: Any, value_b: Any) -> dict[str, Any]:
        better = "equal"
        if value_a != value_b:
            if name == "Attention Level":
                rank = {"low": 0, "moderate": 1, "high": 2}
                better = "a" if rank.get(str(value_a), 1) < rank.get(str(value_b), 1) else "b"
            elif isinstance(value_a, (int, float)) and isinstance(value_b, (int, float)):
                better = "a" if value_a < value_b else "b"
            else:
                better = "equal"
        return {"name": name, "product_a": value_a, "product_b": value_b, "better": better}

    def _nutrient_level(self, product: dict, key: str) -> str:
        levels = product.get("nutrient_levels") or {}
        return levels.get(key, product.get("nutrition", {}).get(key, "unknown"))

    def _additive_count(self, product: dict) -> int:
        insights = product.get("dashboard_insights") or {}
        ctx = insights.get("additive_context") or {}
        if isinstance(ctx, dict):
            return sum(int(v) for v in ctx.values() if isinstance(v, (int, float)))
        return len(product.get("additives_tags", []) or [])

    def _build_summary(self, a: dict, b: dict) -> str:
        return (
            f"{a.get('name', 'Product A')} and {b.get('name', 'Product B')} were compared using "
            "verified ingredient and nutrition data. Review the factor table for informational differences."
        )
