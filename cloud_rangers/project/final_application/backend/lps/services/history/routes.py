from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from lps.gateway.dependencies import get_current_user
from lps.services.history.service import HistoryService
from lps.shared.db.postgres import get_db
from lps.shared.models.user import User

router = APIRouter(prefix="/api/v1/history", tags=["history"])


class FavoriteRequest(BaseModel):
    barcode: str
    product_name: str | None = None
    product_snapshot: dict = Field(default_factory=dict)


@router.get("/scans")
def list_scans(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = HistoryService(db).list_scans(user.id, limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": str(r.id),
                "barcode": r.barcode,
                "product_name": r.product_name,
                "brand": r.brand,
                "attention_level": r.attention_level,
                "source": r.source,
                "scanned_at": r.scanned_at.isoformat(),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/favorites")
def list_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = HistoryService(db).list_favorites(user.id)
    return {
        "items": [
            {
                "id": str(r.id),
                "barcode": r.barcode,
                "product_name": r.product_name,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/favorites", status_code=201)
def add_favorite(
    payload: FavoriteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fav = HistoryService(db).add_favorite(
        user.id,
        barcode=payload.barcode,
        product_name=payload.product_name,
        product_snapshot=payload.product_snapshot,
    )
    return {"id": str(fav.id), "barcode": fav.barcode, "product_name": fav.product_name}


@router.delete("/favorites/{favorite_id}")
def remove_favorite(
    favorite_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    removed = HistoryService(db).remove_favorite(user.id, favorite_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return {"status": "deleted"}
