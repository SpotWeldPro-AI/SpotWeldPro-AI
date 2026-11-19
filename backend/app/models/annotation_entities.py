"""
VISION-P3E: Annotation and dataset remediation entities.

Tables:
  weld_annotations         — one record per annotated image (or image to be annotated)
  annotation_findings      — per-defect finding within one annotation
  annotation_reviews       — reviewer decision log for each annotation
  annotation_audit_entries — immutable audit trail (every state change)
  conflict_adjudications   — human adjudication of 173 label-conflict duplicate pairs
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WeldAnnotation(Base):
    """
    Master annotation record for a single weld image.

    Design rules:
    - `image_path` is the absolute path to the ORIGINAL image (read-only reference).
      Original images MUST NOT be modified.
    - `roi_crop_path` is the path to the ROI-cropped derivative (may be None until cropped).
    - review_status state machine: DRAFT → SUBMITTED → APPROVED / REJECTED / NEEDS_REVISION
    - export_eligible is True only when status=APPROVED and both roi/markup flags are set.
    - Self-approval is prohibited at the service layer (annotator_id != reviewer_id required
      before transitioning to APPROVED).
    """
    __tablename__ = "weld_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ── Image provenance ──────────────────────────────────────────────────────
    image_path: Mapped[str] = mapped_column(Text, unique=True, index=True,
                                             comment="Absolute path to ORIGINAL image; read-only")
    roi_crop_path: Mapped[str | None] = mapped_column(Text, nullable=True, default=None,
                                                       comment="Path to ROI-cropped derivative; None until created")
    image_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True,
                                                    comment="SHA1 hex (16 chars) for duplicate detection")
    weld_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True,
                                                  comment="Production weld identifier (optional)")
    source_archive: Mapped[str | None] = mapped_column(String(300), nullable=True,
                                                         comment="Source zip/archive name")
    split: Mapped[str] = mapped_column(String(20), default="unknown",
                                        comment="train / val / test / unknown")

    # ── Quality metadata ──────────────────────────────────────────────────────
    label_provenance: Mapped[str] = mapped_column(String(80), default="SURFACE_OBSERVATION",
                                                   comment="SURFACE_OBSERVATION / DESTRUCTIVE_TEST / ACCEPTED_REFERENCE")
    contamination_level: Mapped[str] = mapped_column(String(20), default="UNKNOWN",
                                                      comment="CLEAN / LOW / MEDIUM / HIGH / UNKNOWN")
    max_markup_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    is_roi_cropped: Mapped[bool] = mapped_column(Boolean, default=False)
    annotation_markup_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    image_width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Authorship and review status ──────────────────────────────────────────
    annotator_id: Mapped[str] = mapped_column(String(200), index=True,
                                               comment="User email of the annotator")
    review_status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True,
                                                comment="DRAFT / SUBMITTED / APPROVED / REJECTED / NEEDS_REVISION")
    taxonomy_version: Mapped[str] = mapped_column(String(30), default="P3D-1.0")

    # ── Export eligibility ────────────────────────────────────────────────────
    export_eligible: Mapped[bool] = mapped_column(Boolean, default=False,
                                                   comment="True when APPROVED + ROI + markup removed")
    export_version: Mapped[str | None] = mapped_column(String(50), nullable=True,
                                                         comment="Dataset export version tag this record was last included in")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # ── Relationships ─────────────────────────────────────────────────────────
    findings: Mapped[list[AnnotationFinding]] = relationship(
        back_populates="annotation", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[AnnotationReview]] = relationship(
        back_populates="annotation", cascade="all, delete-orphan"
    )
    audit_entries: Mapped[list[AnnotationAuditEntry]] = relationship(
        back_populates="annotation", cascade="all, delete-orphan"
    )

    def is_training_eligible(self) -> bool:
        """Minimum conditions for training inclusion."""
        if self.review_status != "APPROVED":
            return False
        if not self.is_roi_cropped or not self.annotation_markup_removed:
            return False
        if not self.findings:
            return False
        codes = {f.defect_code for f in self.findings}
        # generic_bad alone is not usable
        return codes != {"generic_bad"}

    def recalculate_export_eligibility(self) -> None:
        self.export_eligible = self.is_training_eligible()


class AnnotationFinding(Base):
    """
    One detected defect within a single annotation.

    Multi-label: an annotation can have multiple findings.
    region_data stores:
      BBOX    → {"x": int, "y": int, "w": int, "h": int}
      POLYGON → {"points": [[x, y], ...]}
      POINT   → {"x": int, "y": int}
      WHOLE_IMAGE → {}
    """
    __tablename__ = "annotation_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    annotation_id: Mapped[int] = mapped_column(ForeignKey("weld_annotations.id", ondelete="CASCADE"), index=True)

    defect_code: Mapped[str] = mapped_column(String(80), index=True, comment="DefectCode key from taxonomy")
    name_tr: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))
    region_type: Mapped[str] = mapped_column(String(20), default="BBOX",
                                              comment="BBOX / POLYGON / POINT / WHOLE_IMAGE")
    region_data: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, comment="0–1; 0 = human annotated without explicit score")
    confidence_source: Mapped[str] = mapped_column(String(30), default="HUMAN_ANNOTATION")
    requires_physical_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    is_surface_classifiable: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    annotation: Mapped[WeldAnnotation] = relationship(back_populates="findings")


class AnnotationReview(Base):
    """
    One reviewer decision for an annotation.

    Multiple reviews may exist per annotation (re-review after NEEDS_REVISION).
    reviewer_id MUST NOT equal the annotation's annotator_id when decision=APPROVED.
    This is enforced at the service layer.
    """
    __tablename__ = "annotation_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    annotation_id: Mapped[int] = mapped_column(ForeignKey("weld_annotations.id", ondelete="CASCADE"), index=True)

    reviewer_id: Mapped[str] = mapped_column(String(200), index=True)
    decision: Mapped[str] = mapped_column(String(30),
                                           comment="APPROVED / REJECTED / NEEDS_REVISION")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    previous_status: Mapped[str] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    annotation: Mapped[WeldAnnotation] = relationship(back_populates="reviews")


class AnnotationAuditEntry(Base):
    """
    Immutable audit trail: every state change is appended here.
    Entries are never deleted or modified.
    """
    __tablename__ = "annotation_audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    annotation_id: Mapped[int] = mapped_column(ForeignKey("weld_annotations.id", ondelete="CASCADE"), index=True)

    actor_id: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80),
                                         comment="CREATED / FINDING_ADDED / FINDING_REMOVED / "
                                                 "SUBMITTED / APPROVED / REJECTED / NEEDS_REVISION / REVISED / EXPORTED")
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    annotation: Mapped[WeldAnnotation] = relationship(back_populates="audit_entries")


class PhysicalTestEvidence(Base):
    """
    VISION-DATA-REAL-02 E4: Physical test evidence record.

    Associates a qualified physical test result with a weld image or weld_id.

    Design rules:
    - `image_path` references the ORIGINAL image path (never modified).
    - `test_method` must be a qualified physical or NDT method; surface observations
      MUST NOT be recorded here — use WeldAnnotation.label_provenance for those.
    - `nugget_diameter_mm` requires DESTRUCTIVE_TEST or UT_SCAN method.
    - `evidence_quality` VERIFIED requires a report reference number.
    - No automatic training gate changes occur; E4 gate requires QUALITY_ENGINEER sign-off.
    """
    __tablename__ = "physical_test_evidence"
    __table_args__ = (
        UniqueConstraint("image_path", "test_method", "test_date", name="uq_evidence_image_method_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ── Weld identity ──────────────────────────────────────────────────────────
    image_path: Mapped[str] = mapped_column(Text, index=True,
                                             comment="Absolute path to ORIGINAL image (read-only reference)")
    weld_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True,
                                                 comment="Production weld identifier — links to WeldAnnotation.weld_id")

    # ── Test method ────────────────────────────────────────────────────────────
    test_method: Mapped[str] = mapped_column(
        String(50), index=True,
        comment=(
            "CROSS_SECTION | PEEL_TEST | CHISEL_TEST | UT_SCAN | XRF | RADIOGRAPHIC | OTHER. "
            "SURFACE_OBSERVATION is explicitly excluded — use WeldAnnotation for that."
        ),
    )

    # ── Test context ───────────────────────────────────────────────────────────
    test_date: Mapped[str | None] = mapped_column(String(30), nullable=True,
                                                   comment="ISO 8601 date YYYY-MM-DD")
    test_operator: Mapped[str | None] = mapped_column(String(200), nullable=True,
                                                       comment="Name or badge of the test technician")
    test_report_ref: Mapped[str | None] = mapped_column(String(400), nullable=True,
                                                          comment="Report or document reference number")
    test_facility: Mapped[str | None] = mapped_column(String(300), nullable=True,
                                                        comment="Lab or facility name")

    # ── Measurements ──────────────────────────────────────────────────────────
    nugget_diameter_mm: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Nugget diameter in mm (CROSS_SECTION or UT_SCAN only; None otherwise)",
    )
    nugget_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed_defect_codes: Mapped[str] = mapped_column(
        String(500), default="",
        comment="Comma-separated DefectCode values confirmed by this physical test",
    )

    # ── Verdict ────────────────────────────────────────────────────────────────
    verdict: Mapped[str] = mapped_column(
        String(30), default="UNREVIEWED", index=True,
        comment="ACCEPTABLE | REJECTABLE | INCONCLUSIVE | UNREVIEWED",
    )
    acceptance_standard: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Standard used for verdict (e.g. ISO 15614-12, AWS D8.1, OEM-123)",
    )

    # ── Evidence quality ───────────────────────────────────────────────────────
    evidence_quality: Mapped[str] = mapped_column(
        String(30), default="UNVERIFIED", index=True,
        comment="VERIFIED (report ref required) | UNVERIFIED | INSUFFICIENT",
    )
    notes: Mapped[str] = mapped_column(Text, default="")

    # ── Authorship ─────────────────────────────────────────────────────────────
    created_by: Mapped[str] = mapped_column(String(200), index=True, comment="User email")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)


class ConflictAdjudication(Base):
    """
    Human adjudication record for a label-conflict duplicate pair.

    Populated from DUPLICATE_MANIFEST.csv (173 label-conflict pairs).
    adjudicator_id is None until a human makes a decision.
    decision values: PENDING / KEEP_A / KEEP_B / KEEP_BOTH / EXCLUDE_BOTH
    """
    __tablename__ = "conflict_adjudications"
    __table_args__ = (UniqueConstraint("sha1_16", "path_a", "path_b", name="uq_conflict_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha1_16: Mapped[str] = mapped_column(String(32), index=True)
    path_a: Mapped[str] = mapped_column(Text)
    path_b: Mapped[str] = mapped_column(Text)
    label_a: Mapped[str] = mapped_column(String(80))
    label_b: Mapped[str] = mapped_column(String(80))
    split_a: Mapped[str] = mapped_column(String(20))
    split_b: Mapped[str] = mapped_column(String(20))
    conflict_type: Mapped[str] = mapped_column(String(50),
                                                comment="LABEL_CONFLICT / BOTH (cross-split + label conflict)")
    source_archive_a: Mapped[str] = mapped_column(String(300), default="")
    source_archive_b: Mapped[str] = mapped_column(String(300), default="")

    # ── Adjudication outcome ──────────────────────────────────────────────────
    decision: Mapped[str] = mapped_column(String(30), default="PENDING", index=True,
                                           comment="PENDING / KEEP_A / KEEP_B / KEEP_BOTH / EXCLUDE_BOTH")
    adjudicator_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    adjudication_notes: Mapped[str] = mapped_column(Text, default="")
    adjudicated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
