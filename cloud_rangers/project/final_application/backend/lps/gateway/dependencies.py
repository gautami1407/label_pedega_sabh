"""
FastAPI dependency injection helpers.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from lps.services.auth.service import AuthService
from lps.shared.db.postgres import get_db
from lps.shared.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth: AuthService = Depends(get_auth_service),
) -> User | None:
    if not credentials:
        return None
    return auth.get_user_from_token(credentials.credentials)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth: AuthService = Depends(get_auth_service),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return auth.get_user_from_token(credentials.credentials)


def get_user_tier(user: User | None) -> str:
    if not user:
        return "guest"
    if user.subscription:
        return user.subscription.tier
    return "guest" if user.is_guest else "free"
