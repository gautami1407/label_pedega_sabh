"""
Phase 0 remediation tests.

Verifies security fixes, language safety, and regulatory data isolation.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from analyzer import Analyzer  # noqa: E402
from csv_loader import RegulatoryCSVDatabase, resolve_regulatory_csv_path  # noqa: E402
from lps.shared.language import (  # noqa: E402
    FORBIDDEN_TERMS,
    MEDICAL_DISCLAIMER,
    sanitize_warning_text,
)
from lps.shared.regulatory_audit import audit_regulatory_csv, classify_row  # noqa: E402


class TestLanguageSafety:
    def test_sanitize_replaces_danger_terms(self):
        raw = "DANGER: CRITICAL ALLERGEN: Peanuts. This is unsafe and dangerous."
        cleaned = sanitize_warning_text(raw)
        for term in FORBIDDEN_TERMS:
            assert term not in cleaned.lower()

    def test_medical_disclaimer_present(self):
        assert "not medical advice" in MEDICAL_DISCLAIMER.lower()

    def test_fallback_warnings_use_safe_language(self):
        analyzer = Analyzer.__new__(Analyzer)
        product_data = {
            "ingredients": "sugar, peanuts, palm oil",
            "allergens": ["peanuts"],
            "scores": {"nutriscore": "d", "nova": "4"},
            "regulatory": {
                "banned_ingredients": [],
                "csv_global_status": [
                    {"country": "FSSAI (India)", "status": "Approved", "risk": "Safe", "flagged_additives": []}
                ],
            },
            "nutrient_levels": {},
            "ingredients_analysis": [],
        }
        preferences = {"allergies": ["peanuts"]}
        insights = Analyzer._generate_fallback_insights(analyzer, product_data, preferences)
        sanitized = Analyzer._sanitize_insights(analyzer, insights)

        for warning in sanitized.get("personal_warnings", []):
            combined = f"{warning.get('title', '')} {warning.get('description', '')}".lower()
            for term in FORBIDDEN_TERMS:
                assert term not in combined
            assert warning.get("type") in ("high", "moderate", "low")


class TestRegulatoryAudit:
    def test_synthetic_additive_quarantined(self):
        row = {
            "E_number": "FSSAI Prohibited",
            "Additive_name": "Synthetic Additive SA-516",
            "Country": "India",
            "Status": "Banned in India",
            "Regulatory_authority": "FSSAI Prohibited",
        }
        assert classify_row(row) == "synthetic_additive"

    def test_verified_e_number_passes(self):
        row = {
            "E_number": "E211",
            "Additive_name": "Sodium Benzoate",
            "Country": "India",
            "Status": "Allowed",
            "Regulatory_authority": "FSSAI",
        }
        assert classify_row(row) is None

    def test_audit_splits_source_csv(self):
        source = BACKEND_DIR / "regulatory_database.csv"
        result = audit_regulatory_csv(source)
        assert result.verified_count > 0
        assert result.quarantined_count > 0
        assert result.verified_count + result.quarantined_count == 1027  # 1027 data rows

    def test_verified_csv_exists_and_loads(self):
        verified_path = BACKEND_DIR / "data" / "regulatory_database_verified.csv"
        assert verified_path.exists()
        resolved = resolve_regulatory_csv_path()
        assert resolved.endswith("regulatory_database_verified.csv")
        db = RegulatoryCSVDatabase()
        assert db.quarantined_count == 0
        assert len(db.all_records) == 327


class TestSecurityConfig:
    def test_env_example_exists(self):
        assert (BACKEND_DIR / ".env.example").exists()

    def test_gitignore_covers_env(self):
        gitignore = BACKEND_DIR.parent.parent.parent.parent / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")
        assert ".env" in content
        assert "secrets.toml" in content

    def test_health_endpoint_hides_keys_in_production_mode(self, monkeypatch):
        monkeypatch.setenv("FLASK_DEBUG", "false")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        from importlib import reload
        import api as api_module

        reload(api_module)
        client = api_module.app.test_client()
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert "gemini_key_set" not in data
        assert "quarantined_excluded" in data


class TestFastAPIGateway:
    def test_fastapi_health_endpoint(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from lps.gateway.main import app

        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "lps-fastapi-gateway"
        assert "gemini_configured" in data["integrations"]
        assert "gemini_api_key" not in str(data)

    def test_disclaimer_endpoint(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from lps.gateway.main import app

        client = TestClient(app)
        response = client.get("/api/v1/meta/disclaimer")
        assert response.status_code == 200
        assert "disclaimer" in response.json()
