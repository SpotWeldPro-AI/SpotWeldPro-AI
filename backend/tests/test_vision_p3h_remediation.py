"""
P3H dataset remediation tests.

Covers:
  E1 — conflict review queue generation
  E2 — clean-source manifest classification
  E3 — leakage-safe split construction
  E4 — ground-truth provenance review
  Phase F — model readiness assessment
  DatasetAudit gate — must remain blocked (MUST NOT be bypassed)
"""
from __future__ import annotations

import pytest

from app.vision.p3h_dataset_remediation import (
    ConflictReviewRecord,
    CleanSourceRecord,
    GroundTruthReviewRecord,
    LabelProvenanceClass,
    LeakageSafeSplitRecord,
    ModelReadinessReport,
    ModelReadinessVerdict,
    RemediationStatus,
    RemediationSummary,
    assess_model_readiness,
    build_clean_source_manifest,
    build_conflict_review_queue,
    build_ground_truth_review,
    build_leakage_safe_splits,
    split_counts,
)
from app.vision.temporal.dataset_audit import AuditStatus, DatasetAudit, NO_AUDIT


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _dup_row(sha1, la, lb, pa, pb, sa, sb, aa, ab, ct):
    return dict(
        sha1_16=sha1, label_a=la, label_b=lb, path_a=pa, path_b=pb,
        source_archive_a=aa, source_archive_b=ab, split_a=sa, split_b=sb,
        conflict_type=ct,
    )


def _ann_row(path, label, split, archive="A.zip", r=0.0, g=0.0, b=0.0,
             mx=0.0, contam="CLEAN"):
    return dict(
        image_path=path, label=label, split=split, source_archive=archive,
        red_markup_ratio=r, green_markup_ratio=g, blue_markup_ratio=b,
        max_markup_ratio=mx, contamination_level=contam,
    )


# ── E1 tests ───────────────────────────────────────────────────────────────────

class TestBuildConflictReviewQueue:
    def test_label_conflict_included(self):
        rows = [_dup_row("aaa", "ok", "nok", "p1", "p2", "train", "train",
                         "A.zip", "A.zip", "LABEL_CONFLICT")]
        q = build_conflict_review_queue(rows)
        assert len(q) == 1
        assert q[0].has_label_conflict is True
        assert q[0].has_leakage is False
        assert q[0].status == RemediationStatus.PENDING_REVIEW

    def test_cross_split_leakage_included(self):
        rows = [_dup_row("bbb", "ok", "ok", "p1", "p2", "train", "test",
                         "A.zip", "A.zip", "CROSS_SPLIT_LEAKAGE")]
        q = build_conflict_review_queue(rows)
        assert len(q) == 1
        assert q[0].has_leakage is True
        assert q[0].has_label_conflict is False

    def test_both_included(self):
        rows = [_dup_row("ccc", "ok", "nok", "p1", "p2", "train", "test",
                         "A.zip", "B.zip", "BOTH")]
        q = build_conflict_review_queue(rows)
        assert len(q) == 1
        assert q[0].has_label_conflict is True
        assert q[0].has_leakage is True

    def test_benign_excluded(self):
        rows = [_dup_row("ddd", "ok", "ok", "p1", "p2", "train", "train",
                         "A.zip", "A.zip", "SAME_LABEL_SAME_SPLIT")]
        q = build_conflict_review_queue(rows)
        assert q == []

    def test_no_auto_adjudication(self):
        rows = [
            _dup_row("aaa", "capak", "generic_bad", "p1", "p2",
                     "train", "train", "A.zip", "A.zip", "LABEL_CONFLICT"),
        ]
        q = build_conflict_review_queue(rows)
        assert q[0].review_decision == ""
        assert q[0].review_notes == ""

    def test_mixed_batch(self):
        rows = [
            _dup_row("e1", "ok", "nok", "p1", "p2", "train", "train",
                     "A.zip", "A.zip", "LABEL_CONFLICT"),
            _dup_row("e2", "ok", "ok", "p3", "p4", "train", "test",
                     "A.zip", "A.zip", "CROSS_SPLIT_LEAKAGE"),
            _dup_row("e3", "ok", "ok", "p5", "p6", "train", "train",
                     "A.zip", "A.zip", "SAME_LABEL_SAME_SPLIT"),
            _dup_row("e4", "nok", "ok", "p7", "p8", "train", "test",
                     "A.zip", "B.zip", "BOTH"),
        ]
        q = build_conflict_review_queue(rows)
        assert len(q) == 3
        sha1s = {r.sha1_16 for r in q}
        assert "e1" in sha1s
        assert "e2" in sha1s
        assert "e3" not in sha1s
        assert "e4" in sha1s

    def test_empty_input(self):
        assert build_conflict_review_queue([]) == []

    def test_all_fields_populated(self):
        rows = [_dup_row("ff", "capak", "generic_bad", "/img/a.png", "/img/b.png",
                         "train", "train", "A.zip", "B.zip", "LABEL_CONFLICT")]
        q = build_conflict_review_queue(rows)
        r = q[0]
        assert r.sha1_16 == "ff"
        assert r.path_a == "/img/a.png"
        assert r.path_b == "/img/b.png"
        assert r.source_archive_a == "A.zip"
        assert r.source_archive_b == "B.zip"


