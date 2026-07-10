
"""
Pytest configuration for LPS backend tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault(
    "DATABASE_URL",
    # Keep URL in forward-slash format. Path must be URL-escaped-free.
    "sqlite:///" + str((BACKEND_DIR / "test_lps.db").resolve()).replace("\\", "/"),
)

# Prevent MongoDB from trying to connect to localhost:27017 during tests.
os.environ.setdefault("LPS_DISABLE_MONGODB_FOR_TESTS", "1")




os.environ.setdefault("JWT_SECRET", "super_secure_test_jwt_secret_key_12345")
os.environ.setdefault("FLASK_DEBUG", "true")

from lps.core.config import get_settings  # noqa: E402
from lps.shared.db.postgres import Base, SessionLocal, get_engine, init_db, reset_db_connections  # noqa: E402
from sqlalchemy.orm import close_all_sessions

get_settings.cache_clear()
reset_db_connections()


@pytest.fixture(autouse=True)
def _reset_db_per_test():
    # Keep schema stable across tests; only isolate *data*.
    # Dropping/recreating tables in teardown is causing cross-test race conditions
    # and SQLite "database is locked" errors.
    get_settings.cache_clear()
    reset_db_connections()
    init_db()
    yield

    close_all_sessions()

    engine = get_engine()
    # Deterministically remove rows from all mapped tables.
    # SQLite can throw "database is locked" if another thread/request still holds a connection.
    # Keep retries small to avoid long test hangs.
    import time

    for attempt in range(10):
        try:
            with engine.begin() as conn:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(table.delete())
            break
        except Exception:
            if attempt == 9:
                raise
            time.sleep(0.05)

    reset_db_connections()




@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
