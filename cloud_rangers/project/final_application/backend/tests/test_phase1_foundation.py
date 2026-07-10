"""
Phase 1 foundation tests — auth, profile, product API, attention levels.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from lps.gateway.main import app
from lps.shared.security.jwt import create_access_token, decode_token
from lps.shared.security.password import hash_password, verify_password


client = TestClient(app)


class TestSecurityUtilities:
    def test_password_hash_and_verify(self):
        hashed = hash_password("SecurePass123!")
        assert verify_password("SecurePass123!", hashed)
        assert not verify_password("wrong", hashed)

    def test_jwt_roundtrip(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)


class TestAuthAPI:
    def test_register_and_login(self):
        email = f"user_{uuid.uuid4().hex[:8]}@test.com"
        reg = client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Test User",
            "terms_accepted": True,
        })
        assert reg.status_code == 201
        data = reg.json()
        assert data["access_token"]
        assert data["user"]["tier"] == "free"

        login = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "TestPass123!",
        })
        assert login.status_code == 200
        assert login.json()["access_token"]

    def test_guest_login(self):
        resp = client.post("/api/v1/auth/guest", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["is_guest"] is True
        assert data["user"]["tier"] == "guest"

    def test_duplicate_register_rejected(self):
        email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
        payload = {
            "email": email,
            "password": "TestPass123!",
            "full_name": "Dup User",
            "terms_accepted": True,
        }
        assert client.post("/api/v1/auth/register", json=payload).status_code == 201
        assert client.post("/api/v1/auth/register", json=payload).status_code == 409


class TestProfileAPI:
    def _auth_headers(self):
        reg = client.post("/api/v1/auth/register", json={
            "email": f"profile_{uuid.uuid4().hex[:8]}@test.com",
            "password": "TestPass123!",
            "full_name": "Profile User",
            "terms_accepted": True,
        })
        token = reg.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_profile_crud(self):
        headers = self._auth_headers()
        get_resp = client.get("/api/v1/users/profile", headers=headers)
        assert get_resp.status_code == 200

        put_resp = client.put("/api/v1/users/profile", headers=headers, json={
            "age": 30,
            "allergies": ["peanuts"],
            "dietary_preference": "vegetarian",
            "height": 175,
            "weight": 70,
        })
        assert put_resp.status_code == 200
        body = put_resp.json()
        assert body["age"] == 30
        assert "peanuts" in body["allergies"]
        assert body["height"] == 175

    def test_profile_requires_auth(self):
        resp = client.get("/api/v1/users/profile")
        assert resp.status_code == 401


class TestProductAPI:
    def test_health_includes_infrastructure(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "lps-fastapi-gateway"
        assert "infrastructure" in data
        assert "attention_level" not in data

    def test_legacy_product_route_exists(self):
        resp = client.get("/api/product/3017620422003")
        assert resp.status_code in (200, 404)

    def test_search_requires_query(self):
        resp = client.get("/api/product/search")
        assert resp.status_code == 400
