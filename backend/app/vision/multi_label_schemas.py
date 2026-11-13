"""
VISION-P3D: Multi-label inspection schemas for spot weld defects.

A single weld image may exhibit multiple defects simultaneously
(e.g. spatter + burn-through, or misalignment + edge weld).
These schemas extend the Phase 1 StaticInspectionResult to support:
  - Multiple defect findings per image with per-finding confidence
  - Explicit observability and severity for each finding
  - Surface-visible vs internal-only distinction at result level
  - Training gate: result carries whether the taxonomy + data quality
    gates currently allow model training

No model weights are loaded here.  Confidence values are placeholders
until E1-E4 data quality gates (P3B/P3C) are resolved and a classifier
is trained and validated.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from app.vision.defect_taxonomy import (
    DefectCode,
    DefectSeverity,
    ObservabilityLevel,
    TAXONOMY_VERSION,
    get_taxonomy_entry,
)
from app.vision.schemas import ImageType, InspectionStatus, MeasurementSource


class ConfidenceSource(str, Enum):
    """
    How the confidence value was produced.

    CLASSIFIER        — Output of a trained, validated model (not available until
                        E1-E4 gates resolved and DatasetAudit APPROVED).
    RULE_BASED        — Deterministic rule (e.g. area threshold, contour score).
    HUMAN_ANNOTATION  — Confidence set by an annotator; treat as 1.0 when from
                        a qualified engineer, lower when crowdsourced.
    NOT_COMPUTED      — No confidence available; model not loaded or gate blocked.
    """
    CLASSIFIER = "CLASSIFIER"
    RULE_BASED = "RULE_BASED"
    HUMAN_ANNOTATION = "HUMAN_ANNOTATION"
    NOT_COMPUTED = "NOT_COMPUTED"


class DefectFinding(BaseModel):
    """
    One detected or annotated defect instance within a weld image.

    A DefectFinding does NOT imply that a model detected this defect.
    When source == NOT_COMPUTED the finding is a placeholder indicating that
    this defect class is in scope but cannot yet be evaluated.
    """
    defect_code: DefectCode
    name_tr: str = Field(description="Turkish name from taxonomy")
    name_en: str = Field(description="English name from taxonomy")
    observability: ObservabilityLevel
    severity: DefectSeverity
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Detection confidence 0–1; 0.0 when source is NOT_COMPUTED",
    )
    confidence_source: ConfidenceSource = ConfidenceSource.NOT_COMPUTED
    measurement_source: MeasurementSource = MeasurementSource.NOT_AVAILABLE
    bbox_pixels: Optional[Tuple[int, int, int, int]] = Field(
        default=None,
        description="x, y, width, height in pixels; None for whole-image findings",
    )
    requires_physical_confirmation: bool = Field(
        description="True when NDT or cross-section required for definitive verdict"
    )
    is_surface_classifiable: bool = Field(
        description="True when a surface-image classifier can be trained for this class"
    )
    annotation_region: str = Field(
        default="BBOX",
        description="BBOX | POLYGON | POINT | WHOLE_IMAGE — how to annotate this defect",
    )
    notes: List[str] = Field(default_factory=list)

    @classmethod
    def from_taxonomy(
        cls,
        code: DefectCode,
        confidence: float = 0.0,
        confidence_source: ConfidenceSource = ConfidenceSource.NOT_COMPUTED,
        measurement_source: MeasurementSource = MeasurementSource.NOT_AVAILABLE,
        bbox_pixels: Optional[Tuple[int, int, int, int]] = None,
        notes: Optional[List[str]] = None,
    ) -> "DefectFinding":
        """Construct a DefectFinding with taxonomy-sourced metadata."""
        entry = get_taxonomy_entry(code)
        return cls(
            defect_code=code,
            name_tr=entry.name_tr,
            name_en=entry.name_en,
            observability=entry.observability,
            severity=entry.severity,
            confidence=confidence,
            confidence_source=confidence_source,
            measurement_source=measurement_source,
            bbox_pixels=bbox_pixels,
            requires_physical_confirmation=entry.requires_physical_confirmation(),
            is_surface_classifiable=entry.surface_classifier_applicable,
            annotation_region=entry.annotation_region,
            notes=notes or [],
        )

    def is_critical(self) -> bool:
        return self.severity == DefectSeverity.CRITICAL

    def is_surface_visible(self) -> bool:
        return self.observability == ObservabilityLevel.SURFACE_VISIBLE

    def is_internal_only(self) -> bool:
        return self.observability in (
            ObservabilityLevel.NDT_REQUIRED,
            ObservabilityLevel.DESTRUCTIVE_ONLY,
        )


def _derive_overall_status(findings: List[DefectFinding]) -> InspectionStatus:
    """
    Derive overall weld status from a list of defect findings.

    Rules (in priority order):
      1. No findings or only OK finding → UNKNOWN (classifier not loaded; cannot confirm OK)
      2. Any CRITICAL finding → NOK
      3. Any HIGH finding → NOK
      4. Any MEDIUM finding → REVIEW
      5. Only LOW findings → REVIEW
      6. Only ACCEPT findings → OK (requires classifier confidence > 0)
    """
    non_ok = [f for f in findings if f.defect_code != DefectCode.OK]
    ok_findings = [f for f in findings if f.defect_code == DefectCode.OK]

    if not non_ok:
        if ok_findings and ok_findings[0].confidence > 0.0:
            return InspectionStatus.OK
        return InspectionStatus.UNKNOWN

    severities = {f.severity for f in non_ok}
    if DefectSeverity.CRITICAL in severities:
        return InspectionStatus.NOK
    if DefectSeverity.HIGH in severities:
        return InspectionStatus.NOK
    if DefectSeverity.MEDIUM in severities:
        return InspectionStatus.REVIEW
    return InspectionStatus.REVIEW


class MultiLabelInspectionResult(BaseModel):
    """
    Multi-label inspection result for a single weld image.

    Key additions over StaticInspectionResult:
      - defect_findings: list of zero or more DefectFinding instances
      - surface_detectable_count: how many findings are surface-visible
      - ndt_required_count: how many require NDT / cross-section
      - has_critical: True if any finding is CRITICAL severity
      - training_gate_open: False until DatasetAudit is APPROVED and E1-E4 resolved
    """
    inspection_id: str
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    image_type: ImageType
    taxonomy_version: str = Field(default=TAXONOMY_VERSION)
    overall_status: InspectionStatus
    defect_findings: List[DefectFinding] = Field(default_factory=list)

    # Aggregate counts (set by from_findings)
    total_findings: int = 0
    surface_detectable_count: int = 0
    ndt_required_count: int = 0
    has_critical: bool = False
    surface_classifier_applicable_count: int = 0

    # Training gate state — always False until E1-E4 resolved
    training_gate_open: bool = Field(
        default=False,
        description=(
            "True only when DatasetAudit.is_training_allowed() == True AND "
            "P3B/P3C E1-E4 data quality gates are resolved.  Currently False."
        ),
    )
    training_gate_note: str = Field(
        default=(
            "Training blocked: E1-E4 data quality gates (duplicate resolution, "
            "annotation cleanup, split regeneration, label provenance) not yet resolved. "
            "See docs/DATASET_CLEANING_REPORT.md."
        )
    )

    preprocessing_notes: List[str] = Field(default_factory=list)
    review_notes: List[str] = Field(default_factory=list)

    @classmethod
    def from_findings(
        cls,
        inspection_id: str,
        timestamp: str,
        image_type: ImageType,
        findings: List[DefectFinding],
        preprocessing_notes: Optional[List[str]] = None,
        review_notes: Optional[List[str]] = None,
    ) -> "MultiLabelInspectionResult":
        """Construct a result from a list of findings, deriving aggregate counts."""
        overall = _derive_overall_status(findings)
        return cls(
            inspection_id=inspection_id,
            timestamp=timestamp,
            image_type=image_type,
            overall_status=overall,
            defect_findings=findings,
            total_findings=len(findings),
            surface_detectable_count=sum(
                1 for f in findings if not f.is_internal_only()
            ),
            ndt_required_count=sum(
                1 for f in findings if f.is_internal_only()
            ),
            has_critical=any(f.is_critical() for f in findings),
            surface_classifier_applicable_count=sum(
                1 for f in findings if f.is_surface_classifiable
            ),
            training_gate_open=False,
            preprocessing_notes=preprocessing_notes or [],
            review_notes=review_notes or [],
        )

    def critical_findings(self) -> List[DefectFinding]:
        return [f for f in self.defect_findings if f.is_critical()]

    def surface_visible_findings(self) -> List[DefectFinding]:
        return [f for f in self.defect_findings if f.is_surface_visible()]

    def internal_findings(self) -> List[DefectFinding]:
        return [f for f in self.defect_findings if f.is_internal_only()]

    def requires_ndt(self) -> bool:
        return any(f.requires_physical_confirmation for f in self.defect_findings)

    def defect_codes(self) -> List[DefectCode]:
        return [f.defect_code for f in self.defect_findings]


class AnnotationRecord(BaseModel):
    """
    Ground-truth annotation for one weld image, authored by a qualified engineer.

    Supports multi-label: a single image may carry multiple DefectFinding entries.
    This record feeds into dataset audit and training pipelines once
    E1-E4 gates are resolved.
    """
    image_path: str
    annotator_id: str = Field(description="Engineer or reviewer identifier")
    annotation_date: str = Field(description="ISO 8601 date")
    image_type: ImageType
    findings: List[DefectFinding] = Field(default_factory=list)
    is_roi_cropped: bool = Field(
        default=False,
        description="True when the image has been cropped to weld ROI",
    )
    annotation_markup_removed: bool = Field(
        default=False,
        description="True when inspector markup has been removed or excluded from ROI",
    )
    label_source: str = Field(
        default="SURFACE_OBSERVATION",
        description=(
            "Provenance of the labels; must be DESTRUCTIVE_TEST for nugget acceptance. "
            "SURFACE_OBSERVATION is acceptable for surface defect classification only."
        ),
    )
    notes: List[str] = Field(default_factory=list)

    def is_training_eligible(self) -> bool:
        """
        Minimum conditions for a record to be used in training data:
          - ROI-cropped (annotation markup removed from weld region)
          - Has at least one finding
          - Is not generic_bad only (conflated class)
        """
        if not self.is_roi_cropped or not self.annotation_markup_removed:
            return False
        if not self.findings:
            return False
        codes = {f.defect_code for f in self.findings}
        # generic_bad only is not usable
        if codes == {DefectCode.GENERIC_NOK}:
            return False
        return True
