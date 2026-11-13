"""
P3C dataset quality tests: duplicate detection, label provenance, split leakage,
annotation contamination, and unverified labels.

All tests use synthetic in-memory records. No real images required.
No model training is invoked. These tests verify the analysis primitives
used in DATASET_CLEANING_REPORT.md, DUPLICATE_MANIFEST.csv, etc.
"""
from __future__ import annotations

import pytest

from app.vision.temporal.dataset_p3c import (
    ConflictType,
    ContaminationLevel,
    DuplicatePair,
    ImageRecord,
    classify_annotation_contamination,
    find_duplicate_pairs,
    find_leaked_test_records,
    has_cross_split_leakage,
    label_conflict_sha1s,
    leakage_free_test_records,
    unverified_label_sha1s,
)
from app.vision.temporal.dataset_audit import (
    AuditStatus,
    ClassStatistics,
    DatasetAudit,
    LabelSource,
    SplitDescriptor,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def rec(path: str, sha1: str, label: str, split: str,
        red: float = 0.0, green: float = 0.0, blue: float = 0.0) -> ImageRecord:
    return ImageRecord(image_path=path, sha1_16=sha1, label=label, split=split,
                       red_markup_ratio=red, green_markup_ratio=green, blue_markup_ratio=blue)


# ── Duplicate detection ────────────────────────────────────────────────────────

class TestFindDuplicatePairs:

    def test_no_duplicates_returns_empty(self):
        records = [
            rec("a.png", "aaa", "ok", "train"),
            rec("b.png", "bbb", "ok", "train"),
        ]
        assert find_duplicate_pairs(records) == []

    def test_single_pair_detected(self):
        records = [
            rec("a.png", "abc", "ok", "train"),
            rec("b.png", "abc", "ok", "val"),
        ]
        pairs = find_duplicate_pairs(records)
        assert len(pairs) == 1
        assert pairs[0].sha1_16 == "abc"

    def test_pair_path_order_is_deterministic(self):
        records = [
            rec("z.png", "hash1", "ok", "train"),
            rec("a.png", "hash1", "ok", "train"),
        ]
        pairs = find_duplicate_pairs(records)
        assert pairs[0].path_a == "a.png"
        assert pairs[0].path_b == "z.png"

    def test_triplet_produces_three_pairs(self):
        records = [
            rec("a.png", "h", "ok", "train"),
            rec("b.png", "h", "ok", "val"),
            rec("c.png", "h", "ok", "test"),
        ]
        pairs = find_duplicate_pairs(records)
        assert len(pairs) == 3

    def test_cross_split_leakage_classified(self):
        records = [
            rec("train/w.png", "deadbeef", "ok", "train"),
            rec("test/w.png",  "deadbeef", "ok", "test"),
        ]
        pairs = find_duplicate_pairs(records)
        assert pairs[0].conflict_type == ConflictType.CROSS_SPLIT_LEAKAGE

    def test_label_conflict_classified(self):
        records = [
            rec("a.png", "cafebabe", "ok",        "train"),
            rec("b.png", "cafebabe", "generic_bad", "train"),
        ]
        pairs = find_duplicate_pairs(records)
        assert pairs[0].conflict_type == ConflictType.LABEL_CONFLICT

    def test_both_conflict_classified(self):
        records = [
            rec("a.png", "ff00ff", "ok",        "train"),
            rec("b.png", "ff00ff", "generic_bad", "test"),
        ]
        pairs = find_duplicate_pairs(records)
        assert pairs[0].conflict_type == ConflictType.BOTH

    def test_same_label_same_split_classified(self):
        records = [
            rec("a.png", "11112222", "capak", "train"),
            rec("b.png", "11112222", "capak", "train"),
        ]
        pairs = find_duplicate_pairs(records)
        assert pairs[0].conflict_type == ConflictType.SAME_LABEL_SAME_SPLIT

    def test_multiple_hashes_independent(self):
        records = [
            rec("a.png", "h1", "ok", "train"),
            rec("b.png", "h1", "ok", "test"),
            rec("c.png", "h2", "nok", "train"),
            rec("d.png", "h2", "nok", "val"),
            rec("e.png", "h3", "ok", "train"),  # unique
        ]
        pairs = find_duplicate_pairs(records)
        assert len(pairs) == 2
        sha1s = {p.sha1_16 for p in pairs}
        assert sha1s == {"h1", "h2"}


# ── Annotation contamination ───────────────────────────────────────────────────

class TestClassifyAnnotationContamination:

    def test_all_zero_is_clean(self):
        assert classify_annotation_contamination(0.0, 0.0, 0.0) == ContaminationLevel.CLEAN

    def test_tiny_ratio_is_low(self):
        assert classify_annotation_contamination(0.005, 0.0, 0.0) == ContaminationLevel.LOW

    def test_boundary_low_exact(self):
        assert classify_annotation_contamination(0.01, 0.0, 0.0) == ContaminationLevel.LOW

    def test_above_low_boundary_is_medium(self):
        assert classify_annotation_contamination(0.011, 0.0, 0.0) == ContaminationLevel.MEDIUM

    def test_boundary_medium_exact(self):
        assert classify_annotation_contamination(0.05, 0.0, 0.0) == ContaminationLevel.MEDIUM

    def test_above_medium_is_high(self):
        assert classify_annotation_contamination(0.0, 0.0, 0.06) == ContaminationLevel.HIGH

    def test_max_channel_wins(self):
        # green is highest
        assert classify_annotation_contamination(0.001, 0.08, 0.001) == ContaminationLevel.HIGH

    def test_mixed_channels_still_uses_max(self):
        assert classify_annotation_contamination(0.005, 0.005, 0.005) == ContaminationLevel.LOW

    @pytest.mark.parametrize("red,green,blue,expected", [
        (0.0,   0.0,   0.0,   ContaminationLevel.CLEAN),
        (1e-05, 0.0,   0.0,   ContaminationLevel.LOW),
        (0.01,  0.0,   0.0,   ContaminationLevel.LOW),
        (0.03,  0.0,   0.0,   ContaminationLevel.MEDIUM),
        (0.05,  0.0,   0.0,   ContaminationLevel.MEDIUM),
        (0.051, 0.0,   0.0,   ContaminationLevel.HIGH),
        (0.0,   0.0,   0.99,  ContaminationLevel.HIGH),
    ])
    def test_parametrized(self, red, green, blue, expected):
        assert classify_annotation_contamination(red, green, blue) == expected


# ── Split leakage ──────────────────────────────────────────────────────────────

class TestSplitLeakage:

    def test_no_leakage_in_clean_dataset(self):
        records = [
            rec("train/a.png", "h1", "ok", "train"),
            rec("val/b.png",   "h2", "ok", "val"),
            rec("test/c.png",  "h3", "ok", "test"),
        ]
        assert find_leaked_test_records(records) == []
        assert not has_cross_split_leakage(records)

    def test_leaked_test_detected_via_sha1(self):
        records = [
            rec("train/w.png", "shared", "ok", "train"),
            rec("test/w.png",  "shared", "ok", "test"),
            rec("test/x.png",  "unique", "ok", "test"),
        ]
        leaked = find_leaked_test_records(records)
        assert len(leaked) == 1
        assert leaked[0].image_path == "test/w.png"

    def test_leaked_via_val_detected(self):
        records = [
            rec("val/a.png",  "vhash", "ok", "val"),
            rec("test/a.png", "vhash", "ok", "test"),
        ]
        assert len(find_leaked_test_records(records)) == 1

    def test_leakage_free_excludes_leaked(self):
        records = [
            rec("train/a.png", "s1", "ok", "train"),
            rec("test/a.png",  "s1", "ok", "test"),   # leaked
            rec("test/b.png",  "s2", "ok", "test"),   # clean
        ]
        clean = leakage_free_test_records(records)
        assert len(clean) == 1
        assert clean[0].image_path == "test/b.png"

    def test_has_cross_split_leakage_true(self):
        records = [
            rec("train/x.png", "abc", "ok", "train"),
            rec("test/x.png",  "abc", "ok", "test"),
        ]
        assert has_cross_split_leakage(records)

    def test_has_cross_split_leakage_false(self):
        records = [
            rec("train/x.png", "h1", "ok", "train"),
            rec("test/y.png",  "h2", "ok", "test"),
        ]
        assert not has_cross_split_leakage(records)

    def test_train_val_duplicates_do_not_count_as_leaked_test(self):
        records = [
            rec("train/a.png", "shared", "ok", "train"),
            rec("val/a.png",   "shared", "ok", "val"),
        ]
        assert find_leaked_test_records(records) == []


# ── Label conflicts ────────────────────────────────────────────────────────────

class TestLabelConflicts:

    def test_no_conflicts_in_clean_dataset(self):
        records = [
            rec("a.png", "h1", "ok", "train"),
            rec("b.png", "h2", "nok", "test"),
        ]
        assert label_conflict_sha1s(records) == set()

    def test_same_sha1_different_labels_detected(self):
        records = [
            rec("a.png", "conflict_hash", "ok", "train"),
            rec("b.png", "conflict_hash", "capak", "test"),
        ]
        assert "conflict_hash" in label_conflict_sha1s(records)

    def test_same_sha1_same_label_not_a_conflict(self):
        records = [
            rec("a.png", "h", "capak", "train"),
            rec("b.png", "h", "capak", "val"),
        ]
        assert label_conflict_sha1s(records) == set()

    def test_multiple_conflicts_all_returned(self):
        records = [
            rec("a.png", "c1", "ok",        "train"),
            rec("b.png", "c1", "generic_bad", "train"),
            rec("c.png", "c2", "capak",      "train"),
            rec("d.png", "c2", "generic_bad", "val"),
            rec("e.png", "c3", "kopuk",      "train"),
            rec("f.png", "c3", "kopuk",      "train"),  # same label — not a conflict
        ]
        conflicts = label_conflict_sha1s(records)
        assert conflicts == {"c1", "c2"}


# ── Unverified / ambiguous labels ─────────────────────────────────────────────

class TestUnverifiedLabels:

    def test_generic_bad_with_specific_label_is_unverified(self):
        records = [
            rec("a.png", "u1", "generic_bad", "train"),
            rec("b.png", "u1", "capak",       "train"),
        ]
        assert "u1" in unverified_label_sha1s(records)

    def test_two_specific_labels_not_unverified(self):
        # capak and kopuk are both specific — a label conflict, but not a "generic_bad" problem
        records = [
            rec("a.png", "u2", "capak", "train"),
            rec("b.png", "u2", "kopuk", "train"),
        ]
        assert "u2" not in unverified_label_sha1s(records)

    def test_generic_bad_alone_not_unverified(self):
        records = [
            rec("a.png", "u3", "generic_bad", "train"),
        ]
        assert unverified_label_sha1s(records) == set()

    def test_multiple_specific_labels_plus_generic_all_flagged(self):
        records = [
            rec("a.png", "u4", "generic_bad", "train"),
            rec("b.png", "u4", "capak",       "val"),
            rec("c.png", "u4", "kopuk",       "test"),
        ]
        assert "u4" in unverified_label_sha1s(records)


# ── DatasetAudit label source gate ─────────────────────────────────────────────

class TestLabelSourceProvenance:

    def test_surface_observation_blocks_training(self):
        audit = DatasetAudit(
            dataset_id="v5",
            description="V5 surface inspection dataset",
            status=AuditStatus.APPROVED,
            reviewer="qualified.engineer",
            classes=[
                ClassStatistics("ok",  139, 0.15, LabelSource.VISUAL_INSPECTION),
                ClassStatistics("nok", 788, 0.85, LabelSource.VISUAL_INSPECTION),
            ],
            split=SplitDescriptor(0.7, 0.15, 0.15, ["group_id"]),
        )
        assert not audit.is_training_allowed()
        assert "VISUAL_INSPECTION" in audit.training_blocked_reason()

    def test_surface_observation_v5_matches_known_label_source(self):
        # LabelSource.VISUAL_INSPECTION maps to surface_observation semantics
        assert LabelSource.VISUAL_INSPECTION != LabelSource.DESTRUCTIVE_TEST

    def test_destructive_test_allows_training_when_other_gates_met(self):
        audit = DatasetAudit(
            dataset_id="metal",
            description="Metallographic cross-section dataset",
            status=AuditStatus.APPROVED,
            reviewer="qualified.engineer",
            classes=[
                ClassStatistics("ok",  80, 0.5, LabelSource.DESTRUCTIVE_TEST, "report.pdf"),
                ClassStatistics("nok", 80, 0.5, LabelSource.DESTRUCTIVE_TEST, "report.pdf"),
            ],
            split=SplitDescriptor(0.7, 0.15, 0.15, ["weld_id", "production_batch"]),
        )
        assert audit.is_training_allowed()

    def test_assumed_label_source_blocks_training(self):
        audit = DatasetAudit(
            dataset_id="assumed_ds",
            description="Dataset with assumed labels",
            status=AuditStatus.APPROVED,
            reviewer="eng",
            classes=[ClassStatistics("ok", 100, 1.0, LabelSource.ASSUMED)],
        )
        assert not audit.is_training_allowed()


# ── Integration: compound scenario ────────────────────────────────────────────

class TestCompoundScenario:

    def test_v5_replica_has_all_three_issues(self):
        """
        Synthetic replica of V5 dataset pathology:
        - duplicate pairs with cross-split leakage
        - duplicate pairs with label conflicts
        - contaminated images (markup > 0)
        - VISUAL_INSPECTION label source blocks DatasetAudit
        """
        records = [
            # Leakage: same SHA1 in train and test, same label
            rec("train/puntanok_001.png", "leak01", "generic_bad", "train"),
            rec("test/puntanok_001.png",  "leak01", "generic_bad", "test"),
            # Label conflict: same SHA1, different defect name
            rec("train/puntanok_002.png", "conf01", "generic_bad",  "train", red=0.0),
            rec("train/capak_002.png",    "conf01", "capak",        "train", red=0.08),
            # Clean image, no duplicate
            rec("train/ok_001.png", "clean01", "ok", "train"),
            # Test image, no leakage
            rec("test/ok_002.png",  "clean02", "ok", "test"),
        ]

        # Duplicates
        pairs = find_duplicate_pairs(records)
        assert len(pairs) == 2
        types = {p.conflict_type for p in pairs}
        assert ConflictType.CROSS_SPLIT_LEAKAGE in types
        assert ConflictType.LABEL_CONFLICT in types

        # Leakage
        leaked = find_leaked_test_records(records)
        assert any(r.image_path == "test/puntanok_001.png" for r in leaked)

        # Leakage-free test set
        safe = leakage_free_test_records(records)
        assert all(r.image_path != "test/puntanok_001.png" for r in safe)
        assert any(r.image_path == "test/ok_002.png" for r in safe)

        # Label conflicts
        conflicts = label_conflict_sha1s(records)
        assert "conf01" in conflicts

        # Unverified labels (generic_bad + specific)
        unverified = unverified_label_sha1s(records)
        assert "conf01" in unverified

        # Annotation contamination
        assert classify_annotation_contamination(0.08, 0.0, 0.0) == ContaminationLevel.HIGH
        assert classify_annotation_contamination(0.0, 0.0, 0.0) == ContaminationLevel.CLEAN

        # DatasetAudit gate: VISUAL_INSPECTION blocks
        audit = DatasetAudit(
            dataset_id="v5_replica",
            description="Replica of V5 dataset",
            status=AuditStatus.APPROVED,
            reviewer="eng",
            classes=[ClassStatistics("ok", 139, 0.15, LabelSource.VISUAL_INSPECTION)],
            split=SplitDescriptor(0.7, 0.15, 0.15, ["group_id"]),
        )
        assert not audit.is_training_allowed()
