"""
Phase 3 model validation plan: experiment specifications and evaluation gates.

IMPORTANT:
  - No model weights exist. This module defines the PLAN only.
  - Actual training cannot start until DatasetAudit.is_training_allowed() == True.
  - Evaluation metrics must be measured on a HELD-OUT test set, never training data.
  - GRU/LSTM baselines must be published before any transformer variant is considered.
  - is_causal must be True on any model deployed for real-time inference.

Recommended experiment order:
  1. CNN feature extractor (MobileNetV2 or EfficientNet-Lite0 backbone, frozen)
  2. GRU baseline classifier (window_size=16, hidden_dim=128)
  3. LSTM baseline classifier (same window_size and hidden_dim as GRU)
  4. Compare GRU vs LSTM on precision, recall, F1 and inference latency
  5. Publish comparison before considering a transformer or attention variant
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ModelArchitecture(str, Enum):
    CNN_FEATURE_EXTRACTOR = "CNN_FEATURE_EXTRACTOR"
    GRU_CLASSIFIER = "GRU_CLASSIFIER"
    LSTM_CLASSIFIER = "LSTM_CLASSIFIER"
    TRANSFORMER_CLASSIFIER = "TRANSFORMER_CLASSIFIER"  # only after GRU/LSTM baseline


class ExperimentStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    DATASET_PENDING = "DATASET_PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ABANDONED = "ABANDONED"


@dataclass
class EvaluationGates:
    """
    Minimum acceptable thresholds for a model to pass validation.
    These are targets, not guarantees; actual results must be measured.
    All values are on the HELD-OUT test set only.
    """
    min_precision: float = 0.85      # fraction of POSITIVE predictions that are correct
    min_recall: float = 0.80         # fraction of actual POSITIVES correctly identified
    min_f1: float = 0.82             # harmonic mean
    max_inference_latency_ms: float = 50.0  # per-window on target hardware
    min_window_coverage: float = 0.90       # fraction of weld cycles correctly segmented
    note: str = (
        "These are placeholder target thresholds. "
        "Replace with values derived from application-specific requirements "
        "before beginning formal evaluation."
    )


@dataclass
class ExperimentSpec:
    """Specification for one training experiment."""
    experiment_id: str
    architecture: ModelArchitecture
    backbone: str = ""             # e.g. "mobilenet_v2", "efficientnet_lite0"
    window_size: int = 16          # frames per sequence window
    hidden_dim: int = 128          # for GRU/LSTM hidden state
    batch_size: int = 32
    max_epochs: int = 50
    learning_rate: float = 1e-3
    is_causal: bool = True         # MUST be True for real-time deployment
    dataset_id: str = ""           # links to DatasetAudit.dataset_id
    status: ExperimentStatus = ExperimentStatus.NOT_STARTED
    gates: EvaluationGates = field(default_factory=EvaluationGates)
    actual_metrics: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def passed_gates(self) -> bool:
        """True only if actual_metrics satisfy all gate thresholds."""
        if not self.actual_metrics:
            return False
        return (
            self.actual_metrics.get("precision", 0) >= self.gates.min_precision
            and self.actual_metrics.get("recall", 0) >= self.gates.min_recall
            and self.actual_metrics.get("f1", 0) >= self.gates.min_f1
            and self.actual_metrics.get("inference_latency_ms", 999) <= self.gates.max_inference_latency_ms
        )


@dataclass
class ModelValidationPlan:
    """
    Full validation plan covering dataset audit, experiments, and deployment gates.

    deployment_allowed() returns True only when ALL conditions are verified.
    """
    plan_id: str
    dataset_audit_id: str = "NONE"
    dataset_audit_approved: bool = False
    experiments: List[ExperimentSpec] = field(default_factory=list)
    baseline_published: bool = False   # GRU/LSTM comparison must be published first
    hardware_latency_validated: bool = False  # measured on actual target hardware
    notes: List[str] = field(default_factory=list)

    def deployment_allowed(self) -> bool:
        """
        Returns True only when ALL Phase 3 deployment conditions are met.
        This is a programmatic gate; human sign-off is also required.
        """
        if not self.dataset_audit_approved:
            return False
        if not self.baseline_published:
            return False
        if not self.hardware_latency_validated:
            return False
        passing = [e for e in self.experiments if e.passed_gates() and e.is_causal]
        return len(passing) >= 1

    def deployment_blocked_reason(self) -> str:
        if not self.dataset_audit_approved:
            return f"Dataset audit '{self.dataset_audit_id}' not approved."
        if not self.baseline_published:
            return "GRU/LSTM baseline comparison not yet published."
        if not self.hardware_latency_validated:
            return "Inference latency not validated on target hardware."
        passing = [e for e in self.experiments if e.passed_gates() and e.is_causal]
        if not passing:
            return "No experiment has passed all evaluation gates with is_causal=True."
        return "All conditions met."


# ── Sentinel: no plan exists yet ──────────────────────────────────────────────

CURRENT_PLAN = ModelValidationPlan(
    plan_id="phase3_v0",
    dataset_audit_id="NONE",
    dataset_audit_approved=False,
    baseline_published=False,
    hardware_latency_validated=False,
    experiments=[
        ExperimentSpec(
            experiment_id="exp_01_gru_baseline",
            architecture=ModelArchitecture.GRU_CLASSIFIER,
            backbone="mobilenet_v2",
            window_size=16,
            hidden_dim=128,
            status=ExperimentStatus.DATASET_PENDING,
            notes=["Cannot start: no labeled dataset. See DatasetAudit.NO_AUDIT."],
        ),
        ExperimentSpec(
            experiment_id="exp_02_lstm_baseline",
            architecture=ModelArchitecture.LSTM_CLASSIFIER,
            backbone="mobilenet_v2",
            window_size=16,
            hidden_dim=128,
            status=ExperimentStatus.DATASET_PENDING,
            notes=["Cannot start: no labeled dataset. Run after exp_01 completes."],
        ),
    ],
    notes=[
        "Phase 3 is blocked on Phase 2 hardware validation and dataset collection.",
        "Transformer variant will not be considered until GRU/LSTM baseline is published.",
        "No model weights exist. No accuracy metrics can be reported.",
    ],
)
