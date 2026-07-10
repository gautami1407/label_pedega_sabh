from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, List, Optional

class AttentionLevel(BaseModel):
    level: str = Field(..., description="Low, Moderate, High, or Insufficient Data")
    label: Optional[str] = Field(None, description="Human readable label derived from score")
    explanation: Optional[str] = Field(None, description="Why this level was assigned")

class IngredientPurposeItem(BaseModel):
    name: str = Field(..., description="Ingredient name")
    category: Optional[str] = Field(None, description="Broad category (e.g., preservative, vitamin)")
    purpose: Optional[str] = Field(None, description="Plain‑language purpose of the ingredient")
    explanation: Optional[str] = Field(None, description="Additional explanation if available")

class RegulatoryStatusItem(BaseModel):
    authority: Optional[str] = Field(None, description="Regulatory authority name")
    country: Optional[str] = Field(None, description="Country or region")
    status: Optional[str] = Field(None, description="Regulatory status string")
    source: Optional[str] = Field(None, description="Data source identifier")
    last_verified: Optional[str] = Field(None, description="ISO timestamp of last verification")

class ChemicalContextItem(BaseModel):
    original: str = Field(..., description="Original ingredient term")
    explanation: str = Field(..., description="Plain‑language translation or context")

class PersonalizedWarningItem(BaseModel):
    type: str = Field(..., description="high or moderate")
    title: str = Field(..., description="Short title of the warning")
    description: str = Field(..., description="Explanation tailored to the user profile")

class NewsAndRecalls(BaseModel):
    source: Optional[str] = Field(None, description="Source identifier for recalls/news")
    product: Optional[str] = Field(None, description="Product name linked to news/recalls")
    # Additional fields can be added if the service provides them

class SixFactorsResponse(BaseModel):
    attention_level: AttentionLevel = Field(...)
    ingredient_purpose: List[IngredientPurposeItem] = Field(default_factory=list)
    regulatory_status: List[RegulatoryStatusItem] = Field(default_factory=list)
    chemical_context: List[ChemicalContextItem] = Field(default_factory=list)
    personalized_warnings: List[PersonalizedWarningItem] = Field(default_factory=list)
    news_and_recalls: NewsAndRecalls = Field(default_factory=NewsAndRecalls)

class ProductIntelligenceResponse(BaseModel):
    barcode: str = Field(..., description="Scanned barcode value")
    product: dict = Field(..., description="Full product payload as returned by analyzer")
    six_factors: SixFactorsResponse = Field(..., description="Engine output broken into six factors")
