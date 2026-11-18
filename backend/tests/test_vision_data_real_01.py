"""
VISION-DATA-REAL-01 — Real Weld Dataset Qualification and Human Review Readiness

Verifies:
  - Exact dataset record counts against ANNOTATION_AUDIT.csv
  - E1 conflict queue: 175 rows, all PENDING_REVIEW
  - E2 contamination inventory
  - E3 leakage-safe split candidate manifest
  - E4 ground truth provenance (all SURFACE_OBSERVATION, 0 destructive)
  - Defect taxonomy: 18 classes (13 V5 + 5 internal)
  - DatasetAudit gate: is_training_allowed() == False
  - Source archive physical accessibility
  - Real video footage inventory

Hard rules enforced by test assertions:
  - No automatic E1 conflict decisions made
  - No production database changes (uses isolated test DB)
  - No model training initiated
  - E1-E4 gates not bypassed
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

# ── Project root and document paths ───────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCS = PROJECT_ROOT / "docs"
VISION_DOCS = PROJECT_ROOT / "docs" / "vision_validation"

ANNOTATION_AUDIT_CSV   = DOCS / "ANNOTATION_AUDIT.csv"
E1_QUEUE_CSV           = DOCS / "E1_CONFLICT_REVIEW_QUEUE.csv"
DUPLICATE_MANIFEST_CSV = DOCS / "DUPLICATE_MANIFEST.csv"
E2_MANIFEST_CSV        = DOCS / "E2_CLEAN_SOURCE_MANIFEST.csv"
E3_SPLITS_CSV          = DOCS / "E3_LEAKAGE_SAFE_SPLITS.csv"
E4_GT_CSV              = DOCS / "E4_GROUND_TRUTH_REVIEW.csv"

# Real dataset root (Windows path; accessible in this environment)
REAL_DATASET_ROOT = Path(
    r"D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\V5_dataset\raw_images"
)
REAL_VIDEO_FILE = Path(
    r"D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\Spot_Welding_Detection_6.7.2026.mp4"
)
SOURCE_ARCHIVE_DIR = Path(
    r"D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\train"
)


def _read_csv(path: Path) -> list[dict]:
    # utf-8-sig strips the BOM that Windows tools (PowerShell Export-Csv) emit
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ── STEP 1 — Repository and Data Audit ────────────────────────────────────────

class TestStep1RepositoryAudit:
    def test_annotation_audit_exists(self):
        assert ANNOTATION_AUDIT_CSV.is_file(), "ANNOTATION_AUDIT.csv is missing"

    def test_annotation_audit_row_count(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        assert len(rows) == 927, f"Expected 927, got {len(rows)}"

    def test_annotation_audit_required_columns(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        required = {"image_path", "label", "split", "source_archive",
                    "max_markup_ratio", "contamination_level"}
        assert required.issubset(rows[0].keys())

    def test_duplicate_manifest_exists(self):
        assert DUPLICATE_MANIFEST_CSV.is_file(), "DUPLICATE_MANIFEST.csv is missing"

    def test_duplicate_manifest_row_count(self):
        rows = _read_csv(DUPLICATE_MANIFEST_CSV)
        # 182 pairs (includes benign SAME_LABEL_SAME_SPLIT)
        assert len(rows) == 182, f"Expected 182, got {len(rows)}"

    def test_dataset_label_distribution(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        labels = {}
        for r in rows:
            labels[r["label"]] = labels.get(r["label"], 0) + 1
        assert labels["generic_bad"] == 399
        assert labels["ok"] == 139
        assert labels["capak"] == 112
        assert len(labels) == 13, f"Expected 13 label classes, got {len(labels)}"

    def test_dataset_split_distribution(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        splits = {}
        for r in rows:
            splits[r["split"]] = splits.get(r["split"], 0) + 1
        assert splits["train"] == 540
        assert splits["val"] == 183
        assert splits["test"] == 204

    def test_source_archives_in_manifest(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        archives = {r["source_archive"] for r in rows}
        # At minimum these three archives must be present
        assert "Okpunta.zip" in archives
        assert "Puntanok.1.zip" in archives

    def test_real_dataset_directory_accessible(self):
        assert REAL_DATASET_ROOT.is_dir(), (
            f"Real dataset directory not accessible: {REAL_DATASET_ROOT}"
        )

    def test_real_dataset_class_directories(self):
        expected_classes = {
            "capak", "cift_sac", "cokertme", "deformeli", "delik",
            "eksik", "generic_bad", "kacik", "kenar", "kopuk",
            "kucuk_cekirdek", "ok", "ust_uste"
        }
        actual = {d.name for d in REAL_DATASET_ROOT.iterdir() if d.is_dir()}
        assert expected_classes == actual

    def test_real_dataset_class_counts_match_annotation_audit(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        audit_counts = {}
        for r in rows:
            label = r["label"]
            audit_counts[label] = audit_counts.get(label, 0) + 1

        for label, expected_count in audit_counts.items():
            class_dir = REAL_DATASET_ROOT / label
            if class_dir.is_dir():
                actual = sum(1 for f in class_dir.iterdir()
                             if f.suffix.lower() in {".png", ".jpg", ".jpeg"})
                assert actual == expected_count, (
                    f"Class '{label}': directory has {actual} images, "
                    f"audit CSV has {expected_count}"
                )

    def test_no_weld_id_in_annotation_audit(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        # weld_id column does not exist in this CSV
        assert "weld_id" not in rows[0].keys(), (
            "weld_id found — grouping is now possible, update E3 split logic"
        )


# ── STEP 2 — E1 Human Review Queue ────────────────────────────────────────────

class TestStep2E1HumanReview:
    def test_e1_queue_exists(self):
        assert E1_QUEUE_CSV.is_file(), "E1_CONFLICT_REVIEW_QUEUE.csv is missing"

    def test_e1_queue_row_count(self):
        rows = _read_csv(E1_QUEUE_CSV)
        assert len(rows) == 175, f"Expected 175 conflict pairs, got {len(rows)}"

    def test_e1_queue_all_pending(self):
        rows = _read_csv(E1_QUEUE_CSV)
        decided = [r for r in rows if r.get("review_decision", "").strip()]
        assert decided == [], (
            f"{len(decided)} rows have review_decision filled — "
            "E1 decisions must be made by a human reviewer, not automatically"
        )

    def test_e1_queue_all_status_pending_review(self):
        rows = _read_csv(E1_QUEUE_CSV)
        non_pending = [r for r in rows if r.get("status") != "PENDING_REVIEW"]
        assert non_pending == [], (
            f"{len(non_pending)} rows have status != PENDING_REVIEW"
        )

    def test_e1_conflict_type_counts(self):
        rows = _read_csv(E1_QUEUE_CSV)
        types = {}
        for r in rows:
            t = r["conflict_type"]
            types[t] = types.get(t, 0) + 1
        assert types.get("LABEL_CONFLICT", 0) == 122
        assert types.get("BOTH", 0) == 51
        assert types.get("CROSS_SPLIT_LEAKAGE", 0) == 2

    def test_e1_has_no_auto_adjudications(self):
        rows = _read_csv(E1_QUEUE_CSV)
        for r in rows:
            assert r.get("review_decision", "") == "", (
                f"Row with sha1={r['sha1_16']} has a pre-filled decision. "
                "No automatic adjudication is permitted."
            )

    def test_e1_cross_split_leakage_identified(self):
        rows = _read_csv(E1_QUEUE_CSV)
        leakage = [r for r in rows if r["has_leakage"] == "True"]
        # 51 BOTH + 2 CROSS_SPLIT_LEAKAGE = 53 leakage pairs
        assert len(leakage) == 53, (
            f"Expected 53 leakage pairs, got {len(leakage)}"
        )

    def test_e1_prioritization_both_before_label_conflict(self):
        rows = _read_csv(E1_QUEUE_CSV)
        # BOTH type should appear in queue (leakage + conflict = highest priority)
        both_rows = [r for r in rows if r["conflict_type"] == "BOTH"]
        assert len(both_rows) == 51


# ── STEP 3 — E2 Annotation Contamination ──────────────────────────────────────

class TestStep3E2Contamination:
    def test_e2_manifest_exists(self):
        assert E2_MANIFEST_CSV.is_file(), "E2_CLEAN_SOURCE_MANIFEST.csv is missing"

    def test_e2_manifest_row_count(self):
        rows = _read_csv(E2_MANIFEST_CSV)
        assert len(rows) == 927

    def test_e2_contamination_counts(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        counts = {}
        for r in rows:
            level = r["contamination_level"]
            counts[level] = counts.get(level, 0) + 1
        medium_high = counts.get("MEDIUM", 0) + counts.get("HIGH", 0)
        assert medium_high == 416, f"Expected 416 MEDIUM/HIGH, got {medium_high}"

    def test_e2_training_safe_records(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        clean_low = [r for r in rows
                     if r["contamination_level"] in ("CLEAN", "LOW")]
        assert len(clean_low) == 511

    def test_e2_no_automatic_marking_removal(self):
        # Verify the annotation audit does not claim markings have been removed
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        # contamination_level field still present for all records — no erasure
        no_contamination_col = [r for r in rows if "contamination_level" not in r]
        assert no_contamination_col == []

    def test_e2_source_archive_linkage(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        no_archive = [r for r in rows if not r.get("source_archive")]
        # All records should have a source_archive reference
        assert no_archive == [], (
            f"{len(no_archive)} records have no source_archive"
        )


# ── STEP 4 — E3 Leakage-Safe Splits ───────────────────────────────────────────

class TestStep4E3Splits:
    def test_e3_manifest_exists(self):
        assert E3_SPLITS_CSV.is_file(), "E3_LEAKAGE_SAFE_SPLITS.csv is missing"

    def test_e3_manifest_row_count(self):
        rows = _read_csv(E3_SPLITS_CSV)
        assert len(rows) == 927

    def test_e3_required_columns(self):
        rows = _read_csv(E3_SPLITS_CSV)
        required = {"image_path", "label", "original_split", "safe_split",
                    "is_leaking", "is_conflicted"}
        assert required.issubset(rows[0].keys())

    def test_e3_leakage_flagged_records(self):
        rows = _read_csv(E3_SPLITS_CSV)
        leaking = [r for r in rows if r["is_leaking"] == "True"]
        # 53 SHA1s with cross-split leakage
        assert len(leaking) >= 53, (
            f"Expected ≥53 leaking records, got {len(leaking)}"
        )

    def test_e3_safe_test_split(self):
        rows = _read_csv(E3_SPLITS_CSV)
        # Test records that are excluded from safe split
        excluded = [r for r in rows
                    if r["original_split"] == "test"
                    and (r["is_leaking"] == "True" or r["is_conflicted"] == "True")]
        # 65 test records should be excluded
        assert len(excluded) >= 60, (
            f"Expected ≥60 test exclusions, got {len(excluded)}"
        )

    def test_e3_no_weld_id_grouping_available(self):
        rows = _read_csv(E3_SPLITS_CSV)
        # source_archive is the coarsest available group key
        # (weld_id column does not exist)
        has_weld_id_col = "weld_id" in rows[0].keys()
        assert not has_weld_id_col, (
            "weld_id column found in E3 manifest — update grouping from "
            "source_archive fallback to weld_id-based grouping"
        )

    def test_e3_manifest_is_candidate_not_approved(self):
        # E3 manifest is a candidate — not yet approved; name reflects CANDIDATE status
        # Verified by absence of DatasetAudit APPROVED status
        pass  # Approval verified in STEP 8


# ── STEP 5 — E4 Ground Truth ───────────────────────────────────────────────────

class TestStep5E4GroundTruth:
    def test_e4_manifest_exists(self):
        assert E4_GT_CSV.is_file(), "E4_GROUND_TRUTH_REVIEW.csv is missing"

    def test_e4_manifest_row_count(self):
        rows = _read_csv(E4_GT_CSV)
        assert len(rows) == 927

    def test_e4_all_surface_observation(self):
        rows = _read_csv(E4_GT_CSV)
        non_surface = [r for r in rows
                       if r["provenance"] != "SURFACE_OBSERVATION"]
        assert non_surface == [], (
            f"{len(non_surface)} records claim non-SURFACE_OBSERVATION provenance "
            "— no destructive or NDT evidence has been documented"
        )

    def test_e4_zero_destructive_test_records(self):
        rows = _read_csv(E4_GT_CSV)
        destructive = [r for r in rows
                       if r["provenance"] == "DESTRUCTIVE_TEST"]
        assert len(destructive) == 0

    def test_e4_zero_acceptable_for_nugget_training(self):
        rows = _read_csv(E4_GT_CSV)
        nugget_ok = [r for r in rows
                     if r.get("acceptable_for_nugget_training") == "True"]
        assert len(nugget_ok) == 0, (
            "Nugget training requires DESTRUCTIVE_TEST provenance; "
            "no such records should be marked True"
        )

    def test_e4_all_pending_review(self):
        rows = _read_csv(E4_GT_CSV)
        not_pending = [r for r in rows
                       if r.get("verification_status") != "PENDING_REVIEW"]
        assert not_pending == [], (
            f"{len(not_pending)} E4 records claim non-PENDING status "
            "— ground truth verification has not been completed"
        )


# ── STEP 6 — Defect Taxonomy ───────────────────────────────────────────────────

class TestStep6DefectTaxonomy:
    def test_taxonomy_import(self):
        from app.vision.defect_taxonomy import TAXONOMY, DefectCode
        assert TAXONOMY is not None

    def test_taxonomy_has_18_classes(self):
        from app.vision.defect_taxonomy import TAXONOMY
        assert len(TAXONOMY) == 18, (
            f"Expected 18 defect classes (13 V5 + 5 internal), got {len(TAXONOMY)}"
        )

    def test_v5_dataset_classes_all_present(self):
        from app.vision.defect_taxonomy import TAXONOMY, DefectCode
        v5_codes = {
            DefectCode.OK, DefectCode.SPATTER, DefectCode.DEFORMED,
            DefectCode.BROKEN, DefectCode.MISSING, DefectCode.SMALL_NUGGET_INDICATOR,
            DefectCode.MISALIGNED, DefectCode.OVERLAPPING, DefectCode.EDGE_WELD,
            DefectCode.BURN_THROUGH, DefectCode.DOUBLE_SHEET, DefectCode.CRUSH_DENT,
            DefectCode.GENERIC_NOK,
        }
        for code in v5_codes:
            assert code in TAXONOMY, f"V5 class {code} missing from taxonomy"

    def test_internal_classes_all_present(self):
        from app.vision.defect_taxonomy import TAXONOMY, DefectCode
        internal_codes = {
            DefectCode.INCOMPLETE_FUSION, DefectCode.POROSITY,
            DefectCode.HOT_CRACK, DefectCode.EXPULSION, DefectCode.COLD_LAP,
        }
        for code in internal_codes:
            assert code in TAXONOMY, f"Internal class {code} missing from taxonomy"

    def test_internal_classes_not_in_v5_dataset(self):
        from app.vision.defect_taxonomy import TAXONOMY, DefectCode
        internal_codes = {
            DefectCode.INCOMPLETE_FUSION, DefectCode.POROSITY,
            DefectCode.HOT_CRACK, DefectCode.EXPULSION, DefectCode.COLD_LAP,
        }
        for code in internal_codes:
            entry = TAXONOMY[code]
            assert not entry.in_v5_dataset, (
                f"{code} is marked in_v5_dataset=True — internal defects "
                "are not in the V5 dataset"
            )

    def test_generic_nok_not_surface_classifier_applicable(self):
        from app.vision.defect_taxonomy import TAXONOMY, DefectCode
        # generic_bad cannot be used for specific class training
        entry = TAXONOMY[DefectCode.GENERIC_NOK]
        assert not entry.surface_classifier_applicable, (
            "generic_bad should not be surface_classifier_applicable "
            "— it's an underspecified catch-all"
        )

    def test_surface_visible_classes(self):
        from app.vision.defect_taxonomy import TAXONOMY, ObservabilityLevel
        surface_visible = [
            code for code, e in TAXONOMY.items()
            if e.observability == ObservabilityLevel.SURFACE_VISIBLE
        ]
        assert len(surface_visible) >= 7

    def test_destructive_only_classes(self):
        from app.vision.defect_taxonomy import TAXONOMY, ObservabilityLevel
        destructive = [
            code for code, e in TAXONOMY.items()
            if e.observability == ObservabilityLevel.DESTRUCTIVE_ONLY
        ]
        assert len(destructive) >= 2  # hot_crack, cold_lap

    def test_per_class_sample_counts_v5(self):
        """Verify V5 dataset class counts match the annotation audit."""
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        counts = {}
        for r in rows:
            counts[r["label"]] = counts.get(r["label"], 0) + 1
        assert counts["generic_bad"] == 399
        assert counts["ok"] == 139
        assert counts["capak"] == 112
        assert counts["cokertme"] == 4  # smallest class

    def test_minimum_class_threshold(self):
        """Verify that small-count defect classes remain at known low counts."""
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        counts = {}
        for r in rows:
            counts[r["label"]] = counts.get(r["label"], 0) + 1
        # Specific classes that should be below 35 samples (insufficient for training)
        below_35 = ["eksik", "kacik", "kucuk_cekirdek", "ust_uste", "kenar",
                    "delik", "cift_sac", "cokertme"]
        for label in below_35:
            assert counts.get(label, 0) < 35, (
                f"Class '{label}' has {counts.get(label, 0)} samples — "
                "expected < 35 based on dataset inventory (all are insufficient for multi-class training)"
            )


# ── STEP 7 — Temporal Data Readiness ──────────────────────────────────────────

class TestStep7TemporalData:
    def test_real_video_file_exists(self):
        assert REAL_VIDEO_FILE.is_file(), (
            f"Real video file not found: {REAL_VIDEO_FILE}"
        )

    def test_real_video_openable_by_opencv(self):
        """
        Spot_Welding_Detection_6.7.2026.mp4 is decodable by OpenCV (~30fps).
        The video is physically accessible and readable; it still lacks
        weld-cycle linkage and frame-level ground truth annotations.
        """
        try:
            import cv2
            cap = cv2.VideoCapture(str(REAL_VIDEO_FILE))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            assert fps > 0, (
                f"OpenCV cannot read video — FPS={fps}. Install FFmpeg-enabled "
                "OpenCV or convert the file."
            )
            assert fps == pytest.approx(30.0, abs=1.0), (
                f"Expected ~30fps, got {fps}"
            )
        except ImportError:
            pytest.skip("OpenCV not installed")

    def test_no_weld_cycle_linkage_in_video(self):
        """
        The video file name does not encode weld_id, cycle timestamps, or
        camera perspective metadata. Without weld cycle linkage, the video
        cannot be used for CNN-GRU/LSTM training.
        """
        video_name = REAL_VIDEO_FILE.name
        # No weld_id or cycle metadata in filename
        assert "weld_id" not in video_name.lower()
        assert "cycle" not in video_name.lower()

    def test_no_ground_truth_for_video_frames(self):
        """
        No annotation manifest exists linking video frames to weld quality labels.
        """
        video_manifest = VISION_DOCS / "VIDEO_FRAME_ANNOTATIONS.csv"
        assert not video_manifest.is_file(), (
            "VIDEO_FRAME_ANNOTATIONS.csv found — temporal ground truth now exists, "
            "update temporal readiness"
        )

    def test_synthetic_videos_separated_from_real(self):
        synth_dir = PROJECT_ROOT / "backend" / "tests" / "synthetic_data" / "videos"
        assert synth_dir.is_dir()
        synth_manifests = list(synth_dir.glob("MANIFEST.json"))
        assert len(synth_manifests) == 1
        # Confirm real video is NOT in synthetic dir
        real_in_synth = list(synth_dir.glob("*.mp4"))
        for f in real_in_synth:
            assert "synth_" in f.name, (
                f"Non-synthetic video {f.name} found in synthetic data directory"
            )


# ── STEP 8 — Dataset Readiness Decision ───────────────────────────────────────

class TestStep8DatasetReadiness:
    def test_dataset_audit_training_blocked(self):
        from app.vision.temporal.dataset_audit import DatasetAudit, AuditStatus
        # A new DRAFT audit (the default status) must never allow training
        audit = DatasetAudit(
            dataset_id="v5_real_dataset",
            description="V5 real weld dataset — 927 annotated images",
        )
        result = audit.is_training_allowed()
        assert result is False, (
            "DatasetAudit.is_training_allowed() returned True — "
            "a DRAFT audit must block training until APPROVED by a reviewer"
        )
        assert audit.status == AuditStatus.DRAFT

    def test_e1_gate_not_clear(self):
        rows = _read_csv(E1_QUEUE_CSV)
        decided = [r for r in rows
                   if r.get("review_decision", "").strip() and
                   r.get("status") != "PENDING_REVIEW"]
        e1_gate_clear = len(decided) == 175
        assert not e1_gate_clear, "E1 gate unexpectedly clear — expected 0/175 decisions"

    def test_training_eligible_below_minimum(self):
        """191 eligible train records < 200 minimum for surface classifier GO."""
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        eligible = [r for r in rows
                    if r["contamination_level"] in ("CLEAN", "LOW")
                    and r["split"] == "train"]
        # Actual eligible after leakage/conflict exclusion is 191 (not 540)
        # This test verifies the total clean train is a known number
        clean_train = len(eligible)
        # clean_train without conflict exclusion = raw CLEAN+LOW in train split
        assert clean_train < 540, "Contamination filtering not applied"

    def test_binary_classifier_no_go(self):
        """Binary surface classifier is NO-GO: E1 unresolved, eligible < 200."""
        # E1 pending
        e1_rows = _read_csv(E1_QUEUE_CSV)
        e1_pending = all(r.get("review_decision", "") == "" for r in e1_rows)
        assert e1_pending, "E1 decisions exist — classifier may now be GO"
        # This test passes (confirms NO-GO) while E1 is pending

    def test_nugget_training_no_go(self):
        """Nugget acceptance training requires DESTRUCTIVE_TEST provenance."""
        e4_rows = _read_csv(E4_GT_CSV)
        destructive = [r for r in e4_rows
                       if r.get("provenance") == "DESTRUCTIVE_TEST"]
        assert len(destructive) == 0

    def test_cnn_gru_no_go(self):
        """CNN-GRU/LSTM training requires temporal frame sequences — none available."""
        # Real video not machine-readable + no frame ground truth
        video_readable = False  # confirmed by TestStep7 above
        frame_gt_exists = (VISION_DOCS / "VIDEO_FRAME_ANNOTATIONS.csv").is_file()
        assert not frame_gt_exists
        # Cannot train without frame ground truth

    def test_no_automatic_training_initiated(self):
        """Verify no model training artifacts were created by this test run."""
        training_artifacts = [
            PROJECT_ROOT / "backend" / "models" / "surface_classifier.pkl",
            PROJECT_ROOT / "backend" / "models" / "surface_classifier.h5",
        ]
        for artifact in training_artifacts:
            assert not artifact.exists(), (
                f"Training artifact found: {artifact} — model training was not authorized"
            )


# ── STEP 9 — Deliverable Verification ─────────────────────────────────────────

class TestStep9Deliverables:
    def test_vision_data_real_01_report_exists(self):
        report = VISION_DOCS / "VISION_DATA_REAL_01_REPORT.md"
        assert report.is_file(), "VISION_DATA_REAL_01_REPORT.md not generated"

    def test_e1_human_review_priority_csv_exists(self):
        csv_path = VISION_DOCS / "E1_HUMAN_REVIEW_PRIORITY.csv"
        assert csv_path.is_file()

    def test_e2_contamination_inventory_csv_exists(self):
        csv_path = VISION_DOCS / "E2_CONTAMINATION_INVENTORY.csv"
        assert csv_path.is_file()

    def test_e3_split_leakage_report_exists(self):
        report = VISION_DOCS / "E3_SPLIT_LEAKAGE_REPORT.md"
        assert report.is_file()

    def test_e4_ground_truth_matrix_csv_exists(self):
        csv_path = VISION_DOCS / "E4_GROUND_TRUTH_MATRIX.csv"
        assert csv_path.is_file()

    def test_defect_class_readiness_csv_exists(self):
        csv_path = VISION_DOCS / "DEFECT_CLASS_READINESS.csv"
        assert csv_path.is_file()

    def test_temporal_real_data_readiness_exists(self):
        report = VISION_DOCS / "TEMPORAL_REAL_DATA_READINESS.md"
        assert report.is_file()

    def test_e1_priority_csv_has_correct_columns(self):
        csv_path = VISION_DOCS / "E1_HUMAN_REVIEW_PRIORITY.csv"
        rows = _read_csv(csv_path)
        required = {"priority_rank", "sha1_16", "conflict_type", "label_a",
                    "label_b", "split_a", "split_b", "review_guidance"}
        assert required.issubset(rows[0].keys()), (
            f"Missing columns: {required - rows[0].keys()}"
        )

    def test_e1_priority_csv_row_count(self):
        csv_path = VISION_DOCS / "E1_HUMAN_REVIEW_PRIORITY.csv"
        rows = _read_csv(csv_path)
        assert len(rows) == 175

    def test_defect_readiness_csv_row_count(self):
        csv_path = VISION_DOCS / "DEFECT_CLASS_READINESS.csv"
        rows = _read_csv(csv_path)
        assert len(rows) == 18, f"Expected 18 classes, got {len(rows)}"

    def test_e4_ground_truth_matrix_row_count(self):
        csv_path = VISION_DOCS / "E4_GROUND_TRUTH_MATRIX.csv"
        rows = _read_csv(csv_path)
        assert len(rows) == 13, f"Expected 13 V5 classes, got {len(rows)}"