# ── E2 tests ───────────────────────────────────────────────────────────────────

class TestBuildCleanSourceManifest:
    def test_clean_non_conflict_eligible(self):
        rows = [_ann_row("/img/a.png", "ok", "train", contam="CLEAN", mx=0.0)]
        m = build_clean_source_manifest(rows, conflicting_paths=set())
        assert m[0].training_eligible is True
        assert m[0].eval_eligible is True
        assert m[0].blocked_reason == ""

    def test_low_contamination_eligible(self):
        rows = [_ann_row("/img/b.png", "ok", "train", contam="LOW", mx=0.005)]
        m = build_clean_source_manifest(rows, conflicting_paths=set())
        assert m[0].training_eligible is True

    def test_medium_contamination_blocked(self):
        rows = [_ann_row("/img/c.png", "ok", "train", contam="MEDIUM", mx=0.03)]
        m = build_clean_source_manifest(rows, conflicting_paths=set())
        assert m[0].training_eligible is False
        assert "contamination=MEDIUM" in m[0].blocked_reason

    def test_high_contamination_blocked(self):
        rows = [_ann_row("/img/d.png", "ok", "train", contam="HIGH", mx=0.1)]
        m = build_clean_source_manifest(rows, conflicting_paths=set())
        assert m[0].training_eligible is False

    def test_conflict_path_blocked_for_training_and_eval(self):
        path = "/img/conflict.png"
        rows = [_ann_row(path, "capak", "train", contam="CLEAN", mx=0.0)]
        m = build_clean_source_manifest(rows, conflicting_paths={path})
        assert m[0].training_eligible is False
        assert m[0].eval_eligible is False
        assert "label_conflict_unresolved" in m[0].blocked_reason

    def test_conflict_and_contamination_both_in_reason(self):
        path = "/img/e.png"
        rows = [_ann_row(path, "ok", "train", contam="HIGH", mx=0.2)]
        m = build_clean_source_manifest(rows, conflicting_paths={path})
        assert "contamination=HIGH" in m[0].blocked_reason
        assert "label_conflict_unresolved" in m[0].blocked_reason

    def test_provenance_defaults_to_surface_observation(self):
        rows = [_ann_row("/img/f.png", "ok", "train")]
        m = build_clean_source_manifest(rows, conflicting_paths=set())
        assert m[0].provenance == LabelProvenanceClass.SURFACE_OBSERVATION

    def test_does_not_modify_or_delete_records(self):
        """Verifies pure function: original rows unchanged."""
        orig = _ann_row("/img/g.png", "ok", "train", contam="HIGH")
        rows = [orig.copy()]
        build_clean_source_manifest(rows, conflicting_paths=set())
        assert rows[0]["contamination_level"] == "HIGH"

    def test_empty_input(self):
        assert build_clean_source_manifest([], conflicting_paths=set()) == []


# ── E3 tests ───────────────────────────────────────────────────────────────────

