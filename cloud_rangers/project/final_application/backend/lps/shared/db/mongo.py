
"""
MongoDB client for product and ingredient documents.
"""
from __future__ import annotations

from functools import lru_cache
import os

from pymongo import MongoClient
from pymongo.database import Database


from lps.core.config import get_settings


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:

    """Create a Mongo client.

    During unit tests we must not require a running MongoDB instance.
    """
    settings = get_settings()

    # Test harness guard (prevents connecting to localhost:27017 during CI).
    # For test execution we may still import repository/service layers at import time;
    # therefore, we must not raise during client construction.
    if os.getenv("LPS_DISABLE_MONGODB_FOR_TESTS", "").lower() in {"1", "true", "yes"}:
        # Return a client object without triggering any network activity.
        # Only health checks/repository calls should decide what to do.
        return MongoClient("mongodb://localhost:27017", connect=False)

    return MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=3000)





def get_mongo_db() -> Database:
    settings = get_settings()
    return get_mongo_client()[settings.mongodb_url.rsplit("/", 1)[-1]]


def mongo_ping() -> bool:
    # During tests we must not attempt real network calls.
    if os.getenv("LPS_DISABLE_MONGODB_FOR_TESTS", "").lower() in {"1", "true", "yes"}:
        return False

    try:
        get_mongo_client().admin.command("ping")
        return True
    except Exception:
        return False

