"""Production-grade configuration management.

Pydantic v2 compatibility notes:
- `BaseSettings` has moved to the `pydantic-settings` package.

All secrets must come from environment variables or .env.
"""

from __future__ import annotations

import os
import json
from functools import lru_cache
from typing import Any, Literal


from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables with validation."""

    # APPLICATION
    app_name: str = Field(default="Label Padegha Sabh API", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Deployment environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # SERVER
    host: str = Field(default="0.0.0.0", description="Server bind address")
    fastapi_port: int = Field(default=8000, gt=0, le=65535, description="FastAPI port")
    flask_port: int = Field(default=5000, gt=0, le=65535, description="Legacy Flask port")

    # CORS
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5000",
            "http://127.0.0.1:8000",
        ],
        description="CORS allowed origins",
    )
    cors_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_methods: list[str] = Field(default=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    cors_headers: list[str] = Field(default=["*"])

    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Make CORS env parsing resilient.

        Supports:
        - JSON list: ["http://...", "http://..."]
        - comma-separated string: http://a,http://b
        - single string: http://a
        - empty/None -> default
        """
        if v is None:
            return [
                "http://localhost:3000",
                "http://localhost:5000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:5000",
                "http://127.0.0.1:8000",
            ]
        if isinstance(v, list):
            # ensure all items are strings and strip whitespace
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return [
                    "http://localhost:3000",
                    "http://localhost:5000",
                    "http://localhost:8000",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:5000",
                    "http://127.0.0.1:8000",
                ]
            # If it looks like JSON list, let pydantic parse it later.
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    # fall through to comma split
                    pass
            # Comma-separated
            if "," in s:
                return [part.strip() for part in s.split(",") if part.strip()]
            return [s]
        # Fallback to defaults
        return [
            "http://localhost:3000",
            "http://localhost:5000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5000",
            "http://127.0.0.1:8000",
        ]


    # DATABASES — PostgreSQL
    database_url: str = Field(
        default="postgresql://lps:lps_dev_password@localhost:5432/lps",
        description="PostgreSQL connection string",
    )


    # Compatibility: some call sites/tools expect a string.
    @property
    def database_url_str(self) -> str:
        return self.database_url


    db_pool_size: int = Field(default=10, ge=1, le=100, description="SQLAlchemy pool size")
    db_pool_recycle: int = Field(default=3600, description="Recycle connections after N seconds")
    db_echo: bool = Field(default=False, description="Echo SQL statements")

    # DATABASES — MongoDB
    mongodb_url: str = Field(
        default="mongodb://localhost:27017/lps",

        description="MongoDB connection string",
    )
    mongodb_server_selection_timeout: int = Field(
        default=3000, ge=100, description="MongoDB selection timeout (ms)"
    )

    # CACHE — Redis
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection string")

    redis_socket_timeout: int = Field(default=5, ge=1, description="Redis socket timeout (seconds)")
    redis_socket_connect_timeout: int = Field(
        default=5, ge=1, description="Redis connect timeout (seconds)"
    )

    # AUTHENTICATION — JWT
    jwt_secret: str = Field(
        default="change-me-in-production-use-openssl-rand-hex-32",
        description="JWT signing secret",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=365)

    @field_validator("jwt_secret")
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    # RATE LIMITING
    guest_daily_scan_limit: int = Field(default=5, ge=0)
    free_daily_scan_limit: int = Field(default=20, ge=0)
    premium_daily_scan_limit: int = Field(default=1000, ge=0)

    # EXTERNAL SERVICES — Gemini
    gemini_api_key: str = Field(default="", description="Gemini API key (optional)")
    gemini_model: str = Field(default="gemini-pro", description="Gemini model")
    gemini_timeout: int = Field(default=30, ge=5, description="Timeout (seconds)")

    # EXTERNAL SERVICES — USDA
    usda_api_key: str = Field(default="", description="USDA API key (optional)")
    usda_base_url: str = Field(
        default="https://fdc.nal.usda.gov/api/food", description="USDA API base URL"
    )

    # REGULATORY DATA
    regulatory_csv_path: str = Field(default="regulatory_database.csv")

    @field_validator("regulatory_csv_path", mode="before")
    def resolve_regulatory_csv_path(cls, v: str) -> str:
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        verified_path = os.path.join(backend_dir, "data", "regulatory_database_verified.csv")
        legacy_path = os.path.join(backend_dir, "data", "regulatory_database.csv")
        if os.path.exists(verified_path):
            return verified_path
        if os.path.exists(legacy_path):
            return legacy_path
        return v

    # PATHS
    frontend_dir: str = Field(default="../frontend", description="Frontend static files directory")

    @field_validator("frontend_dir", mode="before")
    def resolve_frontend_dir(cls, v: str) -> str:
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if not os.path.isabs(v):
            return os.path.join(backend_dir, v)
        return v

    # LOGGING
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    log_format: Literal["plain", "json"] = Field(default="json")

    # NOTE: keep env loading but disable strict parsing for complex types.
    # Some environments provide malformed values (e.g., cors_origins) and
    # we want the app to still start with defaults.
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Avoid raising hard errors on env parsing; fields will fall back to defaults.
        # (Pydantic-settings v2 key: `json_loads` is internal; `parse_env_none_str` etc
        # not reliable across versions. This is the most compatible lever.)
        enable_decoding=False,
    )


    def __init__(self, **kwargs: Any) -> None:
        if "debug" not in kwargs:
            if os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes"):
                kwargs["debug"] = True

        if "environment" not in kwargs:
            lps_server = os.getenv("LPS_SERVER", "fastapi").lower()
            kwargs["environment"] = "development" if lps_server == "fastapi" else "production"

        super().__init__(**kwargs)

    def get_database_url_safe(self) -> str:
        url_str = self.database_url

        if "@" in url_str:
            scheme_part = url_str.split("://")[0]
            host_part = url_str.split("@", 1)[1]
            return f"{scheme_part}://***@{host_part}"
        return url_str

    def is_production(self) -> bool:
        return self.environment == "production"

    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