class TestBuildLeakageSafeSplits:
    def _rows(self):
        return [
            _ann_row("/ok/a.png", "ok", "train", contam="CLEAN"),
            _ann_row("/ok/b.png", "ok", "val", contam="CLEAN"),
            _ann_row("/ok/c.png", "ok", "test", contam="CLEAN"),
            _ann_row("/ok/d.png", "ok", "test", contam="LOW"),
            _ann_row("/bad/e.png", "capak", "test", contam="CLEAN"),
        ]

    def test_non_leaked_test_records_kept(self):
        rows = self._rows()
        m = build_leakage_safe_splits(rows, leaking_paths=set(), conflicting_paths=set())
        test_safe = [r for r in m if r.original_split == "test" and r.safe_split == "test"]
        assert len(test_safe) == 3

    def test_leaked_test_path_excluded(self):
        rows = self._rows()
        m = build_leakage_safe_splits(
            rows, leaking_paths={"/ok/c.png"}, conflicting_paths=set()
        )
        rec = next(r for r in m if r.image_path == "/ok/c.png")
        assert rec.safe_split == "EXCLUDED"
        assert rec.is_leaking is True

    def test_conflicted_test_path_excluded(self):
        rows = self._rows()
        m = build_leakage_safe_splits(
            rows, leaking_paths=set(), conflicting_paths={"/ok/d.png"}
        )
        rec = next(r for r in m if r.image_path == "/ok/d.png")
        assert rec.safe_split == "EXCLUDED"
        assert rec.is_conflicted is True

    def test_train_records_not_excluded(self):
        rows = self._rows()
        m = build_leakage_safe_splits(
            rows, leaking_paths={"/ok/a.png"}, conflicting_paths={"/ok/a.png"}
        )
        rec = next(r for r in m if r.image_path == "/ok/a.png")
        # Train records are NOT excluded even if in leakage/conflict sets
        assert rec.safe_split == "train"

    def test_split_counts(self):
        rows = self._rows()
        m = build_leakage_safe_splits(
            rows, leaking_paths={"/ok/c.png"}, conflicting_paths=set()
        )
        counts = split_counts(m)
        assert counts["train"] == 1
        assert counts["val"] == 1
        assert counts["test"] == 2
        assert counts["EXCLUDED"] == 1

    def test_empty_input(self):
        assert build_leakage_safe_splits([], set(), set()) == []


# ── E4 tests ───────────────────────────────────────────────────────────────────

class TestBuildGroundTruthReview:
    def test_default_surface_observation(self):
        rows = [_ann_row("/img/a.png", "ok", "train")]
        m = build_ground_truth_review(rows)
        assert m[0].provenance == LabelProvenanceClass.SURFACE_OBSERVATION
        assert m[0].acceptable_for_nugget_training is False
        assert m[0].acceptable_for_surface_classifier is True
        assert m[0].verification_status == RemediationStatus.PENDING_REVIEW

    def test_destructive_test_provenance(self):
        rows = [_ann_row("/img/b.png", "ok", "train")]
        pmap = {"/img/b.png": LabelProvenanceClass.DESTRUCTIVE_TEST}
        m = build_ground_truth_review(rows, provenance_map=pmap)
        assert m[0].acceptable_for_nugget_training is True
        assert m[0].acceptable_for_surface_classifier is True
        assert m[0].verification_status == RemediationStatus.ELIGIBLE

    def test_model_prediction_not_verified(self):
        rows = [_ann_row("/img/c.png", "ok", "train")]
        pmap = {"/img/c.png": LabelProvenanceClass.MODEL_PREDICTION}
        m = build_ground_truth_review(rows, provenance_map=pmap)
        assert m[0].acceptable_for_nugget_training is False
        assert m[0].acceptable_for_surface_classifier is False
        assert m[0].verification_status == RemediationStatus.NOT_VERIFIED

    def test_unverified_provenance(self):
        rows = [_ann_row("/img/d.png", "ok", "train")]
        pmap = {"/img/d.png": LabelProvenanceClass.UNVERIFIED}
        m = build_ground_truth_review(rows, provenance_map=pmap)
        assert m[0].acceptable_for_nugget_training is False
        assert m[0].verification_status == RemediationStatus.NOT_VERIFIED

    def test_accepted_reference_provenance(self):
        rows = [_ann_row("/img/e.png", "capak", "train")]
        pmap = {"/img/e.png": LabelProvenanceClass.ACCEPTED_REFERENCE}
        m = build_ground_truth_review(rows, provenance_map=pmap)
        assert m[0].acceptable_for_nugget_training is True
        assert m[0].verification_status == RemediationStatus.ELIGIBLE

    def test_no_auto_verification_without_evidence(self):
        """Without a provenance_map, no record is auto-verified as ELIGIBLE."""
        rows = [_ann_row(f"/img/{i}.png", "ok", "train") for i in range(10)]
        m = build_ground_truth_review(rows)
        for rec in m:
            assert rec.verification_status != RemediationStatus.ELIGIBLE

    def test_empty_input(self):
        assert build_ground_truth_review([]) == []


