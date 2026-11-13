"""
VISION-P3C: dataset quality unit tests.

All tests use synthetic in-memory data only.
No external files, no model files, no network access.
"""
import pytest

from app.vision.data_quality import (
    AnnotationRecord,
    ClassifierEvaluation,
    ContaminationLevel,
    DuplicateConflictType,
    DuplicatePair,
    LabelProvenance,
    LeakageCheckResult,
    SafeTestSubset,
    build_leakage_safe_test_subset,
    check_leakage,
    classify_duplicate_pairs,
    compute_duplicate_groups,
    evaluate_classifier_on_safe_subset,
    flag_annotation_contamination,
    summarise_contamination,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _rec(path, sha1, label, split, source="archive_a.zip", group_id="g1",
         r=0.0, g=0.0, b=0.0):
    return dict(
        image_path=path,
        sha1_16=sha1,
        label=label,
        split=split,
        source_archive=source,
        group_id=group_id,
        red_markup_ratio=r,
        green_markup_ratio=g,
        blue_markup_ratio=b,
    )


def _holdout(path, label, decision):
    p_good = 0.5 if decision == "ok" else (0.05 if decision == "nok" else 0.25)
    return dict(image_path=path, label=label, split="test",
                group_id="g1", p_good=p_good, decision=decision)


# ── LabelProvenance ────────────────────────────────────────────────────────────

class TestLabelProvenance:
    def test_destructive_test_acceptable_for_training(self):
        assert LabelProvenance.DESTRUCTIVE_TEST.is_acceptable_for_training()

    def test_accepted_reference_acceptable_for_training(self):
        assert LabelProvenance.ACCEPTED_REFERENCE.is_acceptable_for_training()

    def test_surface_observation_not_acceptable_for_nugget_training(self):
        assert not LabelProvenance.SURFACE_OBSERVATION.is_acceptable_for_training()

    def test_model_prediction_not_acceptable_for_training(self):
        assert not LabelProvenance.MODEL_PREDICTION.is_acceptable_for_training()

    def test_unverified_not_acceptable_for_training(self):
        assert not LabelProvenance.UNVERIFIED.is_acceptable_for_training()

    def test_surface_observation_acceptable_for_surface_classifier(self):
        assert LabelProvenance.SURFACE_OBSERVATION.is_acceptable_for_surface_classifier()

    def test_model_prediction_not_acceptable_for_surface_classifier(self):
        assert not LabelProvenance.MODEL_PREDICTION.is_acceptable_for_surface_classifier()

    def test_unverified_not_acceptable_for_surface_classifier(self):
        assert not LabelProvenance.UNVERIFIED.is_acceptable_for_surface_classifier()


# ── ContaminationLevel ─────────────────────────────────────────────────────────

class TestContaminationLevel:
    def test_all_zero_is_clean(self):
        assert ContaminationLevel.classify(0.0, 0.0, 0.0) == ContaminationLevel.CLEAN

    def test_tiny_ratio_is_low(self):
        assert ContaminationLevel.classify(0.005, 0.0, 0.0) == ContaminationLevel.LOW

    def test_boundary_low_to_medium(self):
        # 0.01 is still LOW
        assert ContaminationLevel.classify(0.01, 0.0, 0.0) == ContaminationLevel.LOW
        # 0.0101 is MEDIUM
        assert ContaminationLevel.classify(0.0101, 0.0, 0.0) == ContaminationLevel.MEDIUM

    def test_medium_range(self):
        assert ContaminationLevel.classify(0.0, 0.03, 0.0) == ContaminationLevel.MEDIUM

    def test_high_above_five_percent(self):
        assert ContaminationLevel.classify(0.0, 0.0, 0.06) == ContaminationLevel.HIGH

    def test_max_channel_drives_level(self):
        # green is highest
        assert ContaminationLevel.classify(0.001, 0.08, 0.001) == ContaminationLevel.HIGH

    def test_training_safe_clean(self):
        assert ContaminationLevel.CLEAN.is_training_safe()

    def test_training_safe_low(self):
        assert ContaminationLevel.LOW.is_training_safe()

    def test_training_unsafe_medium(self):
        assert not ContaminationLevel.MEDIUM.is_training_safe()

    def test_training_unsafe_high(self):
        assert not ContaminationLevel.HIGH.is_training_safe()


# ── compute_duplicate_groups ───────────────────────────────────────────────────

class TestComputeDuplicateGroups:
    def test_no_duplicates_returns_empty(self):
        records = [
            _rec("a.png", "aaa", "ok", "train"),
            _rec("b.png", "bbb", "nok", "test"),
        ]
        assert compute_duplicate_groups(records) == {}

    def test_single_duplicate_pair(self):
        records = [
            _rec("a.png", "deadbeef1234abcd", "ok", "train"),
            _rec("b.png", "deadbeef1234abcd", "nok", "test"),
        ]
        groups = compute_duplicate_groups(records)
        assert len(groups) == 1
        assert len(groups["deadbeef1234abcd"]) == 2

    def test_triple_duplicate(self):
        sha = "ffffffffffffffff"
        records = [
            _rec("a.png", sha, "ok", "train"),
            _rec("b.png", sha, "nok", "val"),
            _rec("c.png", sha, "ok", "test"),
        ]
        groups = compute_duplicate_groups(records)
        assert len(groups[sha]) == 3

    def test_ignores_records_with_no_sha1(self):
        records = [
            _rec("a.png", "", "ok", "train"),
            _rec("b.png", "", "ok", "test"),
        ]
        assert compute_duplicate_groups(records) == {}

    def test_multiple_independent_duplicate_groups(self):
        records = [
            _rec("a.png", "sha1", "ok", "train"),
            _rec("b.png", "sha1", "nok", "test"),
            _rec("c.png", "sha2", "ok", "train"),
            _rec("d.png", "sha2", "ok", "test"),
        ]
        groups = compute_duplicate_groups(records)
        assert len(groups) == 2


# ── classify_duplicate_pairs ───────────────────────────────────────────────────

class TestClassifyDuplicatePairs:
    def test_same_label_same_split_is_benign(self):
        groups = {
            "sha1": [
                _rec("a.png", "sha1", "ok", "train"),
                _rec("b.png", "sha1", "ok", "train"),
            ]
        }
        pairs = classify_duplicate_pairs(groups)
        assert len(pairs) == 1
        assert pairs[0].conflict_type == DuplicateConflictType.SAME_LABEL_SAME_SPLIT

    def test_same_label_across_train_test_is_cross_split(self):
        groups = {
            "sha1": [
                _rec("a.png", "sha1", "ok", "train"),
                _rec("b.png", "sha1", "ok", "test"),
            ]
        }
        pairs = classify_duplicate_pairs(groups)
        assert pairs[0].conflict_type == DuplicateConflictType.SAME_LABEL_CROSS_SPLIT

    def test_different_label_same_split_is_conflict(self):
        groups = {
            "sha1": [
                _rec("a.png", "sha1", "generic_bad", "train"),
                _rec("b.png", "sha1", "capak", "train"),
            ]
        }
        pairs = classify_duplicate_pairs(groups)
        assert pairs[0].conflict_type == DuplicateConflictType.LABEL_CONFLICT_SAME_SPLIT

    def test_different_label_cross_split_is_worst(self):
        groups = {
            "sha1": [
                _rec("a.png", "sha1", "generic_bad", "train"),
                _rec("b.png", "sha1", "capak", "test"),
            ]
        }
        pairs = classify_duplicate_pairs(groups)
        assert pairs[0].conflict_type == DuplicateConflictType.LABEL_CONFLICT_CROSS_SPLIT

    def test_train_val_cross_split(self):
        groups = {
            "sha1": [
                _rec("a.png", "sha1", "ok", "train"),
                _rec("b.png", "sha1", "ok", "val"),
            ]
        }
        pairs = classify_duplicate_pairs(groups)
        assert pairs[0].conflict_type == DuplicateConflictType.SAME_LABEL_CROSS_SPLIT

    def test_triple_group_emits_three_pairs(self):
        sha = "triple"
        groups = {
            sha: [
                _rec("a.png", sha, "ok", "train"),
                _rec("b.png", sha, "nok", "train"),
                _rec("c.png", sha, "ok", "test"),
            ]
        }
        pairs = classify_duplicate_pairs(groups)
        assert len(pairs) == 3


# ── DuplicateConflictType helpers ──────────────────────────────────────────────

class TestDuplicateConflictTypeHelpers:
    def test_has_leakage_flags(self):
        assert DuplicateConflictType.SAME_LABEL_CROSS_SPLIT.has_leakage()
        assert DuplicateConflictType.LABEL_CONFLICT_CROSS_SPLIT.has_leakage()

    def test_no_leakage_flags(self):
        assert not DuplicateConflictType.SAME_LABEL_SAME_SPLIT.has_leakage()
        assert not DuplicateConflictType.LABEL_CONFLICT_SAME_SPLIT.has_leakage()

    def test_has_label_conflict_flags(self):
        assert DuplicateConflictType.LABEL_CONFLICT_SAME_SPLIT.has_label_conflict()
        assert DuplicateConflictType.LABEL_CONFLICT_CROSS_SPLIT.has_label_conflict()

    def test_no_label_conflict_flags(self):
        assert not DuplicateConflictType.SAME_LABEL_SAME_SPLIT.has_label_conflict()
        assert not DuplicateConflictType.SAME_LABEL_CROSS_SPLIT.has_label_conflict()


# ── check_leakage ──────────────────────────────────────────────────────────────

class TestCheckLeakage:
    def _pairs(self, conflict_types):
        result = []
        for i, ct in enumerate(conflict_types):
            result.append(DuplicatePair(
                sha1_16=f"sha{i:04d}",
                path_a=f"a{i}.png", path_b=f"b{i}.png",
                label_a="ok", label_b="ok",
                split_a="train", split_b="test",
                source_archive_a="x.zip", source_archive_b="y.zip",
                group_id_a="g1", group_id_b="g2",
                conflict_type=ct,
            ))
        return result

    def test_empty_no_leakage(self):
        result = check_leakage([])
        assert not result.has_leakage
        assert not result.has_label_conflicts
        assert result.total_duplicate_pairs == 0

    def test_counts_cross_split(self):
        pairs = self._pairs([
            DuplicateConflictType.SAME_LABEL_CROSS_SPLIT,
            DuplicateConflictType.SAME_LABEL_SAME_SPLIT,
        ])
        result = check_leakage(pairs)
        assert result.cross_split_leakage_pairs == 1
        assert result.benign_duplicate_pairs == 1
        assert result.has_leakage

    def test_counts_label_conflicts(self):
        pairs = self._pairs([
            DuplicateConflictType.LABEL_CONFLICT_CROSS_SPLIT,
        ])
        result = check_leakage(pairs)
        assert result.label_conflict_pairs == 1
        assert result.both_conflict_pairs == 1
        assert result.has_label_conflicts

    def test_leaking_sha1s_populated(self):
        pairs = self._pairs([DuplicateConflictType.SAME_LABEL_CROSS_SPLIT])
        result = check_leakage(pairs)
        assert len(result.leaking_sha1s) == 1

    def test_conflicting_sha1s_populated(self):
        pairs = self._pairs([DuplicateConflictType.LABEL_CONFLICT_SAME_SPLIT])
        result = check_leakage(pairs)
        assert len(result.conflicting_sha1s) == 1


# ── flag_annotation_contamination ─────────────────────────────────────────────

class TestFlagAnnotationContamination:
    def test_clean_record(self):
        records = [_rec("a.png", "s", "ok", "train", r=0.0, g=0.0, b=0.0)]
        result = flag_annotation_contamination(records)
        assert result[0].contamination_level == ContaminationLevel.CLEAN

    def test_high_red_markup(self):
        records = [_rec("a.png", "s", "capak", "test", r=0.12, g=0.0, b=0.0)]
        result = flag_annotation_contamination(records)
        assert result[0].contamination_level == ContaminationLevel.HIGH

    def test_max_markup_ratio_stored(self):
        records = [_rec("a.png", "s", "ok", "train", r=0.02, g=0.03, b=0.01)]
        result = flag_annotation_contamination(records)
        assert abs(result[0].max_markup_ratio - 0.03) < 1e-9

    def test_multiple_records(self):
        records = [
            _rec("a.png", "s1", "ok", "train", r=0.0, g=0.0, b=0.0),
            _rec("b.png", "s2", "nok", "test", r=0.0, g=0.0, b=0.07),
        ]
        result = flag_annotation_contamination(records)
        assert result[0].contamination_level == ContaminationLevel.CLEAN
        assert result[1].contamination_level == ContaminationLevel.HIGH

    def test_empty_records_returns_empty(self):
        assert flag_annotation_contamination([]) == []


# ── build_leakage_safe_test_subset ─────────────────────────────────────────────

class TestBuildLeakageSafeTestSubset:
    def _make_records(self):
        recs = []
        # 20 OK test, 5 OK train
        for i in range(20):
            recs.append(_rec(f"ok_test_{i}.png", f"ok_t{i:04d}", "ok", "test"))
        for i in range(5):
            recs.append(_rec(f"ok_train_{i}.png", f"ok_tr{i:04d}", "ok", "train"))
        # 50 NOK test, 2 of which are duplicates of training
        for i in range(50):
            sha = f"nok_test_{i:04d}"
            recs.append(_rec(f"nok_test_{i}.png", sha, "generic_bad", "test"))
        # duplicate pair: same sha appears in train and test
        recs.append(_rec("leak_train.png", "leak_sha_001", "generic_bad", "train"))
        recs.append(_rec("leak_test.png", "leak_sha_001", "generic_bad", "test"))
        return recs

    def test_basic_counts(self):
        records = self._make_records()
        leaking = ["leak_sha_001"]
        subset = build_leakage_safe_test_subset(records, leaking)
        # 20 ok_test + 50 nok_test + 1 leak_test = 71 total test
        assert subset.total_original_test == 71
        # 1 excluded (leak_test)
        assert subset.total_excluded_leakage == 1
        assert subset.total_safe == 70

    def test_no_leakage(self):
        records = [
            _rec("a.png", "s1", "ok", "train"),
            _rec("b.png", "s2", "ok", "test"),
        ]
        subset = build_leakage_safe_test_subset(records, [])
        assert subset.total_safe == 1
        assert subset.total_excluded_leakage == 0

    def test_evaluable_with_enough_ok(self):
        records = [_rec(f"ok{i}.png", f"s{i:04d}", "ok", "test") for i in range(15)]
        subset = build_leakage_safe_test_subset(records, [])
        assert subset.evaluable

    def test_not_evaluable_with_too_few_ok(self):
        records = [_rec(f"ok{i}.png", f"s{i:04d}", "ok", "test") for i in range(5)]
        subset = build_leakage_safe_test_subset(records, [])
        assert not subset.evaluable
        assert "minimum" in subset.not_evaluable_reason.lower()

    def test_safe_counts_by_label(self):
        records = [
            _rec("ok1.png", "ok1", "ok", "test"),
            _rec("ok2.png", "ok2", "ok", "test"),
            _rec("nok1.png", "nok1", "capak", "test"),
        ]
        subset = build_leakage_safe_test_subset(records, [])
        assert subset.safe_counts.get("ok") == 2
        assert subset.safe_counts.get("capak") == 1

    def test_safe_paths_excludes_leaking(self):
        records = [
            _rec("safe.png", "safe_sha", "ok", "test"),
            _rec("leak.png", "leak_sha", "nok", "test"),
        ]
        subset = build_leakage_safe_test_subset(records, ["leak_sha"])
        assert "safe.png" in subset.safe_paths
        assert "leak.png" not in subset.safe_paths


# ── evaluate_classifier_on_safe_subset ────────────────────────────────────────

class TestEvaluateClassifier:
    def _make_holdout(self):
        rows = []
        # 25 OK — 1 auto-accept (true), 2 auto-reject (false reject), rest review
        rows.append(_holdout("ok_0.png", "ok", "ok"))   # true accept
        rows.append(_holdout("ok_1.png", "ok", "nok"))  # false reject
        rows.append(_holdout("ok_2.png", "ok", "nok"))  # false reject
        for i in range(3, 25):
            rows.append(_holdout(f"ok_{i}.png", "ok", "review"))
        # 50 NOK — 2 auto-accept (false accept), 20 auto-reject (true), rest review
        rows.append(_holdout("nok_0.png", "capak", "ok"))   # false accept
        rows.append(_holdout("nok_1.png", "capak", "ok"))   # false accept
        for i in range(2, 22):
            rows.append(_holdout(f"nok_{i}.png", "capak", "nok"))
        for i in range(22, 50):
            rows.append(_holdout(f"nok_{i}.png", "capak", "review"))
        return rows

    def test_basic_evaluation(self):
        rows = self._make_holdout()
        safe_paths = [r["image_path"] for r in rows]
        ev = evaluate_classifier_on_safe_subset(rows, safe_paths)
        assert ev.evaluable
        assert ev.n_ok == 25
        assert ev.n_nok == 50
        assert ev.false_accept_count == 2
        assert ev.false_reject_count == 2
        assert abs(ev.far - 2 / 50) < 1e-9
        assert abs(ev.frr - 2 / 25) < 1e-9

    def test_ci_populated(self):
        rows = self._make_holdout()
        safe_paths = [r["image_path"] for r in rows]
        ev = evaluate_classifier_on_safe_subset(rows, safe_paths)
        assert ev.far_ci_low is not None
        assert ev.far_ci_high is not None
        assert ev.far_ci_low < ev.far < ev.far_ci_high

    def test_frr_ci_populated(self):
        rows = self._make_holdout()
        safe_paths = [r["image_path"] for r in rows]
        ev = evaluate_classifier_on_safe_subset(rows, safe_paths)
        assert ev.frr_ci_low is not None
        assert ev.frr_ci_high is not None

    def test_empty_safe_paths_returns_not_evaluable(self):
        rows = self._make_holdout()
        ev = evaluate_classifier_on_safe_subset(rows, [])
        assert not ev.evaluable

    def test_path_filtering(self):
        rows = self._make_holdout()
        # Only include the first 5 paths
        safe_paths = [r["image_path"] for r in rows[:5]]
        ev = evaluate_classifier_on_safe_subset(rows, safe_paths)
        assert ev.n_total == 5

    def test_too_few_nok_not_evaluable(self):
        # 5 NOK below min_nok_for_far=20
        rows = [_holdout("ok.png", "ok", "review")]
        for i in range(5):
            rows.append(_holdout(f"nok_{i}.png", "capak", "nok"))
        safe_paths = [r["image_path"] for r in rows]
        ev = evaluate_classifier_on_safe_subset(rows, safe_paths)
        assert not ev.evaluable
        assert ev.far is None

    def test_review_rate_computed(self):
        rows = self._make_holdout()
        safe_paths = [r["image_path"] for r in rows]
        ev = evaluate_classifier_on_safe_subset(rows, safe_paths)
        assert ev.review_rate is not None
        assert 0.0 <= ev.review_rate <= 1.0


# ── summarise_contamination ────────────────────────────────────────────────────

class TestSummariseContamination:
    def test_basic_grouping(self):
        records = flag_annotation_contamination([
            _rec("a.png", "s1", "ok", "train", r=0.0, g=0.0, b=0.0),
            _rec("b.png", "s2", "ok", "train", r=0.0, g=0.0, b=0.0),
            _rec("c.png", "s3", "capak", "test", r=0.1, g=0.0, b=0.0),
        ])
        summary = summarise_contamination(records)
        assert summary["ok"][ContaminationLevel.CLEAN] == 2
        assert summary["capak"][ContaminationLevel.HIGH] == 1

    def test_empty_input(self):
        assert summarise_contamination([]) == {}


# ── Integration: full deduplication + leakage pipeline ────────────────────────

class TestIntegration:
    """
    End-to-end: build groups → classify pairs → check leakage → build safe subset.
    Mimics the V5 dataset pattern where generic_bad duplicates specific defect classes.
    """

    def _v5_like_records(self):
        recs = []
        # 83 unique OK in train, 28 OK in val, 28 OK in test
        for i in range(83):
            recs.append(_rec(f"ok_{i}.png", f"ok{i:04d}", "ok", "train",
                             source="Okpunta.zip"))
        for i in range(28):
            recs.append(_rec(f"ok_v_{i}.png", f"okv{i:04d}", "ok", "val",
                             source="Okpunta.zip"))
        for i in range(28):
            recs.append(_rec(f"ok_t_{i}.png", f"okt{i:04d}", "ok", "test",
                             source="Okpunta.zip"))
        # 10 generic_bad in train, each with an exact duplicate as capak in test
        for i in range(10):
            sha = f"dup{i:04d}xxxxxxxxxxxx"
            recs.append(_rec(f"gb_tr_{i}.png", sha, "generic_bad", "train",
                             source="Puntanok.1.zip"))
            recs.append(_rec(f"capak_t_{i}.png", sha, "capak", "test",
                             source="Punta_hatalar.zip"))
        # 20 clean generic_bad in test (no duplicates)
        for i in range(20):
            recs.append(_rec(f"gb_t_{i}.png", f"gb{i:04d}xxxxxxxxxx", "generic_bad",
                             "test", source="Puntanok.1.zip"))
        return recs

    def test_duplicate_groups_found(self):
        recs = self._v5_like_records()
        groups = compute_duplicate_groups(recs)
        assert len(groups) == 10

    def test_all_pairs_are_cross_split_conflict(self):
        recs = self._v5_like_records()
        groups = compute_duplicate_groups(recs)
        pairs = classify_duplicate_pairs(groups)
        for p in pairs:
            assert p.conflict_type == DuplicateConflictType.LABEL_CONFLICT_CROSS_SPLIT

    def test_leakage_check_finds_all_10_leaking_sha1s(self):
        recs = self._v5_like_records()
        groups = compute_duplicate_groups(recs)
        pairs = classify_duplicate_pairs(groups)
        result = check_leakage(pairs)
        assert len(result.leaking_sha1s) == 10
        assert result.has_leakage

    def test_safe_subset_excludes_leaked_test_rows(self):
        recs = self._v5_like_records()
        groups = compute_duplicate_groups(recs)
        pairs = classify_duplicate_pairs(groups)
        leakage = check_leakage(pairs)
        subset = build_leakage_safe_test_subset(recs, leakage.leaking_sha1s)
        # 10 capak test rows excluded; 20 generic_bad test + 28 OK test remain
        assert subset.total_excluded_leakage == 10
        assert subset.total_safe == 48
        assert subset.total_original_test == 58

    def test_safe_subset_evaluable_with_28_ok(self):
        recs = self._v5_like_records()
        groups = compute_duplicate_groups(recs)
        pairs = classify_duplicate_pairs(groups)
        leakage = check_leakage(pairs)
        subset = build_leakage_safe_test_subset(recs, leakage.leaking_sha1s)
        # 28 OK test images survive → evaluable
        assert subset.evaluable

    def test_wilson_ci_bounds_valid(self):
        # Smoke test: CI bounds must satisfy 0 ≤ low ≤ p ≤ high ≤ 1
        rows = []
        for i in range(30):
            rows.append(_holdout(f"ok_{i}.png", "ok", "review"))
        for i in range(60):
            decision = "ok" if i < 3 else ("nok" if i < 23 else "review")
            rows.append(_holdout(f"nok_{i}.png", "capak", decision))
        safe_paths = [r["image_path"] for r in rows]
        ev = evaluate_classifier_on_safe_subset(rows, safe_paths)
        if ev.evaluable:
            assert 0.0 <= ev.far_ci_low <= ev.far <= ev.far_ci_high <= 1.0
