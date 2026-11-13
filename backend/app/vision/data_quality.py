"""
Vision P3C — dataset quality checking primitives.

All functions operate on plain dicts/lists read from CSV manifests.
No external data files are required at import time.
No model training or inference is performed here.

Label provenance taxonomy (aligned with DatasetAudit.LabelSource):
  DESTRUCTIVE_TEST    — physical cross-section, caliper measurement
  ACCEPTED_REFERENCE  — published standard / manufacturer test log
  SURFACE_OBSERVATION — visual inspection record (same restriction as VISUAL_INSPECTION)
  MODEL_PREDICTION    — classifier output — never acceptable as training ground truth
  UNVERIFIED          — unknown / undocumented origin
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ── Label provenance ───────────────────────────────────────────────────────────

class LabelProvenance(str, Enum):
    DESTRUCTIVE_TEST = "DESTRUCTIVE_TEST"
    ACCEPTED_REFERENCE = "ACCEPTED_REFERENCE"
    SURFACE_OBSERVATION = "SURFACE_OBSERVATION"  # visual inspection; not acceptable for nugget training
    MODEL_PREDICTION = "MODEL_PREDICTION"        # never use as ground truth
    UNVERIFIED = "UNVERIFIED"

    def is_acceptable_for_training(self) -> bool:
        """
        Only DESTRUCTIVE_TEST and ACCEPTED_REFERENCE are acceptable as training labels
        for safety-critical nugget acceptance.  SURFACE_OBSERVATION is acceptable
        ONLY for surface-defect classification when that limitation is documented.
        """
        return self in (self.DESTRUCTIVE_TEST, self.ACCEPTED_REFERENCE)

    def is_acceptable_for_surface_classifier(self) -> bool:
        """
        For a surface-defect binary classifier (OK/NOK based on visible features),
        SURFACE_OBSERVATION is conditionally acceptable after annotation cleanup,
        deduplication, and reviewer sign-off.  It is NOT acceptable for nugget
        acceptance because a visually OK weld may have an undersized nugget.
        """
        return self in (self.DESTRUCTIVE_TEST, self.ACCEPTED_REFERENCE, self.SURFACE_OBSERVATION)


# ── Annotation contamination ───────────────────────────────────────────────────

class ContaminationLevel(str, Enum):
    CLEAN = "CLEAN"       # all markup ratios == 0.0
    LOW = "LOW"           # max markup ratio in (0, 0.01]
    MEDIUM = "MEDIUM"     # max markup ratio in (0.01, 0.05]
    HIGH = "HIGH"         # max markup ratio > 0.05

    @classmethod
    def classify(cls, red: float, green: float, blue: float) -> "ContaminationLevel":
        max_ratio = max(red, green, blue)
        if max_ratio == 0.0:
            return cls.CLEAN
        if max_ratio <= 0.01:
            return cls.LOW
        if max_ratio <= 0.05:
            return cls.MEDIUM
        return cls.HIGH

    def is_training_safe(self) -> bool:
        """CLEAN and LOW are considered training-safe; MEDIUM/HIGH are not."""
        return self in (self.CLEAN, self.LOW)


# ── Duplicate analysis ─────────────────────────────────────────────────────────

class DuplicateConflictType(str, Enum):
    SAME_LABEL_SAME_SPLIT = "SAME_LABEL_SAME_SPLIT"       # benign
    SAME_LABEL_CROSS_SPLIT = "SAME_LABEL_CROSS_SPLIT"     # leakage, no label conflict
    LABEL_CONFLICT_SAME_SPLIT = "LABEL_CONFLICT_SAME_SPLIT"  # label disagreement
    LABEL_CONFLICT_CROSS_SPLIT = "LABEL_CONFLICT_CROSS_SPLIT"  # leakage + conflict (worst)

    def has_leakage(self) -> bool:
        return self in (self.SAME_LABEL_CROSS_SPLIT, self.LABEL_CONFLICT_CROSS_SPLIT)

    def has_label_conflict(self) -> bool:
        return self in (self.LABEL_CONFLICT_SAME_SPLIT, self.LABEL_CONFLICT_CROSS_SPLIT)


@dataclass
class DuplicatePair:
    sha1_16: str
    path_a: str
    path_b: str
    label_a: str
    label_b: str
    split_a: str
    split_b: str
    source_archive_a: str
    source_archive_b: str
    group_id_a: str
    group_id_b: str
    conflict_type: DuplicateConflictType


@dataclass
class AnnotationRecord:
    image_path: str
    label: str
    split: str
    source_archive: str
    red_markup_ratio: float
    green_markup_ratio: float
    blue_markup_ratio: float
    max_markup_ratio: float
    contamination_level: ContaminationLevel


@dataclass
class LeakageCheckResult:
    total_records: int
    total_duplicate_pairs: int
    cross_split_leakage_pairs: int
    label_conflict_pairs: int
    both_conflict_pairs: int
    benign_duplicate_pairs: int
    # sha1s that appear in both train and test
    leaking_sha1s: List[str] = field(default_factory=list)
    # sha1s with conflicting labels
    conflicting_sha1s: List[str] = field(default_factory=list)

    @property
    def has_leakage(self) -> bool:
        return self.cross_split_leakage_pairs > 0

    @property
    def has_label_conflicts(self) -> bool:
        return self.label_conflict_pairs > 0


@dataclass
class SafeTestSubset:
    """
    A leakage-free test set: images whose SHA1 does not appear in train or val.
    """
    total_original_test: int
    total_safe: int
    total_excluded_leakage: int
    # Counts by label
    safe_counts: Dict[str, int] = field(default_factory=dict)
    excluded_counts: Dict[str, int] = field(default_factory=dict)
    safe_paths: List[str] = field(default_factory=list)
    evaluable: bool = True
    not_evaluable_reason: str = ""

    MIN_OK_FOR_EVALUATION = 10  # minimum OK samples to compute OK-class metrics


@dataclass
class ClassifierEvaluation:
    """
    Model evaluation on a leakage-safe, annotation-aware test subset.
    May be NOT_EVALUABLE if the subset is too small.
    """
    evaluable: bool
    not_evaluable_reason: str = ""
    n_total: int = 0
    n_ok: int = 0
    n_nok: int = 0
    n_auto_accept: int = 0
    n_auto_reject: int = 0
    n_review: int = 0
    false_accept_count: int = 0  # NOK → auto-accept
    false_reject_count: int = 0  # OK → auto-reject
    true_accept_count: int = 0
    true_reject_count: int = 0
    # Rates (None when not evaluable due to small N)
    far: Optional[float] = None   # false accept rate = false_accept / n_nok
    frr: Optional[float] = None   # false reject rate = false_reject / n_ok
    review_rate: Optional[float] = None
    # Confidence intervals (Wilson 95%) — None if N too small
    far_ci_low: Optional[float] = None
    far_ci_high: Optional[float] = None
    frr_ci_low: Optional[float] = None
    frr_ci_high: Optional[float] = None


# ── Core functions ─────────────────────────────────────────────────────────────

def compute_duplicate_groups(records: List[dict]) -> Dict[str, List[dict]]:
    """
    Group records by sha1_16.  Returns only SHA1s that appear more than once.
    Input records must have keys: sha1_16, image_path, label, split,
                                  source_archive, group_id.
    """
    by_sha1: Dict[str, List[dict]] = {}
    for rec in records:
        h = rec.get("sha1_16", "")
        if h:
            by_sha1.setdefault(h, []).append(rec)
    return {h: recs for h, recs in by_sha1.items() if len(recs) > 1}


def classify_duplicate_pairs(
    duplicate_groups: Dict[str, List[dict]],
) -> List[DuplicatePair]:
    """
    For every SHA1 that appears more than once, emit one DuplicatePair for
    each distinct (path_a, path_b) combination.  For groups of N > 2, emit
    all N*(N-1)/2 pairs; in practice the dataset has pairs only.
    """
    pairs: List[DuplicatePair] = []
    for sha1, recs in duplicate_groups.items():
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                a, b = recs[i], recs[j]
                same_label = a["label"] == b["label"]
                same_split = a["split"] == b["split"]
                # Cross-split = any two different split names
                splits = {a["split"], b["split"]}
                is_cross_split = len(splits) > 1

                if same_label and not is_cross_split:
                    ct = DuplicateConflictType.SAME_LABEL_SAME_SPLIT
                elif same_label and is_cross_split:
                    ct = DuplicateConflictType.SAME_LABEL_CROSS_SPLIT
                elif not same_label and not is_cross_split:
                    ct = DuplicateConflictType.LABEL_CONFLICT_SAME_SPLIT
                else:
                    ct = DuplicateConflictType.LABEL_CONFLICT_CROSS_SPLIT

                pairs.append(DuplicatePair(
                    sha1_16=sha1,
                    path_a=a.get("image_path", ""),
                    path_b=b.get("image_path", ""),
                    label_a=a["label"],
                    label_b=b["label"],
                    split_a=a["split"],
                    split_b=b["split"],
                    source_archive_a=a.get("source_archive", ""),
                    source_archive_b=b.get("source_archive", ""),
                    group_id_a=a.get("group_id", ""),
                    group_id_b=b.get("group_id", ""),
                    conflict_type=ct,
                ))
    return pairs


def check_leakage(pairs: List[DuplicatePair]) -> LeakageCheckResult:
    leaking = [p for p in pairs if p.conflict_type.has_leakage()]
    conflicting = [p for p in pairs if p.conflict_type.has_label_conflict()]
    both = [p for p in pairs if p.conflict_type == DuplicateConflictType.LABEL_CONFLICT_CROSS_SPLIT]
    benign = [p for p in pairs if p.conflict_type == DuplicateConflictType.SAME_LABEL_SAME_SPLIT]

    total_records_in_groups = sum(
        1 for _ in pairs
    )  # pairs, not records; total_records passed separately

    return LeakageCheckResult(
        total_records=0,  # filled by caller
        total_duplicate_pairs=len(pairs),
        cross_split_leakage_pairs=len(leaking),
        label_conflict_pairs=len(conflicting),
        both_conflict_pairs=len(both),
        benign_duplicate_pairs=len(benign),
        leaking_sha1s=list({p.sha1_16 for p in leaking}),
        conflicting_sha1s=list({p.sha1_16 for p in conflicting}),
    )


def flag_annotation_contamination(records: List[dict]) -> List[AnnotationRecord]:
    """
    Classify each record by its annotation markup ratio.
    Records must have: image_path, label, split, source_archive,
                       red_markup_ratio, green_markup_ratio, blue_markup_ratio.
    """
    result: List[AnnotationRecord] = []
    for rec in records:
        r = float(rec.get("red_markup_ratio", 0.0))
        g = float(rec.get("green_markup_ratio", 0.0))
        b = float(rec.get("blue_markup_ratio", 0.0))
        max_r = max(r, g, b)
        result.append(AnnotationRecord(
            image_path=rec.get("image_path", ""),
            label=rec.get("label", ""),
            split=rec.get("split", ""),
            source_archive=rec.get("source_archive", ""),
            red_markup_ratio=r,
            green_markup_ratio=g,
            blue_markup_ratio=b,
            max_markup_ratio=max_r,
            contamination_level=ContaminationLevel.classify(r, g, b),
        ))
    return result


def build_leakage_safe_test_subset(
    records: List[dict],
    leaking_sha1s: List[str],
) -> SafeTestSubset:
    """
    From the manifest, identify test images whose SHA1 does NOT appear
    in the train or val splits.  Returns a SafeTestSubset.
    """
    leaking_set = set(leaking_sha1s)
    test_records = [r for r in records if r.get("split") == "test"]
    safe, excluded = [], []
    for r in test_records:
        if r.get("sha1_16", "") in leaking_set:
            excluded.append(r)
        else:
            safe.append(r)

    safe_counts: Dict[str, int] = {}
    excluded_counts: Dict[str, int] = {}
    for r in safe:
        safe_counts[r["label"]] = safe_counts.get(r["label"], 0) + 1
    for r in excluded:
        excluded_counts[r["label"]] = excluded_counts.get(r["label"], 0) + 1

    n_ok_safe = safe_counts.get("ok", 0)
    evaluable = n_ok_safe >= SafeTestSubset.MIN_OK_FOR_EVALUATION
    reason = "" if evaluable else (
        f"Only {n_ok_safe} leakage-free OK test images; "
        f"minimum {SafeTestSubset.MIN_OK_FOR_EVALUATION} required."
    )
    return SafeTestSubset(
        total_original_test=len(test_records),
        total_safe=len(safe),
        total_excluded_leakage=len(excluded),
        safe_counts=safe_counts,
        excluded_counts=excluded_counts,
        safe_paths=[r["image_path"] for r in safe],
        evaluable=evaluable,
        not_evaluable_reason=reason,
    )


def _wilson_ci(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score 95% confidence interval for a proportion k/n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def evaluate_classifier_on_safe_subset(
    holdout_records: List[dict],
    safe_paths: List[str],
    accept_threshold: float = 0.42,
    reject_threshold: float = 0.12,
    min_nok_for_far: int = 20,
    min_ok_for_frr: int = 10,
) -> ClassifierEvaluation:
    """
    Re-evaluate the existing classifier's decisions on the leakage-safe
    test subset only.

    holdout_records: rows from v5_holdout_decisions.csv with keys:
      image_path, label, split, group_id, p_good, decision
    safe_paths: set of image paths from SafeTestSubset.safe_paths
    """
    safe_set = set(safe_paths)
    safe_records = [r for r in holdout_records if r.get("image_path", "") in safe_set]

    if not safe_records:
        return ClassifierEvaluation(
            evaluable=False,
            not_evaluable_reason="No holdout records matched safe test paths.",
        )

    n_ok = sum(1 for r in safe_records if r.get("label") == "ok")
    n_nok = sum(1 for r in safe_records if r.get("label") != "ok")

    # Use stored decision field (pre-computed with given thresholds)
    n_auto_accept = sum(1 for r in safe_records if r.get("decision") == "ok")
    n_auto_reject = sum(1 for r in safe_records if r.get("decision") == "nok")
    n_review = sum(1 for r in safe_records if r.get("decision") == "review")

    # False accept: NOK classified as auto-accept
    fa = sum(1 for r in safe_records if r.get("label") != "ok" and r.get("decision") == "ok")
    # False reject: OK classified as auto-reject
    fr = sum(1 for r in safe_records if r.get("label") == "ok" and r.get("decision") == "nok")
    # True accept: OK classified as auto-accept
    ta = sum(1 for r in safe_records if r.get("label") == "ok" and r.get("decision") == "ok")
    # True reject: NOK classified as auto-reject
    tr = sum(1 for r in safe_records if r.get("label") != "ok" and r.get("decision") == "nok")

    ev = ClassifierEvaluation(
        evaluable=True,
        n_total=len(safe_records),
        n_ok=n_ok,
        n_nok=n_nok,
        n_auto_accept=n_auto_accept,
        n_auto_reject=n_auto_reject,
        n_review=n_review,
        false_accept_count=fa,
        false_reject_count=fr,
        true_accept_count=ta,
        true_reject_count=tr,
        review_rate=n_review / len(safe_records) if safe_records else None,
    )

    if n_nok >= min_nok_for_far:
        ev.far = fa / n_nok
        ci = _wilson_ci(fa, n_nok)
        ev.far_ci_low, ev.far_ci_high = ci
    else:
        ev.evaluable = False
        ev.not_evaluable_reason = (
            f"Only {n_nok} leakage-free NOK test images; "
            f"minimum {min_nok_for_far} required for FAR with confidence interval."
        )

    if n_ok >= min_ok_for_frr:
        ev.frr = fr / n_ok
        ci = _wilson_ci(fr, n_ok)
        ev.frr_ci_low, ev.frr_ci_high = ci
    # else frr stays None

    return ev


def summarise_contamination(
    annotation_records: List[AnnotationRecord],
) -> Dict[str, Dict[ContaminationLevel, int]]:
    """
    Returns {label: {ContaminationLevel: count}} for all records.
    """
    result: Dict[str, Dict[ContaminationLevel, int]] = {}
    for rec in annotation_records:
        label_map = result.setdefault(rec.label, {})
        label_map[rec.contamination_level] = label_map.get(rec.contamination_level, 0) + 1
    return result