# ── Phase F model readiness tests ─────────────────────────────────────────────

class TestAssessModelReadiness:
    def _clean_manifest_sufficient(self):
        """250 clean, non-conflicted training records; 50 test."""
        rows = []
        for i in range(200):
            rows.append(CleanSourceRecord(
                image_path=f"/train/{i}.png", label="ok" if i % 3 == 0 else "generic_bad",
                split="train", source_archive="A.zip", contamination_level="CLEAN",
                max_markup_ratio=0.0, is_in_conflict=False,
                provenance=LabelProvenanceClass.SURFACE_OBSERVATION,
                training_eligible=True, eval_eligible=True,
            ))
        for i in range(50):
            rows.append(CleanSourceRecord(
                image_path=f"/test/{i}.png", label="ok" if i % 2 == 0 else "generic_bad",
                split="test", source_archive="A.zip", contamination_level="CLEAN",
                max_markup_ratio=0.0, is_in_conflict=False,
                provenance=LabelProvenanceClass.SURFACE_OBSERVATION,
                training_eligible=False, eval_eligible=True,
            ))
        return rows

    def test_returns_five_reports(self):
        rows = self._clean_manifest_sufficient()
        reports = assess_model_readiness(rows, e1_resolved=True, e2_resolved=True, e3_resolved=True)
        assert len(reports) == 5

    def test_surface_classifier_conditional_when_e_gates_clear(self):
        rows = self._clean_manifest_sufficient()
        reports = assess_model_readiness(rows, e1_resolved=True, e2_resolved=True, e3_resolved=True)
        surface = next(r for r in reports if "Surface" in r.model_name)
        assert surface.verdict == ModelReadinessVerdict.CONDITIONAL

    def test_surface_classifier_no_go_when_e1_unresolved(self):
        rows = self._clean_manifest_sufficient()
        reports = assess_model_readiness(rows, e1_resolved=False)
        surface = next(r for r in reports if "Surface" in r.model_name)
        assert surface.verdict == ModelReadinessVerdict.NO_GO

    def test_cnn_gru_always_no_go_without_sequences(self):
        rows = self._clean_manifest_sufficient()
        reports = assess_model_readiness(rows, has_sequence_data=False)
        gru = next(r for r in reports if "GRU" in r.model_name)
        assert gru.verdict == ModelReadinessVerdict.NO_GO

    def test_cnn_lstm_always_no_go_without_sequences(self):
        rows = self._clean_manifest_sufficient()
        reports = assess_model_readiness(rows, has_sequence_data=False)
        lstm = next(r for r in reports if "LSTM" in r.model_name)
        assert lstm.verdict == ModelReadinessVerdict.NO_GO

    def test_segmentation_always_no_go_without_masks(self):
        rows = self._clean_manifest_sufficient()
        reports = assess_model_readiness(rows, has_segmentation_masks=False)
        seg = next(r for r in reports if "Segment" in r.model_name)
        assert seg.verdict == ModelReadinessVerdict.NO_GO

    def test_multi_label_no_go_without_class_counts(self):
        # Only 2 records per class → below minimum
        rows = [CleanSourceRecord(
            image_path=f"/{c}/{i}.png", label=c, split="train", source_archive="A.zip",
            contamination_level="CLEAN", max_markup_ratio=0.0, is_in_conflict=False,
            provenance=LabelProvenanceClass.SURFACE_OBSERVATION,
            training_eligible=True, eval_eligible=True,
        ) for c in ("capak", "deformeli", "kopuk") for i in range(2)]
        reports = assess_model_readiness(rows, e1_resolved=True)
        ml = next(r for r in reports if "Multi" in r.model_name)
        assert ml.verdict == ModelReadinessVerdict.NO_GO

    def test_surface_classifier_no_go_insufficient_records(self):
        """Fewer than MIN_TRAIN clean records → NO-GO even with e_gates cleared."""
        rows = [CleanSourceRecord(
            image_path=f"/train/{i}.png", label="ok", split="train",
            source_archive="A.zip", contamination_level="CLEAN", max_markup_ratio=0.0,
            is_in_conflict=False, provenance=LabelProvenanceClass.SURFACE_OBSERVATION,
            training_eligible=True, eval_eligible=True,
        ) for i in range(50)]  # 50 < 200 minimum
        reports = assess_model_readiness(rows, e1_resolved=True, e2_resolved=True, e3_resolved=True)
        surface = next(r for r in reports if "Surface" in r.model_name)
        assert surface.verdict == ModelReadinessVerdict.NO_GO


