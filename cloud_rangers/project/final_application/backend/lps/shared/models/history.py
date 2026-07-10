"""
Scan history, favorites, and comparison history models.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from lps.shared.db.postgres import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScanHistory(Base):
    __tablename__ = "scan_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attention_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    report_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    barcode: Mapped[str] = mapped_column(String(50), index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ComparisonHistory(Base):
    __tablename__ = "comparison_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    product_a_barcode: Mapped[str] = mapped_column(String(50))
    product_b_barcode: Mapped[str] = mapped_column(String(50))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
