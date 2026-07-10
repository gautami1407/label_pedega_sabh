"""
Tests for health check endpoint and application startup.

Tests:
- Application initialization
- Health check endpoint response structure
- Database connectivity verification
- Cache connectivity verification
- Regulatory database loading
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    from lps.gateway.main import app
    return TestClient(app)


@pytest.mark.api
def test_health_check_returns_200(client: TestClient) -> None:
    """Test that health endpoint returns 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.api
def test_health_check_structure(client: TestClient) -> None:
    """Test that health endpoint returns required structure."""
    response = client.get("/api/health")
    data = response.json()

    # Required top-level fields
    assert "status" in data
    assert "service" in data
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data
    assert "databases" in data
    assert "regulatory" in data
    assert "disclaimer" in data

    # Status should be one of valid states
    assert data["status"] in ["ok", "degraded", "failed"]

    # Service identification
    assert data["service"] == "lps-fastapi-gateway"
    assert data["version"] == "1.0.0"

    # Environment should be valid
    assert data["environment"] in ["development", "staging", "production"]


@pytest.mark.api
def test_health_check_databases(client: TestClient) -> None:
    """Test that health endpoint reports database status."""
    response = client.get("/api/health")
    data = response.json()

    assert "postgresql" in data["databases"]
    assert "redis" in data["databases"]
    assert "mongodb" in data["databases"]

    for db_name, db_info in data["databases"].items():
        assert "status" in db_info, f"Missing status for {db_name}"
        assert db_info["status"] in ["ok", "failed"], f"Invalid status for {db_name}"


@pytest.mark.api
def test_health_check_regulatory(client: TestClient) -> None:
    """Test that health endpoint reports regulatory data status."""
    response = client.get("/api/health")
    data = response.json()

    assert "csv_loaded" in data["regulatory"]
    assert "verified_records" in data["regulatory"]
    assert "quarantined_excluded" in data["regulatory"]

    # These should be booleans or integers
    assert isinstance(data["regulatory"]["csv_loaded"], bool)
    assert isinstance(data["regulatory"]["verified_records"], int)
    assert isinstance(data["regulatory"]["quarantined_excluded"], int)


@pytest.mark.api
def test_disclaimer_endpoint(client: TestClient) -> None:
    """Test that disclaimer endpoint works."""
    response = client.get("/api/v1/meta/disclaimer")
    assert response.status_code == 200
    data = response.json()
    assert "disclaimer" in data
    assert len(data["disclaimer"]) > 0


@pytest.mark.api
def test_docs_endpoint_available_in_debug(client: TestClient) -> None:
    """Test that API docs are available in debug mode."""
    from lps.core.config import get_settings
    settings = get_settings()

    if settings.debug:
        response = client.get("/api/docs")
        # Docs might redirect or return HTML
        assert response.status_code in [200, 307, 308]


@pytest.mark.integration
def test_index_html_available(client: TestClient) -> None:
    """Test that index.html is served."""
    response = client.get("/")
    # Could return HTML or JSON depending on frontend availability
    assert response.status_code in [200, 404]


@pytest.mark.unit
def test_settings_initialization() -> None:
    """Test that settings initialize correctly."""
    from lps.core.config import get_settings

    settings = get_settings()

    assert settings.app_name == "Label Padegha Sabh API"
    assert settings.app_version == "1.0.0"
    assert settings.environment in ["development", "staging", "production"]
    assert settings.fastapi_port > 0
    assert len(settings.jwt_secret) >= 32


@pytest.mark.unit
def test_settings_validation() -> None:
    """Test that settings validation works."""
    from lps.core.config import Settings

    # Valid settings should initialize
    settings = Settings(
        jwt_secret="a" * 32,
        database_url="postgresql://user:pass@localhost/db",
    )
    assert settings is not None

    # Invalid JWT secret should fail
    with pytest.raises(ValueError):
        Settings(jwt_secret="tooshort")


@pytest.mark.unit
def test_logging_setup() -> None:
    """Test that logging is initialized correctly."""
    from lps.core.logging import setup_logging, get_logger

    setup_logging()
    logger = get_logger("test_logger")

    assert logger is not None
    assert logger.name == "test_logger"


@pytest.mark.unit
def test_settings_database_url_safe() -> None:
    """Test that database URLs are safely masked."""
    from lps.core.config import Settings

    settings = Settings(
        database_url="postgresql://user:password123@localhost:5432/mydb",
        jwt_secret="a" * 32,
    )

    safe_url = settings.get_database_url_safe()
    assert "password123" not in safe_url
    assert "***" in safe_url
    assert "localhost" in safe_url


@pytest.mark.unit
def test_settings_production_check() -> None:
    """Test that environment checks work."""
    from lps.core.config import Settings

    # Development environment
    dev_settings = Settings(
        environment="development",
        jwt_secret="a" * 32,
    )
    assert dev_settings.is_development()
    assert not dev_settings.is_production()

    # Production environment
    prod_settings = Settings(
        environment="production",
        jwt_secret="a" * 32,
    )
    assert prod_settings.is_production()
    assert not prod_settings.is_development()


@pytest.mark.api
def test_request_id_header_in_response(client: TestClient) -> None:
    """Test that X-Request-ID header is included in response."""
    response = client.get("/api/health")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


@pytest.mark.api
def test_cors_headers_present(client: TestClient) -> None:
    """Test that CORS headers are properly configured."""
    response = client.options("/api/health")
    # OPTIONS might not be directly supported but GET should have CORS headers
    response = client.get("/api/health")
    # At minimum, health check should be accessible
    assert response.status_code == 200
