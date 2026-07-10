"""
AI orchestrator — structured six-factor pipeline.

Deterministic layers run first; Gemini provides narrative explanations only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lps.shared.language import (
    MEDICAL_DISCLAIMER,
    attention_label_from_score,
    attention_level_from_score,
)
from lps.shared.schemas.product_intelligence import (
    AttentionLevel,
    ChemicalContextItem,
    IngredientPurposeItem,
    NewsAndRecalls,
    PersonalizedWarningItem,
    ProductIntelligenceResponse,
    RegulatoryStatusItem,
    SixFactorsResponse,
)


class AIOrchestrator:
    """Structures analyzer output into the six-factor contract."""

    def build_report(self, barcode: str, analysis: dict[str, Any]) -> ProductIntelligenceResponse:
        insights = analysis.get("dashboard_insights") or analysis
        score = int(insights.get("concern_score", 0) or 0)
        attention = AttentionLevel(
            level=attention_level_from_score(score),
            label=attention_label_from_score(score),
            explanation="Attention level is derived from verified ingredient, nutrition, and profile signals.",
        )

        ingredient_items = []
        for item in insights.get("ingredient_purpose", []) or []:
            ingredient_items.append(
                IngredientPurposeItem(
                    name=item.get("name", ""),
                    category=item.get("risk_level"),
                    purpose=item.get("purpose"),
                    explanation=item.get("purpose"),
                )
            )

        regulatory_items = []
        for row in insights.get("global_regulatory_status", []) or []:
            regulatory_items.append(
                RegulatoryStatusItem(
                    authority=row.get("country"),
                    country=row.get("country"),
                    status=row.get("status"),
                    source="regulatory_database_verified.csv",
                    last_verified=datetime.now(timezone.utc).isoformat(),
                )
            )

        additive_ctx = (insights.get("additive_context") or insights.get("chemical_context_explanation", {}).get("categories") or {})
        chemical_items = []
        if isinstance(additive_ctx, dict):
            for key, value in additive_ctx.items():
                chemical_items.append(
                    ChemicalContextItem(
                        original=key,
                        explanation=f"Detected count: {value}",
                    )
                )

        warning_items = []
        for warning in insights.get("personal_warnings", []) or []:
            warning_items.append(
                PersonalizedWarningItem(
                    type=warning.get("type", "moderate"),
                    title=warning.get("title", ""),
                    description=warning.get("description", ""),
                )
            )

        news_block = insights.get("verified_news_and_recalls") or {}
        news = NewsAndRecalls(
            source=news_block.get("source"),
            product=news_block.get("product") or analysis.get("name"),
        )

        six = SixFactorsResponse(
            attention_level=attention,
            ingredient_purpose=ingredient_items,
            regulatory_status=regulatory_items,
            chemical_context=chemical_items,
            personalized_warnings=warning_items,
            news_and_recalls=news,
        )

        product_payload = dict(analysis)
        product_payload["disclaimer"] = MEDICAL_DISCLAIMER
        product_payload["six_factors"] = six.model_dump()

        return ProductIntelligenceResponse(
            barcode=barcode,
            product=product_payload,
            six_factors=six,
        )
