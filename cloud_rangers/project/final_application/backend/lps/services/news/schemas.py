from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

class RecallItem(BaseModel):
    recall_number: str = Field(..., description="Unique recall identifier")
    product_description: str = Field(..., description="Description of the recalled product")
    reason: str = Field(..., description="Reason for recall")
    status: str = Field(..., description="Current status of the recall")
    distribution_pattern: Optional[str] = Field(None, description="Distribution pattern info")
    recall_initiation_date: Optional[datetime] = Field(None, description="Date recall was initiated")
    source: str = Field(..., description="Source of the recall information")
    last_verified: Optional[datetime] = Field(None, description="When this record was last verified")
    confidence: Optional[str] = Field(None, description="Confidence level (high/medium/low)")

class NewsItem(BaseModel):
    title: str = Field(..., description="Headline of the news article")
    url: str = Field(..., description="Link to the full article")
    source: str = Field(..., description="Publisher or agency")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    last_verified: Optional[datetime] = Field(None, description="When this article was last verified")
    confidence: Optional[str] = Field(None, description="Confidence level of relevance")

class NewsAndRecallsResponse(BaseModel):
    verified_recalls: List[RecallItem] = Field(default_factory=list, description="List of verified recall entries")
    related_news: List[NewsItem] = Field(default_factory=list, description="List of related news articles")
    last_updated: Optional[datetime] = Field(None, description="Timestamp of last aggregation update")
    source_attribution: Optional[dict] = Field(None, description="Metadata about data sources used")
