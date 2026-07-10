"""
Authentication business logic.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from lps.core.config import get_settings
from lps.shared.models.user import Subscription, User, UserProfile
from lps.shared.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from lps.shared.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_expiry_seconds,
)
from lps.shared.security.password import hash_password, verify_password
from lps.shared.db.redis_client import get_redis, redis_ping

_FALLBACK_REFRESH_STORE: dict[str, str] = {}


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def _store_refresh_token(self, user_id: uuid.UUID, refresh_token: str) -> None:
        if redis_ping():
            key = f"refresh:{refresh_token}"
            get_redis().setex(key, get_token_expiry_seconds(), str(user_id))
        else:
            _FALLBACK_REFRESH_STORE[refresh_token] = str(user_id)

    def _resolve_refresh_token(self, refresh_token: str) -> uuid.UUID:
        user_id = None
        if redis_ping():
            user_id = get_redis().get(f"refresh:{refresh_token}")
        else:
            user_id = _FALLBACK_REFRESH_STORE.get(refresh_token)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        return uuid.UUID(user_id)

    def _revoke_refresh_token(self, refresh_token: str) -> None:
        if redis_ping():
            get_redis().delete(f"refresh:{refresh_token}")
        else:
            _FALLBACK_REFRESH_STORE.pop(refresh_token, None)

    def _create_subscription(self, user_id: uuid.UUID, tier: str) -> Subscription:
        sub = Subscription(user_id=user_id, tier=tier, scans_today=0, scans_reset_date=date.today())
        self.db.add(sub)
        return sub

    def _build_auth_response(self, user: User, refresh_token: str) -> AuthResponse:
        access = create_access_token(user.id, is_guest=user.is_guest)
        tier = user.subscription.tier if user.subscription else ("guest" if user.is_guest else "free")
        return AuthResponse(
            access_token=access,
            refresh_token=refresh_token,
            expires_in=self.settings.access_token_expire_minutes * 60,
            user=UserOut(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_guest=user.is_guest,
                tier=tier,
            ),
        )

    def register(self, payload: RegisterRequest) -> AuthResponse:
        if not payload.terms_accepted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Terms must be accepted")

        existing = self.db.query(User).filter(User.email == payload.email.lower(), User.deleted_at.is_(None)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            full_name=payload.full_name.strip(),
            auth_provider="email",
            is_guest=False,
            terms_accepted_at=datetime.now(timezone.utc),
        )
        self.db.add(user)
        self.db.flush()

        self.db.add(UserProfile(user_id=user.id))
        self._create_subscription(user.id, "free")

        refresh = create_refresh_token()
        self._store_refresh_token(user.id, refresh)
        self.db.commit()
        self.db.refresh(user)
        _ = user.subscription
        return self._build_auth_response(user, refresh)

    def login(self, payload: LoginRequest) -> AuthResponse:
        user = self.db.query(User).filter(
            User.email == payload.email.lower(),
            User.deleted_at.is_(None),
            User.is_guest.is_(False),
        ).first()
        if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        refresh = create_refresh_token()
        self._store_refresh_token(user.id, refresh)
        return self._build_auth_response(user, refresh)

    def guest_login(self) -> AuthResponse:
        user = User(
            email=None,
            password_hash=None,
            full_name="Guest User",
            auth_provider="guest",
            is_guest=True,
        )
        self.db.add(user)
        self.db.flush()
        self._create_subscription(user.id, "guest")
        refresh = create_refresh_token()
        self._store_refresh_token(user.id, refresh)
        self.db.commit()
        self.db.refresh(user)
        return self._build_auth_response(user, refresh)

    def refresh(self, refresh_token: str) -> AuthResponse:
        user_id = self._resolve_refresh_token(refresh_token)
        user = self.db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        self._revoke_refresh_token(refresh_token)
        new_refresh = create_refresh_token()
        self._store_refresh_token(user.id, new_refresh)
        return self._build_auth_response(user, new_refresh)

    def get_user_from_token(self, token: str) -> User:
        try:
            payload = decode_token(token)
            user_id = uuid.UUID(payload["sub"])
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

        user = self.db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
