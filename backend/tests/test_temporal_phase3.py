"""
Tests for Phase 3 temporal interfaces: dataset audit, model plan, deployment gates.

IMPORTANT: These tests verify interface correctness and gate enforcement.
No model weights exist. No training metrics are tested here.
All 'passing' examples use manually inserted placeholder metrics to verify
gate logic only — they do NOT represent real model performance.
"""
from __future__ import annotations

import pytest

from app.vision.temporal.dataset_audit import (
    AuditStatus,
    ClassStatistics,
    DatasetAudit,
    LabelSource,
    NO_AUDIT,
    SplitDescriptor,
)
from app.vision.temporal.model_plan import (
    CURRENT_PLAN,
    ExperimentSpec,
    ExperimentStatus,
    ModelArchitecture,
    ModelValidationPlan,
)
from app.vision.temporal.interfaces import (
    NotLoadedClassifier,
    NotLoadedExtractor,
)


# ── DatasetAudit tests ─────────────────────────────────────────────────────────

class TestDatasetAuditGate:

    def test_no_audit_blocks_training(self):
        assert not NO_AUDIT.is_training_allowed()

    def test_draft_status_blocks_training(self):
        audit = DatasetAudit(dataset_id="d1", description="test")
        assert not audit.is_training_allowed()

    def test_approved_without_reviewer_blocks(self):
        audit = DatasetAudit(
            dataset_id="d1", description="test",
            status=AuditStatus.APPROVED,
            reviewer=None,
        )
        assert not audit.is_training_allowed()

    def test_visual_inspection_labels_block_training(self):
        audit = DatasetAudit(
            dataset_id="d1", description="test",
            status=AuditStatus.APPROVED,
            reviewer="eng.test",
            classes=[ClassStatistics(
                label="OK", count=100, fraction=0.5,
                label_source=LabelSource.VISUAL_INSPECTION,
            )],
            split=SplitDescriptor(
                train_fraction=0.7, validation_fraction=0.15, test_fraction=0.15,
                grouping_keys=["weld_id", "session_id"],
            ),
        )
        assert not audit.is_training_allowed()
        assert "VISUAL_INSPECTION" in audit.training_blocked_reason()

    def test_assumed_labels_block_training(self):
        audit = DatasetAudit(
            dataset_id="d1", description="test",
            status=AuditStatus.APPROVED,
            reviewer="eng.test",
            classes=[ClassStatistics(
                label="NOK", count=50, fraction=0.5,
                label_source=LabelSource.ASSUMED,
            )],
        )
        assert not audit.is_training_allowed()

    def test_valid_audit_allows_training(self):
        audit = DatasetAudit(
            dataset_id="d1", description="test",
            status=AuditStatus.APPROVED,
            reviewer="qualified.engineer",
            classes=[
                ClassStatistics("OK", 400, 0.8, LabelSource.DESTRUCTIVE_TEST, "report_A.pdf"),
                ClassStatistics("NOK", 100, 0.2, LabelSource.DESTRUCTIVE_TEST, "report_A.pdf"),
            ],
            split=SplitDescriptor(
                train_fraction=0.7, validation_fraction=0.15, test_fraction=0.15,
                grouping_keys=["weld_id", "part_id", "session_id", "production_batch"],
            ),
        )
        assert audit.is_training_allowed()

    def test_blocking_issues_block_training(self):
        audit = DatasetAudit(
            dataset_id="d1", description="test",
            status=AuditStatus.APPROVED,
            reviewer="eng.test",
            blocking_issues=["Camera calibration incomplete"],
        )
        assert not audit.is_training_allowed()

    def test_blocked_reason_message_set(self):
        assert len(NO_AUDIT.training_blocked_reason()) > 0


class TestSplitDescriptorValidation:

    def test_valid_split(self):
        s = SplitDescriptor(0.7, 0.15, 0.15, ["weld_id", "session_id"])
        assert s.validate() == []

    def test_fractions_not_summing_to_one(self):
        s = SplitDescriptor(0.6, 0.2, 0.1, ["weld_id"])  # sums to 0.9
        errors = s.validate()
        assert any("1.0" in e for e in errors)

    def test_empty_grouping_keys_error(self):
        s = SplitDescriptor(0.7, 0.15, 0.15, [])
        errors = s.validate()
        assert any("grouping_keys" in e for e in errors)


# ── ModelValidationPlan tests ──────────────────────────────────────────────────

