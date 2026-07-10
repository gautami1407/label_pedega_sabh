"""
Product, scan, comparison, and legacy-compatible API routes.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from lps.gateway.dependencies import get_current_user, get_optional_user, get_user_tier
from lps.services.auth.rate_limit import ScanRateLimiter
from lps.services.history.service import HistoryService
from lps.services.product.comparison import ComparisonService
from lps.services.product.service import ProductService
from lps.services.product_catalog.schemas import ProductByBarcodeResponse, ProductSearchResponse
from lps.services.product_catalog.service import ProductCatalogService
from lps.services.profile.service import ProfileService
from lps.shared.db.postgres import get_db
from lps.shared.models.user import User
from lps.shared.utils.barcode import validate_barcode
import os
import time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["products"])
product_service = ProductService()
product_catalog_service = ProductCatalogService()
comparison_service = ComparisonService()


class ScanPreferences(BaseModel):
    preferences: dict = Field(default_factory=dict)


class BarcodeScanRequest(BaseModel):
    barcode: str
    preferences: dict = Field(default_factory=dict)


class CompareRequest(BaseModel):
    product_a: str
    product_b: str
    preferences: dict = Field(default_factory=dict)


class AnalyzeRequest(BaseModel):
    image: str | None = None
    image_data: str | None = None
    preferences: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str | None = None
    query: str | None = None
    context: dict | None = None


def _resolve_preferences(body_prefs: dict, user: User | None, db: Session) -> dict:
    if body_prefs:
        return body_prefs
    if user:
        return ProfileService(db).get_preferences(user.id)
    return {}


def _enforce_scan_limit(user: User | None, db: Session) -> dict | None:
    if not user:
        return None
    tier = get_user_tier(user)
    return ScanRateLimiter(db).check_and_increment(user.id, tier)


def _record_scan_if_authenticated(user: User | None, db: Session, barcode: str, result: dict) -> None:
    if not user:
        return
    try:
        HistoryService(db).record_scan(
            user.id,
            barcode=barcode,
            product_name=result.get("name"),
            brand=result.get("brand"),
            attention_level=result.get("attention_level"),
            source=result.get("source") or result.get("resolver_source"),
            report_snapshot={
                "attention_label": result.get("attention_label"),
                "barcode": barcode,
            },
        )
    except Exception as exc:
        logger.warning("Failed to record scan history: %s", exc)


def _scan_and_respond(
    barcode: str,
    preferences: dict,
    user: User | None,
    db: Session,
) -> dict:
    is_valid, reason = validate_barcode(barcode)
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    rate_meta = _enforce_scan_limit(user, db)
    result = product_service.analyze_barcode(barcode, preferences)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    if rate_meta:
        result["rate_limit"] = rate_meta
    _record_scan_if_authenticated(user, db, barcode, result)
    return result


# ── Catalog endpoints ─────────────────────────────────────────────

@router.get("/api/v1/catalog/barcode/{barcode}", response_model=ProductByBarcodeResponse)
def catalog_by_barcode(barcode: str):
    product = product_catalog_service.get_by_barcode(barcode)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in local catalog")
    product_out = {k: (str(v) if k == "_id" else v) for k, v in product.items()}
    return {
        "product": product_out,
        "source": product.get("source", "local"),
        "cached": product.get("source") == "local",
    }


@router.get("/api/v1/catalog/search", response_model=ProductSearchResponse)
def catalog_search(q: str = "", page: int = 1, limit: int = 20):
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    items, total = product_catalog_service.search(query, page=page, limit=limit)
    out_items = []
    for item in items:
        obj = {k: (str(v) if k == "_id" else v) for k, v in item.items()}
        out_items.append(obj)
    return {"items": out_items, "total": int(total), "page": int(page), "limit": int(limit)}


# ── Scan & analysis ─────────────────────────────────────────────

@router.post("/api/v1/scan/barcode")
def scan_barcode_v1(
    payload: BarcodeScanRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    preferences = _resolve_preferences(payload.preferences, user, db)
    return _scan_and_respond(payload.barcode, preferences, user, db)


@router.get("/api/v1/products/{barcode}")
@router.post("/api/v1/products/{barcode}")
async def analyze_barcode_v1(
    barcode: str,
    request: Request,
    body: ScanPreferences | None = None,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    preferences = {}
    if request.method == "POST":
        try:
            json_body = await request.json()
            if isinstance(json_body, dict):
                preferences = json_body.get("preferences", {})
        except Exception:
            preferences = body.preferences if body else {}
    preferences = _resolve_preferences(preferences, user, db)
    return _scan_and_respond(barcode, preferences, user, db)


@router.get("/api/product/{barcode}")
@router.post("/api/product/{barcode}")
async def analyze_barcode_legacy(
    barcode: str,
    request: Request,
    body: ScanPreferences | None = None,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    preferences = {}
    if request.method == "POST":
        try:
            json_body = await request.json()
            if isinstance(json_body, dict):
                preferences = json_body.get("preferences", {})
        except Exception:
            preferences = body.preferences if body else {}
    preferences = _resolve_preferences(preferences, user, db)
    return _scan_and_respond(barcode, preferences, user, db)


@router.post("/api/v1/scan/ocr")
@router.post("/api/analyze")
def analyze_image(
    payload: AnalyzeRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    image_data = payload.image or payload.image_data or ""
    if not image_data:
        raise HTTPException(status_code=400, detail="No image data provided")

    encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
    try:
        image_bytes = base64.b64decode(encoded)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image data") from exc

    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image exceeds 5MB limit")

    preferences = _resolve_preferences(payload.preferences, user, db)
    rate_meta = _enforce_scan_limit(user, db)
    result = product_service.analyze_image(image_bytes, preferences)
    if "error" in result and not result.get("name"):
        raise HTTPException(status_code=422, detail=result["error"])
    if rate_meta:
        result["rate_limit"] = rate_meta
    return result


@router.post("/api/v1/products/compare")
def compare_products(
    payload: CompareRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    preferences = _resolve_preferences(payload.preferences, user, db)
    result = comparison_service.compare(payload.product_a, payload.product_b, preferences)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── Search & lookup ─────────────────────────────────────────────

@router.get("/api/product/search")
@router.get("/api/v1/products/search")
def search_products(q: str = "", page_size: int = 5):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    local_items, local_total = product_catalog_service.search(query, page=1, limit=page_size)
    if local_items:
        return {"products": local_items, "count": local_total, "source": "catalog"}

    results = product_service.search_products(query, page_size=page_size)
    return {"products": results, "count": len(results), "source": "open_food_facts"}


@router.get("/api/additives/{identifier}")
@router.get("/api/v1/ingredients/{identifier}")
def lookup_additive(identifier: str):
    result = product_service.lookup_additive(identifier)
    if not result:
        raise HTTPException(status_code=404, detail=f"Additive '{identifier}' not found")
    return result


@router.get("/api/news")
@router.get("/api/v1/alerts/news")
def get_news(product: str | None = None):
    return product_service.fetch_news(product)


@router.post("/api/chat")
@router.post("/api/v1/ai/chat")
def chat(payload: ChatRequest, _user: User | None = Depends(get_optional_user)):
    query = payload.message or payload.query or ""
    if not query:
        raise HTTPException(status_code=400, detail="No message provided")
    return product_service.chat(query, payload.context)


# Diagnostic logging endpoint for scanner diagnostics (writes to backend/logs)
@router.post("/api/v1/scan/logs")
def receive_scan_logs(payload: dict):
    try:
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        fname = f"scan_log_{int(time.time())}.json"
        path = os.path.join(logs_dir, fname)
        with open(path, "w", encoding="utf-8") as fh:
            import json

            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return {"status": "ok", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
