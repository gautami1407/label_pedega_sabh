"""
JWT access and refresh token utilities.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from lps.core.config import get_settings


def create_access_token(user_id: uuid.UUID, *, is_guest: bool = False) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "type": "guest" if is_guest else "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_token_expiry_seconds() -> int:
    settings = get_settings()
    return settings.refresh_token_expire_days * 86400


def is_token_valid(token: str) -> bool:
    try:
        decode_token(token)
        return True
    except JWTError:
        return False
