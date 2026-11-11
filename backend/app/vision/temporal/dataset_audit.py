"""
Phase 3 prerequisite: dataset audit schema.

CRITICAL: No model training may begin until a DatasetAudit with
status=APPROVED exists and has been reviewed by a qualified engineer.

Requirements before APPROVED status:
  1. Ground truth from validated destructive testing or accepted references only.
     Never from visual inspection alone or assumed labeling.
  2. Minimum dataset size: define based on expected class balance and desired
     precision/recall targets. Record here as min_samples_per_class.
  3. Leakage-safe splits: separate samples by weld_id, part_id, session_id,
     and production_batch. Never split within a weld sequence.
  4. Label provenance: each label must trace to a destructive test report or
     accepted reference document.
  5. Class imbalance documented: record OK:NOK ratio and chosen mitigation.
  6. Temporal continuity: for sequence models, frames from the same weld cycle
     must stay together in the same split (train OR test, never both).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class AuditStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LabelSource(str, Enum):
    DESTRUCTIVE_TEST = "DESTRUCTIVE_TEST"      # preferred: physical cross-section
    ACCEPTED_REFERENCE = "ACCEPTED_REFERENCE"  # e.g. established manufacturer test log
    VISUAL_INSPECTION = "VISUAL_INSPECTION"    # NOT acceptable for training labels
    ASSUMED = "ASSUMED"                         # NOT acceptable


@dataclass
class SplitDescriptor:
    """Train/validation/test split proportions and leakage-safe grouping."""
    train_fraction: float
    validation_fraction: float
    test_fraction: float
    grouping_keys: List[str] = field(default_factory=list)
    # e.g. ["weld_id", "part_id", "session_id", "production_batch"]
    temporal_contiguous: bool = True
    # True = all frames of a weld cycle stay in the same split

    def validate(self) -> List[str]:
        errors = []
        total = self.train_fraction + self.validation_fraction + self.test_fraction
        if abs(total - 1.0) > 0.001:
            errors.append(f"Split fractions sum to {total:.3f}, must be 1.0")
        if not self.grouping_keys:
            errors.append("grouping_keys is empty; set at minimum ['weld_id', 'session_id']")
        return errors


@dataclass
class ClassStatistics:
    label: str
    count: int
    fraction: float
    label_source: LabelSource
    label_provenance_ref: str = ""  # e.g. "test_report_2024_batch_A.pdf"


@dataclass
class DatasetAudit:
    """
    Mandatory pre-training audit record.

    Training must NOT begin until:
      status == AuditStatus.APPROVED
      AND reviewer is set
      AND all label_sources are DESTRUCTIVE_TEST or ACCEPTED_REFERENCE
      AND split.validate() returns []
    """
    dataset_id: str
    description: str
    status: AuditStatus = AuditStatus.DRAFT
    reviewer: Optional[str] = None
    total_sequences: int = 0           # number of complete weld-cycle sequences
    total_frames: int = 0              # total frames across all sequences
    target_fps: Optional[float] = None
    split: Optional[SplitDescriptor] = None
    classes: List[ClassStatistics] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)

    def is_training_allowed(self) -> bool:
        """
        Returns True only when all blocking conditions are cleared.
        This is a programmatic gate, not a substitute for human review.
        """
        if self.status != AuditStatus.APPROVED:
            return False
        if not self.reviewer:
            return False
        for cls in self.classes:
            if cls.label_source in (LabelSource.VISUAL_INSPECTION, LabelSource.ASSUMED):
                return False
        if self.split is not None and self.split.validate():
            return False
        return len(self.blocking_issues) == 0

    def training_blocked_reason(self) -> str:
        if self.status != AuditStatus.APPROVED:
            return f"Dataset status is {self.status}; must be APPROVED."
        if not self.reviewer:
            return "No reviewer assigned."
        for cls in self.classes:
            if cls.label_source in (LabelSource.VISUAL_INSPECTION, LabelSource.ASSUMED):
                return (
                    f"Class '{cls.label}' uses label source {cls.label_source}. "
                    "Only DESTRUCTIVE_TEST or ACCEPTED_REFERENCE are permitted."
                )
        if self.split is not None:
            errs = self.split.validate()
            if errs:
                return "Split errors: " + "; ".join(errs)
        if self.blocking_issues:
            return "Blocking issues: " + "; ".join(self.blocking_issues)
        return "No blocking issues found."


# ── Sentinel: no audit exists yet ─────────────────────────────────────────────

NO_AUDIT = DatasetAudit(
    dataset_id="NONE",
    description="No dataset audit exists. Training is not permitted.",
    status=AuditStatus.DRAFT,
    blocking_issues=["No labeled dataset has been collected or audited."],
    notes=[
        "To begin Phase 3: collect ground truth from destructive testing, "
        "complete a DatasetAudit with status=APPROVED, then contact the "
        "vision pipeline team to initiate training."
    ],
)
