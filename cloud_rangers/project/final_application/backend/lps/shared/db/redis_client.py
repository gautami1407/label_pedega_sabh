"""
Redis client for cache, sessions, and rate limiting.
"""
from __future__ import annotations

from functools import lru_cache

import redis

from lps.core.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def redis_ping() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False
