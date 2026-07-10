from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    terms_accepted: bool = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GuestAuthRequest(BaseModel):
    device_id: str | None = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str | None
    full_name: str | None
    is_guest: bool
    tier: str

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ConsentRecord(BaseModel):
    consent_type: str
    version: str
    granted_at: datetime
