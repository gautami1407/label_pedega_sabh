from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProfileUpdate(BaseModel):
    age: int | None = Field(default=None, ge=1, le=120)
    gender: str | None = Field(default=None, max_length=20)
    allergies: list[str] = Field(default_factory=list)
    health_conditions: list[str] = Field(default_factory=list)
    dietary_preference: str | None = Field(default=None, max_length=50)
    pregnancy_status: bool = False
    fitness_goals: list[str] = Field(default_factory=list)
    sensitivities: str | None = None
    other_allergy: str | None = None
    other_diet: str | None = None
    height: float | None = Field(default=None, ge=30, le=300)
    weight: float | None = Field(default=None, ge=1, le=500)

    @field_validator("allergies", "health_conditions", "fitness_goals", mode="before")
    @classmethod
    def normalize_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return [str(v) for v in value]


class ProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    age: int | None
    gender: str | None
    allergies: list[str]
    health_conditions: list[str]
    dietary_preference: str | None
    pregnancy_status: bool
    fitness_goals: list[str]
    sensitivities: str | None
    other_allergy: str | None
    other_diet: str | None
    height: float | None
    weight: float | None
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_profile(cls, profile) -> "ProfileOut":
        return cls(
            id=profile.id,
            user_id=profile.user_id,
            age=profile.age,
            gender=profile.gender,
            allergies=profile.allergies or [],
            health_conditions=profile.health_conditions or [],
            dietary_preference=profile.dietary_preference,
            pregnancy_status=profile.pregnancy_status,
            fitness_goals=profile.fitness_goals or [],
            sensitivities=profile.sensitivities,
            other_allergy=profile.other_allergy,
            other_diet=profile.other_diet,
            height=float(profile.height_cm) if profile.height_cm is not None else None,
            weight=float(profile.weight_kg) if profile.weight_kg is not None else None,
            updated_at=profile.updated_at,
        )

    def to_preferences_dict(self) -> dict:
        """Map to legacy analyzer preferences format."""
        return {
            "age": self.age,
            "gender": self.gender,
            "allergies": self.allergies,
            "health_conditions": self.health_conditions,
            "dietaryPreference": self.dietary_preference,
            "pregnancy_status": self.pregnancy_status,
            "fitness_goals": self.fitness_goals,
            "sensitivities": self.sensitivities,
            "otherAllergy": self.other_allergy,
            "otherDiet": self.other_diet,
            "height": self.height,
            "weight": self.weight,
        }
