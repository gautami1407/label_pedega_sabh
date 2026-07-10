"""
Redis-backed product data cache with file-system fallback.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

from lps.shared.db.redis_client import get_redis, redis_ping

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".product_checker_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_TTL = 86400


class ProductCache:
    """Two-tier cache: Redis primary, local filesystem fallback."""

    def __init__(self, ttl: int = DEFAULT_TTL) -> None:
        self.ttl = ttl
        self._redis_available = redis_ping()

    def _redis_key(self, key: str, src: str) -> str:
        digest = hashlib.md5(key.encode()).hexdigest()
        return f"cache:product:{src}:{digest}"

    def _file_path(self, key: str, src: str) -> str:
        digest = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{src}_{digest}.json")

    def get(self, key: str, src: str) -> Any | None:
        if self._redis_available:
            try:
                raw = get_redis().get(self._redis_key(key, src))
                if raw:
                    payload = json.loads(raw)
                    if time.time() - payload.get("cache_time", 0) <= self.ttl:
                        return payload.get("data")
            except Exception as exc:
                logger.warning("Redis cache read failed: %s", exc)

        path = self._file_path(key, src)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    payload = json.load(handle)
                if time.time() - payload.get("cache_time", 0) <= self.ttl:
                    return payload.get("data")
            except Exception:
                pass
        return None

    def set(self, key: str, src: str, data: Any) -> None:
        payload = {"data": data, "cache_time": time.time()}

        if self._redis_available:
            try:
                get_redis().setex(
                    self._redis_key(key, src),
                    self.ttl,
                    json.dumps(payload),
                )
            except Exception as exc:
                logger.warning("Redis cache write failed: %s", exc)

        try:
            with open(self._file_path(key, src), "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
        except Exception as exc:
            logger.warning("File cache write failed: %s", exc)
