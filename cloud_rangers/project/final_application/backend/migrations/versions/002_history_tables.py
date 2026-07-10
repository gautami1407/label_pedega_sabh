"""Scan history, favorites, and comparison history tables.

Revision ID: 002
Revises: 001
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scan_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("barcode", sa.String(length=50), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("attention_level", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=True),
        sa.Column("report_snapshot", sa.JSON(), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_history_user_id", "scan_history", ["user_id"])
    op.create_index("ix_scan_history_barcode", "scan_history", ["barcode"])
    op.create_index("ix_scan_history_scanned_at", "scan_history", ["scanned_at"])

    op.create_table(
        "favorites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("barcode", sa.String(length=50), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("product_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])
    op.create_index("ix_favorites_barcode", "favorites", ["barcode"])

    op.create_table(
        "comparison_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_a_barcode", sa.String(length=50), nullable=False),
        sa.Column("product_b_barcode", sa.String(length=50), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comparison_history_user_id", "comparison_history", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_comparison_history_user_id", table_name="comparison_history")
    op.drop_table("comparison_history")
    op.drop_index("ix_favorites_barcode", table_name="favorites")
    op.drop_index("ix_favorites_user_id", table_name="favorites")
    op.drop_table("favorites")
    op.drop_index("ix_scan_history_scanned_at", table_name="scan_history")
    op.drop_index("ix_scan_history_barcode", table_name="scan_history")
    op.drop_index("ix_scan_history_user_id", table_name="scan_history")
    op.drop_table("scan_history")
