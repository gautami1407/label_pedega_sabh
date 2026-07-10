"""
Scan history and favorites service.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from lps.shared.models.history import Favorite, ScanHistory


class HistoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_scan(
        self,
        user_id: uuid.UUID,
        *,
        barcode: str | None,
        product_name: str | None,
        brand: str | None,
        attention_level: str | None,
        source: str | None,
        report_snapshot: dict,
    ) -> ScanHistory:
        entry = ScanHistory(
            user_id=user_id,
            barcode=barcode,
            product_name=product_name,
            brand=brand,
            attention_level=attention_level,
            source=source,
            report_snapshot=report_snapshot,
            scanned_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_scans(self, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0) -> list[ScanHistory]:
        return (
            self.db.query(ScanHistory)
            .filter(ScanHistory.user_id == user_id)
            .order_by(ScanHistory.scanned_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def add_favorite(
        self,
        user_id: uuid.UUID,
        *,
        barcode: str,
        product_name: str | None,
        product_snapshot: dict,
    ) -> Favorite:
        existing = (
            self.db.query(Favorite)
            .filter(Favorite.user_id == user_id, Favorite.barcode == barcode)
            .first()
        )
        if existing:
            existing.product_name = product_name
            existing.product_snapshot = product_snapshot
            self.db.commit()
            self.db.refresh(existing)
            return existing

        fav = Favorite(
            user_id=user_id,
            barcode=barcode,
            product_name=product_name,
            product_snapshot=product_snapshot,
        )
        self.db.add(fav)
        self.db.commit()
        self.db.refresh(fav)
        return fav

    def list_favorites(self, user_id: uuid.UUID) -> list[Favorite]:
        return (
            self.db.query(Favorite)
            .filter(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
            .all()
        )

    def remove_favorite(self, user_id: uuid.UUID, favorite_id: uuid.UUID) -> bool:
        fav = (
            self.db.query(Favorite)
            .filter(Favorite.id == favorite_id, Favorite.user_id == user_id)
            .first()
        )
        if not fav:
            return False
        self.db.delete(fav)
        self.db.commit()
        return True
