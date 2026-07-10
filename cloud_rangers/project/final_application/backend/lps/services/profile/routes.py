from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from lps.gateway.dependencies import get_current_user
from lps.services.profile.service import ProfileService
from lps.shared.db.postgres import get_db
from lps.shared.models.user import User
from lps.shared.schemas.profile import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    return ProfileService(db).get_profile(user.id)


@router.put("/profile", response_model=ProfileOut)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    return ProfileService(db).update_profile(user.id, payload)
