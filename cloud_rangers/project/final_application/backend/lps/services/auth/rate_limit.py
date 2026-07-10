"""
Daily scan rate limiting by subscription tier.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from lps.core.config import get_settings
from lps.shared.db.redis_client import get_redis, redis_ping
from lps.shared.models.user import Subscription


TIER_LIMITS = {
    "guest": lambda s: s.guest_daily_scan_limit,
    "free": lambda s: s.free_daily_scan_limit,
    "premium": lambda _: None,
    "enterprise": lambda _: None,
}


class ScanRateLimiter:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def _limit_for_tier(self, tier: str) -> int | None:
        resolver = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        return resolver(self.settings)

    def _redis_key(self, user_id: uuid.UUID) -> str:
        return f"ratelimit:scans:{user_id}:{date.today().isoformat()}"

    def check_and_increment(self, user_id: uuid.UUID, tier: str) -> dict:
        limit = self._limit_for_tier(tier)
        if limit is None:
            return {"tier": tier, "scans_today": None, "limit": None, "remaining": None}

        if redis_ping():
            key = self._redis_key(user_id)
            current = int(get_redis().get(key) or 0)
            if current >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Daily scan limit reached ({limit}/day). Upgrade for unlimited scans.",
                )
            get_redis().incr(key)
            if current == 0:
                get_redis().expire(key, 86400)
            return {
                "tier": tier,
                "scans_today": current + 1,
                "limit": limit,
                "remaining": limit - current - 1,
            }

        sub = self.db.query(Subscription).filter(Subscription.user_id == user_id).first()
        if not sub:
            return {"tier": tier, "scans_today": 1, "limit": limit, "remaining": limit - 1}

        if sub.scans_reset_date != date.today():
            sub.scans_reset_date = date.today()
            sub.scans_today = 0

        if sub.scans_today >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily scan limit reached ({limit}/day). Upgrade for unlimited scans.",
            )

        sub.scans_today += 1
        self.db.commit()
        return {
            "tier": tier,
            "scans_today": sub.scans_today,
            "limit": limit,
            "remaining": limit - sub.scans_today,
        }
