"""
Phase 2 core product feature tests — barcode, history, comparison, orchestrator.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lps.gateway.main import app
from lps.services.ai.orchestrator import AIOrchestrator
from lps.shared.utils.barcode import normalize_barcode, validate_barcode


client = TestClient(app)


class TestBarcodeValidation:
    def test_valid_ean13(self):
        ok, reason = validate_barcode("3017620422003")
        assert ok, reason

    def test_invalid_checksum(self):
        ok, reason = validate_barcode("3017620422004")
        assert not ok
        assert "checksum" in reason.lower()

    def test_empty_barcode(self):
        ok, reason = validate_barcode("")
        assert not ok
        assert "empty" in reason.lower()

    def test_normalize_strips_non_digits(self):
        assert normalize_barcode("301-762-042-2003") == "3017620422003"


class TestHistoryAPI:
    def _auth_headers(self) -> dict[str, str]:
        email = f"hist_{uuid.uuid4().hex[:8]}@test.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "TestPass123!",
                "full_name": "History User",
                "terms_accepted": True,
            },
        )
        token = reg.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_favorites_crud(self):
        headers = self._auth_headers()
        add = client.post(
            "/api/v1/history/favorites",
            headers=headers,
            json={"barcode": "3017620422003", "product_name": "Nutella"},
        )
        assert add.status_code == 201
        fav_id = add.json()["id"]

        listing = client.get("/api/v1/history/favorites", headers=headers)
        assert listing.status_code == 200
        assert any(item["barcode"] == "3017620422003" for item in listing.json()["items"])

        deleted = client.delete(f"/api/v1/history/favorites/{fav_id}", headers=headers)
        assert deleted.status_code == 200

    def test_scans_requires_auth(self):
        resp = client.get("/api/v1/history/scans")
        assert resp.status_code == 401


class TestProductRoutes:
    def test_invalid_barcode_rejected(self):
        resp = client.get("/api/product/12345")
        assert resp.status_code == 400

    def test_compare_requires_valid_products(self):
        resp = client.post(
            "/api/v1/products/compare",
            json={"product_a": "invalid", "product_b": "also-invalid"},
        )
        assert resp.status_code in (400, 404)

    @patch("lps.services.product.service.ProductService.analyze_barcode")
    def test_scan_records_history_for_authenticated_user(self, mock_analyze):
        mock_analyze.return_value = {
            "name": "Test Product",
            "brand": "Test Brand",
            "attention_level": "low",
            "source": "off",
            "dashboard_insights": {"concern_score": 10},
        }
        email = f"scan_{uuid.uuid4().hex[:8]}@test.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "TestPass123!",
                "full_name": "Scan User",
                "terms_accepted": True,
            },
        )
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        scan = client.post(
            "/api/v1/scan/barcode",
            headers=headers,
            json={"barcode": "3017620422003"},
        )
        assert scan.status_code == 200

        history = client.get("/api/v1/history/scans", headers=headers)
        assert history.status_code == 200
        items = history.json()["items"]
        assert any(item["barcode"] == "3017620422003" for item in items)


class TestAIOrchestrator:
    def test_build_report_structure(self):
        analysis = {
            "name": "Sample",
            "dashboard_insights": {
                "concern_score": 25,
                "ingredient_purpose": [{"name": "sugar", "purpose": "sweetener", "risk_level": "low"}],
                "global_regulatory_status": [{"country": "EU", "status": "approved"}],
                "personal_warnings": [{"type": "moderate", "title": "Sugar", "description": "Contains sugar."}],
                "verified_news_and_recalls": {"source": "fda", "product": "Sample"},
            },
        }
        report = AIOrchestrator().build_report("3017620422003", analysis)
        payload = report.model_dump()
        assert payload["barcode"] == "3017620422003"
        assert payload["six_factors"]["attention_level"]["level"] in ("low", "moderate", "high")
        assert len(payload["six_factors"]["ingredient_purpose"]) == 1
