"""
User health profile service.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from lps.shared.models.user import UserProfile
from lps.shared.schemas.profile import ProfileOut, ProfileUpdate


class ProfileService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_profile(self, user_id: uuid.UUID) -> ProfileOut:
        profile = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id)
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return ProfileOut.from_orm_profile(profile)

    def update_profile(self, user_id: uuid.UUID, payload: ProfileUpdate) -> ProfileOut:
        profile = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id)
            self.db.add(profile)

        data = payload.model_dump(exclude_unset=True)
        height = data.pop("height", None)
        weight = data.pop("weight", None)

        for field, value in data.items():
            setattr(profile, field, value)
        if height is not None:
            profile.height_cm = height
        if weight is not None:
            profile.weight_kg = weight

        self.db.commit()
        self.db.refresh(profile)
        return ProfileOut.from_orm_profile(profile)

    def get_preferences(self, user_id: uuid.UUID) -> dict:
        return self.get_profile(user_id).to_preferences_dict()
