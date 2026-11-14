"""
P3H dataset remediation primitives.

Pure functions only — no file I/O at import time, no model calls, no auto-adjudication.
Builds on data_quality.py types.

E1: duplicate + label-conflict review queues
E2: annotation contamination classification and clean-source manifest
E3: leakage-safe split construction from available grouping keys
E4: ground-truth provenance audit and NOT_VERIFIED marking
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ── Enums ─────────────────────────────────────────────────────────────────────

class RemediationStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"           # passes all checks for the stated purpose
    PENDING_REVIEW = "PENDING_REVIEW"  # human decision required before use
    BLOCKED = "BLOCKED"             # disqualified; must not be used for training/eval
    NOT_VERIFIED = "NOT_VERIFIED"   # label provenance not confirmed


class LabelProvenanceClass(str, Enum):
    DESTRUCTIVE_TEST = "DESTRUCTIVE_TEST"      # cross-section, caliper — gold standard
    ACCEPTED_REFERENCE = "ACCEPTED_REFERENCE"  # published standard / manufacturer log
    SURFACE_OBSERVATION = "SURFACE_OBSERVATION"  # visual annotation — not for nugget models
    MODEL_PREDICTION = "MODEL_PREDICTION"      # never acceptable as ground truth
    UNVERIFIED = "UNVERIFIED"                  # unknown origin


class ModelReadinessVerdict(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    CONDITIONAL = "CONDITIONAL"  # requirements met with stated caveats


# ── E1: Conflict review records ───────────────────────────────────────────────

@dataclass
class ConflictReviewRecord:
    """One duplicate pair that requires human adjudication."""
    sha1_16: str
    path_a: str
    path_b: str
    label_a: str
    label_b: str
    split_a: str
    split_b: str
    source_archive_a: str
    source_archive_b: str
    conflict_type: str          # from DuplicateConflictType
    has_label_conflict: bool
    has_leakage: bool
    review_decision: str = ""   # filled by human reviewer
    review_notes: str = ""      # filled by human reviewer
    status: RemediationStatus = RemediationStatus.PENDING_REVIEW


def build_conflict_review_queue(
    dup_rows: List[dict],
) -> List[ConflictReviewRecord]:
    """
    Convert duplicate manifest rows into human-review records.

    Only conflicting pairs (LABEL_CONFLICT, BOTH, CROSS_SPLIT_LEAKAGE) are
    included.  SAME_LABEL_SAME_SPLIT benign pairs are omitted.

    No auto-adjudication is performed; all records are PENDING_REVIEW.
    """
    result: List[ConflictReviewRecord] = []
    for row in dup_rows:
        ct = row.get("conflict_type", "")
        has_conflict = ct in ("LABEL_CONFLICT", "BOTH")
        has_leakage = ct in ("CROSS_SPLIT_LEAKAGE", "BOTH")
        if not (has_conflict or has_leakage):
            continue
        result.append(ConflictReviewRecord(
            sha1_16=row.get("sha1_16", ""),
            path_a=row.get("path_a", ""),
            path_b=row.get("path_b", ""),
            label_a=row.get("label_a", ""),
            label_b=row.get("label_b", ""),
            split_a=row.get("split_a", ""),
            split_b=row.get("split_b", ""),
            source_archive_a=row.get("source_archive_a", ""),
            source_archive_b=row.get("source_archive_b", ""),
            conflict_type=ct,
            has_label_conflict=has_conflict,
            has_leakage=has_leakage,
        ))
    return result


# ── E2: Clean-source manifest ─────────────────────────────────────────────────

@dataclass
class CleanSourceRecord:
    """One annotation record classified by training suitability."""
    image_path: str
    label: str
    split: str
    source_archive: str
    contamination_level: str    # CLEAN / LOW / MEDIUM / HIGH
    max_markup_ratio: float
    is_in_conflict: bool        # True if SHA1 appears in a conflict pair
    provenance: LabelProvenanceClass
    training_eligible: bool
    eval_eligible: bool
    blocked_reason: str = ""


def build_clean_source_manifest(
    annotation_rows: List[dict],
    conflicting_paths: set[str],
    *,
    surface_classifier_ok: bool = True,
) -> List[CleanSourceRecord]:
    """
    Classify each annotation record by training and evaluation suitability.

    Rules:
    - Contamination MEDIUM/HIGH → training_eligible=False (use clean original only)
    - In conflict_paths → training_eligible=False, eval_eligible=False
    - Provenance defaults to SURFACE_OBSERVATION (no provenance column in manifest)
    - SURFACE_OBSERVATION is conditionally acceptable for surface classifier only

    Does not modify, delete, or move any file.
    """
    result: List[CleanSourceRecord] = []
    for row in annotation_rows:
        path = row.get("image_path", "")
        contam = row.get("contamination_level", "UNKNOWN")
        max_ratio = float(row.get("max_markup_ratio", 0.0))
        in_conflict = path in conflicting_paths

        # Contamination gate
        contam_ok = contam in ("CLEAN", "LOW")
        # Provenance: manifest has no provenance column → SURFACE_OBSERVATION
        prov = LabelProvenanceClass.SURFACE_OBSERVATION

        training_eligible = contam_ok and not in_conflict and surface_classifier_ok
        eval_eligible = not in_conflict

        blocked_parts: List[str] = []
        if not contam_ok:
            blocked_parts.append(f"contamination={contam}")
        if in_conflict:
            blocked_parts.append("label_conflict_unresolved")
        if not surface_classifier_ok:
            blocked_parts.append("surface_classifier_disabled")

        result.append(CleanSourceRecord(
            image_path=path,
            label=row.get("label", ""),
            split=row.get("split", ""),
            source_archive=row.get("source_archive", ""),
            contamination_level=contam,
            max_markup_ratio=max_ratio,
            is_in_conflict=in_conflict,
            provenance=prov,
            training_eligible=training_eligible,
            eval_eligible=eval_eligible,
            blocked_reason="; ".join(blocked_parts),
        ))
    return result


# ── E3: Leakage-safe splits ───────────────────────────────────────────────────

@dataclass
class LeakageSafeSplitRecord:
    """One annotation record with its safe-split assignment."""
    image_path: str
    label: str
    original_split: str
    safe_split: str             # "train", "val", "test", or "EXCLUDED"
    source_archive: str         # grouping key (best available without weld_id)
    contamination_level: str
    is_leaking: bool
    is_conflicted: bool
    exclusion_reason: str = ""


def build_leakage_safe_splits(
    annotation_rows: List[dict],
    leaking_paths: set[str],
    conflicting_paths: set[str],
) -> List[LeakageSafeSplitRecord]:
    """
    Produce a leakage-safe split manifest.

    Strategy (best available without weld_id/part_id):
    - Use source_archive as the coarse grouping key.
    - Any path in leaking_paths or conflicting_paths is EXCLUDED from test.
    - Original train/val assignments are preserved for non-excluded records.
    - Records previously in test that are now excluded get safe_split=EXCLUDED.

    NOTE: Without weld_id, full leakage-safety cannot be guaranteed at weld-cycle
    granularity.  This manifest is a best-effort remediation pending E1 resolution.
    """
    result: List[LeakageSafeSplitRecord] = []
    for row in annotation_rows:
        path = row.get("image_path", "")
        orig_split = row.get("split", "unknown")
        is_leak = path in leaking_paths
        is_conf = path in conflicting_paths

        excl_parts: List[str] = []
        if is_leak:
            excl_parts.append("cross_split_leakage")
        if is_conf:
            excl_parts.append("label_conflict_unresolved")

        if orig_split == "test" and excl_parts:
            safe_split = "EXCLUDED"
        else:
            safe_split = orig_split

        result.append(LeakageSafeSplitRecord(
            image_path=path,
            label=row.get("label", ""),
            original_split=orig_split,
            safe_split=safe_split,
            source_archive=row.get("source_archive", ""),
            contamination_level=row.get("contamination_level", "UNKNOWN"),
            is_leaking=is_leak,
            is_conflicted=is_conf,
            exclusion_reason="; ".join(excl_parts),
        ))
    return result


def split_counts(records: List[LeakageSafeSplitRecord]) -> Dict[str, int]:
    """Count records per safe_split value."""
    counts: Dict[str, int] = {}
    for r in records:
        counts[r.safe_split] = counts.get(r.safe_split, 0) + 1
    return counts


# ── E4: Ground truth review ───────────────────────────────────────────────────

@dataclass
class GroundTruthReviewRecord:
    """One annotation record with its verified ground-truth status."""
    image_path: str
    label: str
    split: str
    source_archive: str
    provenance: LabelProvenanceClass
    acceptable_for_nugget_training: bool
    acceptable_for_surface_classifier: bool
    verification_status: RemediationStatus
    review_notes: str = ""


def build_ground_truth_review(
    annotation_rows: List[dict],
    *,
    provenance_map: Optional[Dict[str, LabelProvenanceClass]] = None,
) -> List[GroundTruthReviewRecord]:
    """
    Produce a ground-truth review manifest.

    provenance_map: optional {image_path: LabelProvenanceClass}.
    When no map is provided (the common case — no provenance column in manifest),
    all records default to SURFACE_OBSERVATION.

    SURFACE_OBSERVATION:
      - acceptable_for_nugget_training = False (visual appearance != nugget quality)
      - acceptable_for_surface_classifier = True (after contamination + conflict cleanup)

    MODEL_PREDICTION / UNVERIFIED:
      - both acceptable fields = False
      - status = NOT_VERIFIED
    """
    prov_map = provenance_map or {}
    result: List[GroundTruthReviewRecord] = []
    for row in annotation_rows:
        path = row.get("image_path", "")
        prov = prov_map.get(path, LabelProvenanceClass.SURFACE_OBSERVATION)

        nugget_ok = prov in (
            LabelProvenanceClass.DESTRUCTIVE_TEST,
            LabelProvenanceClass.ACCEPTED_REFERENCE,
        )
        surface_ok = prov in (
            LabelProvenanceClass.DESTRUCTIVE_TEST,
            LabelProvenanceClass.ACCEPTED_REFERENCE,
            LabelProvenanceClass.SURFACE_OBSERVATION,
        )
        if prov in (LabelProvenanceClass.MODEL_PREDICTION, LabelProvenanceClass.UNVERIFIED):
            status = RemediationStatus.NOT_VERIFIED
        elif prov == LabelProvenanceClass.SURFACE_OBSERVATION:
            status = RemediationStatus.PENDING_REVIEW
        else:
            status = RemediationStatus.ELIGIBLE

        result.append(GroundTruthReviewRecord(
            image_path=path,
            label=row.get("label", ""),
            split=row.get("split", ""),
            source_archive=row.get("source_archive", ""),
            provenance=prov,
            acceptable_for_nugget_training=nugget_ok,
            acceptable_for_surface_classifier=surface_ok,
            verification_status=status,
            review_notes=(
                "Provenance not documented in manifest; assumed SURFACE_OBSERVATION. "
                "Acceptable for surface classifier after E1-E3 remediation; "
                "NOT acceptable for nugget acceptance classification."
                if prov == LabelProvenanceClass.SURFACE_OBSERVATION else ""
            ),
        ))
    return result


# ── Phase F: Model readiness ───────────────────────────────────────────────────

@dataclass
class ModelReadinessReport:
    """GO/NO-GO assessment for one model family."""
    model_name: str
    architecture: str
    verdict: ModelReadinessVerdict
    eligible_train_count: int
    eligible_test_count: int
    min_required_train: int
    min_required_test: int
    blockers: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)


# Minimum sample requirements (conservative, not statistical power calculations)
_MIN_TRAIN = 200
_MIN_TEST = 40
_MIN_TRAIN_MULTILABEL_PER_CLASS = 30
_MIN_TEST_MULTILABEL_PER_CLASS = 10


def assess_model_readiness(
    clean_manifest: List[CleanSourceRecord],
    *,
    has_sequence_data: bool = False,
    has_segmentation_masks: bool = False,
    e1_resolved: bool = False,
    e2_resolved: bool = False,
    e3_resolved: bool = False,
) -> List[ModelReadinessReport]:
    """
    Produce GO/NO-GO verdicts for the five model families.

    Parameters reflect the current blocking state; callers set them based on
    E1–E3 remediation outcomes.  No model training or inference is performed.
    """
    train_eligible = [r for r in clean_manifest if r.training_eligible and r.split == "train"]
    test_eligible = [r for r in clean_manifest if r.eval_eligible and r.split == "test"]

    from collections import Counter
    train_by_label: Dict[str, int] = Counter(r.label for r in train_eligible)
    test_by_label: Dict[str, int] = Counter(r.label for r in test_eligible)

    n_train = len(train_eligible)
    n_test = len(test_eligible)

    reports: List[ModelReadinessReport] = []

    # 1. Binary surface classifier (OK vs NOK)
    surface_blockers: List[str] = []
    surface_caveats: List[str] = []
    if not e1_resolved:
        surface_blockers.append("E1: 170 unresolved duplicate/conflict SHA1s reduce clean train set")
    if not e2_resolved:
        surface_caveats.append("E2: 416/927 records contaminated; clean originals not verified")
    if not e3_resolved:
        surface_caveats.append("E3: splits constructed from source_archive proxy; weld_id grouping unavailable")
    if n_train < _MIN_TRAIN:
        surface_blockers.append(f"E1: insufficient clean training samples ({n_train} < {_MIN_TRAIN} required)")
    surface_caveats.append(
        "Labels are SURFACE_OBSERVATION only; model predicts visible surface quality, "
        "NOT nugget acceptance — must be documented in deployment specification."
    )
    surface_verdict = (
        ModelReadinessVerdict.CONDITIONAL if (not surface_blockers and n_train >= _MIN_TRAIN)
        else ModelReadinessVerdict.NO_GO
    )
    reports.append(ModelReadinessReport(
        model_name="Binary Surface Classifier (OK/NOK)",
        architecture="CNN fine-tune",
        verdict=surface_verdict,
        eligible_train_count=n_train,
        eligible_test_count=n_test,
        min_required_train=_MIN_TRAIN,
        min_required_test=_MIN_TEST,
        blockers=surface_blockers,
        caveats=surface_caveats,
    ))

    # 2. Multi-label defect detection (18 specific classes)
    ml_blockers: List[str] = []
    if not e1_resolved:
        ml_blockers.append("E1 unresolved: 173 conflicting pairs pollute class examples")
    for label, cnt in train_by_label.items():
        if label not in ("ok", "generic_bad") and cnt < _MIN_TRAIN_MULTILABEL_PER_CLASS:
            ml_blockers.append(
                f"class '{label}': only {cnt} clean train samples (min {_MIN_TRAIN_MULTILABEL_PER_CLASS})"
            )
    ml_blockers.append(
        "399 records labeled 'generic_bad' cannot be decomposed into specific defect classes "
        "without destructive-test confirmation"
    )
    reports.append(ModelReadinessReport(
        model_name="Multi-label Defect Detection",
        architecture="CNN + multi-head classifier",
        verdict=ModelReadinessVerdict.NO_GO,
        eligible_train_count=n_train,
        eligible_test_count=n_test,
        min_required_train=_MIN_TRAIN_MULTILABEL_PER_CLASS,
        min_required_test=_MIN_TEST_MULTILABEL_PER_CLASS,
        blockers=ml_blockers,
    ))

    # 3. Image segmentation
    seg_blockers = [
        "No segmentation masks exist in the dataset (only bounding-box or image-level labels)",
        "Segmentation requires pixel-level annotation: polygon/mask per defect instance",
    ]
    reports.append(ModelReadinessReport(
        model_name="Image Segmentation",
        architecture="U-Net / Mask-RCNN",
        verdict=ModelReadinessVerdict.NO_GO,
        eligible_train_count=0,
        eligible_test_count=0,
        min_required_train=_MIN_TRAIN,
        min_required_test=_MIN_TEST,
        blockers=seg_blockers,
    ))

    # 4. CNN-GRU
    gru_blockers = [
        "No temporal video sequences in current dataset (still-image archive only)",
        "CNN-GRU requires contiguous frame sequences from weld cycles with timestamps",
        "DatasetAudit.is_training_allowed() = False (status=DRAFT, no approved reviewer)",
    ]
    if not has_sequence_data:
        pass  # already in blockers above
    reports.append(ModelReadinessReport(
        model_name="CNN-GRU",
        architecture="CNN feature extractor + GRU classifier",
        verdict=ModelReadinessVerdict.NO_GO,
        eligible_train_count=0,
        eligible_test_count=0,
        min_required_train=_MIN_TRAIN,
        min_required_test=_MIN_TEST,
        blockers=gru_blockers,
    ))

    # 5. CNN-LSTM
    lstm_blockers = [
        "No temporal video sequences in current dataset (still-image archive only)",
        "CNN-LSTM requires contiguous frame sequences from weld cycles with timestamps",
        "DatasetAudit.is_training_allowed() = False (status=DRAFT, no approved reviewer)",
        "GRU baseline must be published before LSTM is evaluated (per model_plan.py)",
    ]
    reports.append(ModelReadinessReport(
        model_name="CNN-LSTM",
        architecture="CNN feature extractor + LSTM classifier",
        verdict=ModelReadinessVerdict.NO_GO,
        eligible_train_count=0,
        eligible_test_count=0,
        min_required_train=_MIN_TRAIN,
        min_required_test=_MIN_TEST,
        blockers=lstm_blockers,
    ))

    return reports


# ── Summary helpers ────────────────────────────────────────────────────────────

@dataclass
class RemediationSummary:
    """Top-level summary of the P3H remediation pass."""
    total_records: int
    total_duplicate_pairs: int
    conflicting_pairs: int
    leaking_pairs: int
    benign_duplicate_pairs: int
    unique_conflict_sha1s: int
    unique_leakage_sha1s: int
    training_safe_records: int       # CLEAN+LOW contamination
    training_unsafe_records: int     # MEDIUM+HIGH contamination
    eligible_train_records: int      # after E1+E2 filter
    eligible_test_records: int
    e1_status: RemediationStatus
    e2_status: RemediationStatus
    e3_status: RemediationStatus
    e4_status: RemediationStatus
    training_allowed: bool = False   # only True when DatasetAudit.is_training_allowed()
    training_blocked_reason: str = ""
