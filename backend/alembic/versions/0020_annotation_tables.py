"""add annotation tables (P3E vision pipeline)

Revision ID: 0020_annotation_tables
Revises: 0019_import_batches
Create Date: 2026-11-13

Adds the five annotation tables introduced in P3E:
  weld_annotations, annotation_findings, annotation_reviews,
  annotation_audit_entries, conflict_adjudications.

These tables were previously created via Base.metadata.create_all() on
databases bootstrapped during development (e.g. spotweld_gamic.db).
This migration makes them part of the Alembic-managed schema so that
fresh deployments and PostgreSQL environments create them correctly.

Reconciliation guard: if weld_annotations already exists (create_all
ran), upgrade() skips all DDL and returns.  The alembic_version stamp is
still advanced to 0020_annotation_tables, so the migration chain stays
consistent without touching any existing annotation data.

IMPORTANT: downgrade() drops all five tables and their indexes.  It is
destructive and should not be run on a database containing annotation
data you want to keep.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0020_annotation_tables"
down_revision = "0019_import_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "weld_annotations" in existing:
        # Tables were created via Base.metadata.create_all(); nothing to do.
        return

    # ── weld_annotations ─────────────────────────────────────────────────────
    op.create_table(
        "weld_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=False),
        sa.Column("roi_crop_path", sa.Text(), nullable=True),
        sa.Column("image_hash", sa.String(32), nullable=True),
        sa.Column("weld_id", sa.String(200), nullable=True),
        sa.Column("source_archive", sa.String(300), nullable=True),
        sa.Column("split", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("label_provenance", sa.String(80), nullable=False,
                  server_default="SURFACE_OBSERVATION"),
        sa.Column("contamination_level", sa.String(20), nullable=False,
                  server_default="UNKNOWN"),
        sa.Column("max_markup_ratio", sa.Float(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("is_roi_cropped", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("annotation_markup_removed", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("image_width_px", sa.Integer(), nullable=True),
        sa.Column("image_height_px", sa.Integer(), nullable=True),
        sa.Column("annotator_id", sa.String(200), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("taxonomy_version", sa.String(30), nullable=False,
                  server_default="P3D-1.0"),
        sa.Column("export_eligible", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("export_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_path", name="uq_weld_annotations_image_path"),
    )
    op.create_index("ix_weld_annotations_id", "weld_annotations", ["id"])
    op.create_index("ix_weld_annotations_image_path", "weld_annotations", ["image_path"])
    op.create_index("ix_weld_annotations_image_hash", "weld_annotations", ["image_hash"])
    op.create_index("ix_weld_annotations_weld_id", "weld_annotations", ["weld_id"])
    op.create_index("ix_weld_annotations_annotator_id", "weld_annotations", ["annotator_id"])
    op.create_index("ix_weld_annotations_review_status", "weld_annotations", ["review_status"])

    # ── annotation_findings ───────────────────────────────────────────────────
    op.create_table(
        "annotation_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("annotation_id", sa.Integer(), nullable=False),
        sa.Column("defect_code", sa.String(80), nullable=False),
        sa.Column("name_tr", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("region_type", sa.String(20), nullable=False, server_default="BBOX"),
        sa.Column("region_data", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence_source", sa.String(30), nullable=False,
                  server_default="HUMAN_ANNOTATION"),
        sa.Column("requires_physical_confirmation", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("is_surface_classifiable", sa.Boolean(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["annotation_id"], ["weld_annotations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_annotation_findings_id", "annotation_findings", ["id"])
    op.create_index(
        "ix_annotation_findings_annotation_id", "annotation_findings", ["annotation_id"]
    )
    op.create_index(
        "ix_annotation_findings_defect_code", "annotation_findings", ["defect_code"]
    )

    # ── annotation_reviews ────────────────────────────────────────────────────
    op.create_table(
        "annotation_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("annotation_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.String(200), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("previous_status", sa.String(30), nullable=False),
        sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["annotation_id"], ["weld_annotations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_annotation_reviews_id", "annotation_reviews", ["id"])
    op.create_index(
        "ix_annotation_reviews_annotation_id", "annotation_reviews", ["annotation_id"]
    )
    op.create_index(
        "ix_annotation_reviews_reviewer_id", "annotation_reviews", ["reviewer_id"]
    )

    # ── annotation_audit_entries ──────────────────────────────────────────────
    op.create_table(
        "annotation_audit_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("annotation_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["annotation_id"], ["weld_annotations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_annotation_audit_entries_id", "annotation_audit_entries", ["id"]
    )
    op.create_index(
        "ix_annotation_audit_entries_annotation_id",
        "annotation_audit_entries",
        ["annotation_id"],
    )

    # ── conflict_adjudications ────────────────────────────────────────────────
    op.create_table(
        "conflict_adjudications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sha1_16", sa.String(32), nullable=False),
        sa.Column("path_a", sa.Text(), nullable=False),
        sa.Column("path_b", sa.Text(), nullable=False),
        sa.Column("label_a", sa.String(80), nullable=False),
        sa.Column("label_b", sa.String(80), nullable=False),
        sa.Column("split_a", sa.String(20), nullable=False),
        sa.Column("split_b", sa.String(20), nullable=False),
        sa.Column("conflict_type", sa.String(50), nullable=False),
        sa.Column("source_archive_a", sa.String(300), nullable=False, server_default=""),
        sa.Column("source_archive_b", sa.String(300), nullable=False, server_default=""),
        sa.Column("decision", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("adjudicator_id", sa.String(200), nullable=True),
        sa.Column("adjudication_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("adjudicated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha1_16", "path_a", "path_b", name="uq_conflict_pair"),
    )
    op.create_index(
        "ix_conflict_adjudications_id", "conflict_adjudications", ["id"]
    )
    op.create_index(
        "ix_conflict_adjudications_sha1_16", "conflict_adjudications", ["sha1_16"]
    )
    op.create_index(
        "ix_conflict_adjudications_decision", "conflict_adjudications", ["decision"]
    )
    op.create_index(
        "ix_conflict_adjudications_adjudicator_id",
        "conflict_adjudications",
        ["adjudicator_id"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order (children before parent).
    # WARNING: destructive — annotation data will be lost.
    op.drop_index("ix_conflict_adjudications_adjudicator_id",
                  table_name="conflict_adjudications")
    op.drop_index("ix_conflict_adjudications_decision",
                  table_name="conflict_adjudications")
    op.drop_index("ix_conflict_adjudications_sha1_16",
                  table_name="conflict_adjudications")
    op.drop_index("ix_conflict_adjudications_id",
                  table_name="conflict_adjudications")
    op.drop_table("conflict_adjudications")

    op.drop_index("ix_annotation_audit_entries_annotation_id",
                  table_name="annotation_audit_entries")
    op.drop_index("ix_annotation_audit_entries_id",
                  table_name="annotation_audit_entries")
    op.drop_table("annotation_audit_entries")

    op.drop_index("ix_annotation_reviews_reviewer_id",
                  table_name="annotation_reviews")
    op.drop_index("ix_annotation_reviews_annotation_id",
                  table_name="annotation_reviews")
    op.drop_index("ix_annotation_reviews_id", table_name="annotation_reviews")
    op.drop_table("annotation_reviews")

    op.drop_index("ix_annotation_findings_defect_code",
                  table_name="annotation_findings")
    op.drop_index("ix_annotation_findings_annotation_id",
                  table_name="annotation_findings")
    op.drop_index("ix_annotation_findings_id", table_name="annotation_findings")
    op.drop_table("annotation_findings")

    op.drop_index("ix_weld_annotations_review_status",
                  table_name="weld_annotations")
    op.drop_index("ix_weld_annotations_annotator_id",
                  table_name="weld_annotations")
    op.drop_index("ix_weld_annotations_weld_id", table_name="weld_annotations")
    op.drop_index("ix_weld_annotations_image_hash",
                  table_name="weld_annotations")
    op.drop_index("ix_weld_annotations_image_path",
                  table_name="weld_annotations")
    op.drop_index("ix_weld_annotations_id", table_name="weld_annotations")
    op.drop_table("weld_annotations")
