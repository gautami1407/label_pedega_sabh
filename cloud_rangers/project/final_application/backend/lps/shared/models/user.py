"""
PostgreSQL ORM models for users, profiles, and subscriptions.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lps.shared.db.postgres import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), default="email")
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False)
    subscription: Mapped["Subscription | None"] = relationship(back_populates="user", uselist=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, index=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    allergies: Mapped[list] = mapped_column(JSON, default=list)
    health_conditions: Mapped[list] = mapped_column(JSON, default=list)
    dietary_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pregnancy_status: Mapped[bool] = mapped_column(Boolean, default=False)
    fitness_goals: Mapped[list] = mapped_column(JSON, default=list)
    sensitivities: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_allergy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    other_diet: Mapped[str | None] = mapped_column(String(255), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="profile")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(20), default="free")
    scans_today: Mapped[int] = mapped_column(Integer, default=0)
    scans_reset_date: Mapped[date] = mapped_column(Date, default=date.today)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="subscription")
