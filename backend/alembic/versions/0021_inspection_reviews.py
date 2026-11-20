"""add inspection_reviews table (VISION-AI-REVIEW-01)

Revision ID: 0021_inspection_reviews
Revises: 0020_annotation_tables
Create Date: 2026-11-20

Adds the inspection_reviews table for engineer feedback on static inspection results.
Reconciliation guard: if the table already exists (create_all ran), upgrade() skips
DDL and advances only the alembic_version stamp.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0021_inspection_reviews"
down_revision = "0020_annotation_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "inspection_reviews" in set(inspector.get_table_names()):
        return

    op.create_table(
        "inspection_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inspection_id", sa.String(64), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_username", sa.String(200), nullable=False),
        sa.Column("reviewer_role", sa.String(80), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("inspection_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_training_label", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspection_reviews_inspection_id", "inspection_reviews", ["inspection_id"])
    op.create_index("ix_inspection_reviews_reviewer_id", "inspection_reviews", ["reviewer_id"])


def downgrade() -> None:
    op.drop_index("ix_inspection_reviews_reviewer_id", table_name="inspection_reviews")
    op.drop_index("ix_inspection_reviews_inspection_id", table_name="inspection_reviews")
    op.drop_table("inspection_reviews")
