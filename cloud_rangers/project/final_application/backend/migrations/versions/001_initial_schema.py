"""Initial user, profile, and subscription schema.

Revision ID: 001
Revises:
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("auth_provider", sa.String(length=20), nullable=False),
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("allergies", sa.JSON(), nullable=False),
        sa.Column("health_conditions", sa.JSON(), nullable=False),
        sa.Column("dietary_preference", sa.String(length=50), nullable=True),
        sa.Column("pregnancy_status", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fitness_goals", sa.JSON(), nullable=False),
        sa.Column("sensitivities", sa.Text(), nullable=True),
        sa.Column("other_allergy", sa.String(length=255), nullable=True),
        sa.Column("other_diet", sa.String(length=255), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("scans_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scans_reset_date", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