# ── DatasetAudit gate — must remain blocked ────────────────────────────────────

class TestDatasetAuditGateIntact:
    def test_no_audit_sentinel_blocks_training(self):
        assert NO_AUDIT.is_training_allowed() is False
        assert "DRAFT" in NO_AUDIT.training_blocked_reason()

    def test_draft_status_blocks_training(self):
        audit = DatasetAudit(
            dataset_id="p3h_test",
            description="test",
            status=AuditStatus.DRAFT,
            reviewer="engineer",
        )
        assert audit.is_training_allowed() is False

    def test_approved_without_reviewer_blocks_training(self):
        from app.vision.temporal.dataset_audit import LabelSource, ClassStatistics, SplitDescriptor
        audit = DatasetAudit(
            dataset_id="p3h_test2",
            description="test",
            status=AuditStatus.APPROVED,
            reviewer=None,
            classes=[ClassStatistics("ok", 100, 0.5, LabelSource.DESTRUCTIVE_TEST)],
            split=SplitDescriptor(0.7, 0.15, 0.15, grouping_keys=["weld_id"]),
        )
        assert audit.is_training_allowed() is False
        assert "reviewer" in audit.training_blocked_reason().lower()

    def test_visual_inspection_label_blocks_training(self):
        from app.vision.temporal.dataset_audit import LabelSource, ClassStatistics, SplitDescriptor
        audit = DatasetAudit(
            dataset_id="p3h_test3",
            description="test",
            status=AuditStatus.APPROVED,
            reviewer="eng",
            classes=[ClassStatistics("ok", 100, 0.5, LabelSource.VISUAL_INSPECTION)],
            split=SplitDescriptor(0.7, 0.15, 0.15, grouping_keys=["weld_id"]),
        )
        assert audit.is_training_allowed() is False

    def test_fully_approved_audit_passes(self):
        from app.vision.temporal.dataset_audit import LabelSource, ClassStatistics, SplitDescriptor
        audit = DatasetAudit(
            dataset_id="p3h_approved",
            description="test approved",
            status=AuditStatus.APPROVED,
            reviewer="qualified_engineer",
            classes=[
                ClassStatistics("ok", 500, 0.6, LabelSource.DESTRUCTIVE_TEST),
                ClassStatistics("capak", 200, 0.4, LabelSource.DESTRUCTIVE_TEST),
            ],
            split=SplitDescriptor(0.7, 0.15, 0.15, grouping_keys=["weld_id", "session_id"]),
            blocking_issues=[],
        )
        assert audit.is_training_allowed() is True


# ── RemediationSummary smoke test ──────────────────────────────────────────────

class TestRemediationSummary:
    def test_instantiation(self):
        s = RemediationSummary(
            total_records=927,
            total_duplicate_pairs=182,
            conflicting_pairs=173,
            leaking_pairs=53,
            benign_duplicate_pairs=7,
            unique_conflict_sha1s=170,
            unique_leakage_sha1s=53,
            training_safe_records=511,
            training_unsafe_records=416,
            eligible_train_records=300,
            eligible_test_records=50,
            e1_status=RemediationStatus.BLOCKED,
            e2_status=RemediationStatus.PENDING_REVIEW,
            e3_status=RemediationStatus.PENDING_REVIEW,
            e4_status=RemediationStatus.PENDING_REVIEW,
            training_allowed=False,
            training_blocked_reason="E1 unresolved",
        )
        assert s.training_allowed is False
        assert s.total_records == 927
