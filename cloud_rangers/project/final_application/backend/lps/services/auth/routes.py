from __future__ import annotations

from fastapi import APIRouter, Depends

from lps.services.auth.service import AuthService
from lps.shared.schemas.auth import (
    AuthResponse,
    GuestAuthRequest,
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
)
from lps.gateway.dependencies import get_auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, auth: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return auth.register(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, auth: AuthService = Depends(get_auth_service)) -> AuthResponse:
    return auth.login(payload)


@router.post("/guest", response_model=AuthResponse)
def guest_login(
    _payload: GuestAuthRequest | None = None,
    auth: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return auth.guest_login()


@router.post("/refresh", response_model=AuthResponse)
def refresh_token(
    payload: TokenRefreshRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    return auth.refresh(payload.refresh_token)
