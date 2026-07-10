import os

# Ensure test environment disables MongoDB dependencies
os.environ.setdefault("LPS_DISABLE_MONGODB_FOR_TESTS", "1")

from fastapi.testclient import TestClient
from lps.gateway.main import create_app
from lps.shared.db.postgres import init_db

client = TestClient(create_app())

# Initialize the PostgreSQL schema for tests
init_db()


def register_and_login(email: str, password: str) -> str:
    # Register user
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert register_resp.status_code == 201, f"Register failed: {register_resp.text}"

    # Login user
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return login_resp.json()["access_token"]


def test_profile_get_and_update():
    token = register_and_login("profiletest@example.com", "StrongPass123!")
    headers = {"Authorization": f"Bearer {token}"}

    # GET profile (should create empty profile)
    get_resp = client.get("/api/v1/users/profile", headers=headers)
    assert get_resp.status_code == 200, f"GET profile failed: {get_resp.text}"
    data = get_resp.json()
    assert data["user_id"] is not None
    assert data["age"] is None

    # PUT profile update
    update_payload = {
        "age": 30,
        "gender": "female",
        "allergies": ["peanuts"],
        "height": 165.5,
        "weight": 62.0,
    }
    put_resp = client.put("/api/v1/users/profile", json=update_payload, headers=headers)
    assert put_resp.status_code == 200, f"PUT profile failed: {put_resp.text}"
    updated = put_resp.json()
    assert updated["age"] == 30
    assert updated["gender"] == "female"
    assert "peanuts" in updated["allergies"]
    assert updated["height"] == 165.5
    assert updated["weight"] == 62.0
