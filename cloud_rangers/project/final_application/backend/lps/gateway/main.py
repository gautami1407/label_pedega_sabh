"""
FastAPI gateway for Label Padegha Sabh — Phase 1 production API.

Production-grade gateway with:
- Structured logging
- Comprehensive health checks
- Request/Response middleware
- Graceful startup/shutdown
- CORS configuration
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from csv_loader import RegulatoryCSVDatabase  # noqa: E402
from lps.core.config import get_settings  # noqa: E402
from lps.core.logging import setup_logging, get_logger  # noqa: E402
from lps.core.middleware import RequestLoggingMiddleware, ErrorHandlingMiddleware  # noqa: E402
from lps.services.auth.routes import router as auth_router  # noqa: E402
from lps.services.history.routes import router as history_router  # noqa: E402
from lps.services.product.routes import router as product_router  # noqa: E402
from lps.services.profile.routes import router as profile_router  # noqa: E402
from lps.shared.db.mongo import mongo_ping  # noqa: E402
from lps.shared.db.postgres import init_db  # noqa: E402
from lps.shared.db.redis_client import redis_ping  # noqa: E402
from lps.shared.language import MEDICAL_DISCLAIMER  # noqa: E402

# Initialize logging before settings are loaded
setup_logging()
logger = get_logger(__name__)

settings = get_settings()
_reg_db: RegulatoryCSVDatabase | None = None


def get_reg_db() -> RegulatoryCSVDatabase:
    """Get regulatory database instance (lazy loaded)."""
    global _reg_db
    if _reg_db is None:
        logger.info("Loading regulatory database from CSV")
        _reg_db = RegulatoryCSVDatabase(csv_path=settings.regulatory_csv_path)
        logger.info(f"Regulatory database loaded: {len(_reg_db.all_records)} records")
    return _reg_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Application startup and shutdown events.
    
    Startup:
    - Initialize databases
    - Load regulatory data
    - Warm up connections
    
    Shutdown:
    - Graceful resource cleanup
    """
    logger.info("========== APPLICATION STARTUP ==========")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Database: {settings.get_database_url_safe()}")
    
    try:
        logger.info("Initializing PostgreSQL...")
        init_db()
        logger.info("PostgreSQL initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}", exc_info=True)
        raise

    try:
        logger.info("Loading regulatory database...")
        get_reg_db()
        logger.info("Regulatory database loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load regulatory database: {e}", exc_info=True)
        raise

    logger.info("========== APPLICATION READY ==========")
    
    yield
    
    logger.info("========== APPLICATION SHUTDOWN ==========")
    logger.info("Cleaning up resources...")
    # Shutdown logic here
    logger.info("========== APPLICATION STOPPED ==========")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware in correct order (reverse order of execution)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(history_router)
app.include_router(product_router)


@app.get("/api/docs", include_in_schema=False)
async def api_docs_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

_frontend = Path(settings.frontend_dir).resolve()

@app.get("/", include_in_schema=False)
async def serve_index():
    index = _frontend / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Label Padegha Sabh API", "docs": "/api/docs"}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    target = _frontend / full_path
    if target.exists() and target.is_file():
        return FileResponse(target)

    # Allow directory index.html files for nested paths.
    if target.exists() and target.is_dir():
        index = target / "index.html"
        if index.exists():
            return FileResponse(index)

    # If the file is not found, fall back to index.html for SPA routing.
    index = _frontend / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/health")
@app.get("/api/health")
@app.get("/api/v1/health")
async def health() -> dict:
    """
    Comprehensive health check endpoint.
    
    Returns:
    - Application status
    - Version
    - Database connectivity (PostgreSQL)
    - Cache connectivity (Redis)
    - Document store connectivity (MongoDB)
    - Regulatory database status
    - Integration status (debug only)
    """
    pg_status = _postgres_ok()
    redis_status = redis_ping()
    mongo_status = mongo_ping()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    critical_ok = pg_status
    non_critical_ok = redis_status and mongo_status
    health_status = "ok" if critical_ok else "degraded" if non_critical_ok else "failed"
    
    payload = {
        "status": health_status,
        "service": "lps-fastapi-gateway",
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": now,
        "databases": {
            "postgresql": {
                "status": "ok" if pg_status else "failed",
                "url": settings.get_database_url_safe(),
            },
            "redis": {
                "status": "ok" if redis_status else "failed",
                "url": str(settings.redis_url).split("/")[0:3] + ["****"] if "/" in str(settings.redis_url) else "unknown",
            },
            "mongodb": {
                "status": "ok" if mongo_status else "failed",
                "url": str(settings.mongodb_url).split("/")[0:3] + ["****"] if "/" in str(settings.mongodb_url) else "unknown",
            },
        },
        "infrastructure": {
            "postgresql": {
                "status": "ok" if pg_status else "failed",
                "url": settings.get_database_url_safe(),
            },
            "redis": {
                "status": "ok" if redis_status else "failed",
                "url": str(settings.redis_url).split("/")[0:3] + ["****"] if "/" in str(settings.redis_url) else "unknown",
            },
            "mongodb": {
                "status": "ok" if mongo_status else "failed",
                "url": str(settings.mongodb_url).split("/")[0:3] + ["****"] if "/" in str(settings.mongodb_url) else "unknown",
            },
        },
        "regulatory": {
            "csv_loaded": len(_reg_db.all_records) > 0 if (_reg_db := get_reg_db()) else False,
            "verified_records": len(get_reg_db().all_records) if (_reg_db := get_reg_db()) else 0,
            "quarantined_excluded": get_reg_db().quarantined_count if (_reg_db := get_reg_db()) else 0,
        },
    }
    
    # Add integrations in debug mode only
    if settings.debug:
        payload["integrations"] = {
            "gemini_configured": bool(settings.gemini_api_key),
            "usda_configured": bool(settings.usda_api_key),
        }
        payload["settings"] = {
            "debug": settings.debug,
            "cors_origins": settings.cors_origins,
            "rate_limits": {
                "guest_daily_scans": settings.guest_daily_scan_limit,
                "free_daily_scans": settings.free_daily_scan_limit,
                "premium_daily_scans": settings.premium_daily_scan_limit,
            },
        }
    
    # Add medical disclaimer
    payload["disclaimer"] = MEDICAL_DISCLAIMER
    
    return payload


def _postgres_ok() -> bool:
    try:
        from sqlalchemy import text
        from lps.shared.db.postgres import get_engine
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@app.get("/api/v1/meta/disclaimer")
async def disclaimer() -> dict:
    return {"disclaimer": MEDICAL_DISCLAIMER}


def create_app() -> FastAPI:
    return app