class TestModelValidationPlan:

    def test_current_plan_deployment_blocked(self):
        assert not CURRENT_PLAN.deployment_allowed()

    def test_blocked_reason_references_dataset(self):
        reason = CURRENT_PLAN.deployment_blocked_reason()
        assert len(reason) > 0

    def test_deployment_requires_dataset_audit(self):
        plan = ModelValidationPlan(plan_id="p1", dataset_audit_approved=False)
        assert not plan.deployment_allowed()
        assert "Dataset audit" in plan.deployment_blocked_reason()

    def test_deployment_requires_baseline_published(self):
        plan = ModelValidationPlan(
            plan_id="p1",
            dataset_audit_id="d1",
            dataset_audit_approved=True,
            baseline_published=False,
        )
        assert not plan.deployment_allowed()
        assert "baseline" in plan.deployment_blocked_reason().lower()

    def test_deployment_requires_hardware_validation(self):
        plan = ModelValidationPlan(
            plan_id="p1",
            dataset_audit_approved=True,
            baseline_published=True,
            hardware_latency_validated=False,
        )
        assert not plan.deployment_allowed()

    def test_deployment_requires_passing_experiment(self):
        plan = ModelValidationPlan(
            plan_id="p1",
            dataset_audit_approved=True,
            baseline_published=True,
            hardware_latency_validated=True,
            experiments=[],  # no experiments
        )
        assert not plan.deployment_allowed()

    def test_deployment_allowed_when_all_gates_met(self):
        """Verify gate logic with manually-set placeholder metrics."""
        exp = ExperimentSpec(
            experiment_id="exp_test",
            architecture=ModelArchitecture.GRU_CLASSIFIER,
            is_causal=True,
            status=ExperimentStatus.COMPLETE,
            # Manually insert placeholder passing metrics — these are NOT real results
            actual_metrics={
                "precision": 0.90,
                "recall": 0.85,
                "f1": 0.87,
                "inference_latency_ms": 20.0,
            },
        )
        plan = ModelValidationPlan(
            plan_id="p_test",
            dataset_audit_approved=True,
            baseline_published=True,
            hardware_latency_validated=True,
            experiments=[exp],
        )
        assert plan.deployment_allowed()

    def test_non_causal_model_cannot_enable_deployment(self):
        """is_causal=False must never allow real-time deployment."""
        exp = ExperimentSpec(
            experiment_id="exp_noncausal",
            architecture=ModelArchitecture.LSTM_CLASSIFIER,
            is_causal=False,  # future-frame leakage
            status=ExperimentStatus.COMPLETE,
            actual_metrics={"precision": 0.99, "recall": 0.99, "f1": 0.99, "inference_latency_ms": 1.0},
        )
        plan = ModelValidationPlan(
            plan_id="p_nc",
            dataset_audit_approved=True,
            baseline_published=True,
            hardware_latency_validated=True,
            experiments=[exp],
        )
        assert not plan.deployment_allowed()

    def test_failed_gates_block_deployment(self):
        exp = ExperimentSpec(
            experiment_id="exp_poor",
            architecture=ModelArchitecture.GRU_CLASSIFIER,
            is_causal=True,
            status=ExperimentStatus.COMPLETE,
            actual_metrics={"precision": 0.60, "recall": 0.55, "f1": 0.57, "inference_latency_ms": 10.0},
        )
        plan = ModelValidationPlan(
            plan_id="p_poor",
            dataset_audit_approved=True,
            baseline_published=True,
            hardware_latency_validated=True,
            experiments=[exp],
        )
        assert not plan.deployment_allowed()


class TestExperimentSpec:

    def test_no_metrics_fails_gates(self):
        exp = ExperimentSpec("e1", ModelArchitecture.GRU_CLASSIFIER, is_causal=True)
        assert not exp.passed_gates()

    def test_passing_metrics_pass_gates(self):
        exp = ExperimentSpec(
            "e1", ModelArchitecture.GRU_CLASSIFIER, is_causal=True,
            actual_metrics={"precision": 0.90, "recall": 0.85, "f1": 0.87, "inference_latency_ms": 15.0},
        )
        assert exp.passed_gates()

    def test_high_latency_fails_gate(self):
        exp = ExperimentSpec(
            "e1", ModelArchitecture.GRU_CLASSIFIER, is_causal=True,
            actual_metrics={"precision": 0.90, "recall": 0.85, "f1": 0.87, "inference_latency_ms": 200.0},
        )
        assert not exp.passed_gates()

    def test_current_experiments_dataset_pending(self):
        for exp in CURRENT_PLAN.experiments:
            assert exp.status == ExperimentStatus.DATASET_PENDING


# ── NotLoaded sentinel tests (Phase 1 interfaces still work) ──────────────────

class TestNotLoadedSentinels:

    def test_extractor_not_loaded(self):
        ext = NotLoadedExtractor()
        assert not ext.is_loaded()
        with pytest.raises(RuntimeError, match="No CNN feature extractor"):
            ext.extract(b"\xff\xd8\xff\xd9")

    def test_classifier_not_loaded(self):
        clf = NotLoadedClassifier()
        assert not clf.is_loaded()
        with pytest.raises(RuntimeError, match="No sequence classifier"):
            clf.predict([])

    def test_classifier_vacuously_causal(self):
        clf = NotLoadedClassifier()
        assert clf.is_causal  # vacuously true; never actually runs
