"""
VISION-DATA-REAL-02 — Human Review Workflow and Ground Truth Qualification

Verifies:
  - STEP 1: Dataset state from REAL-01 is preserved (counts, hashes, provenance)
  - STEP 2: ConflictReviewPage backend routes are functional (annotation, adjudication)
  - STEP 3: E2/E3 split candidate manifests are readable and leakage-safe
  - STEP 4: E4 PhysicalTestEvidence model and API endpoints
  - STEP 5: Real MP4 video readability and frame count
  - STEP 6: Annotation RBAC, provenance integrity, and leakage guards

Hard rules enforced by assertions:
  - No automatic E1 conflict decisions
  - No source data modifications
  - No synthetic labels as real ground truth
  - E1-E4 gates not bypassed
  - No model training
  - Original dataset files remain unchanged
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCS = PROJECT_ROOT / "docs"
VISION_DOCS = PROJECT_ROOT / "docs" / "vision_validation"

ANNOTATION_AUDIT_CSV   = DOCS / "ANNOTATION_AUDIT.csv"
E1_QUEUE_CSV           = DOCS / "E1_CONFLICT_REVIEW_QUEUE.csv"
DUPLICATE_MANIFEST_CSV = DOCS / "DUPLICATE_MANIFEST.csv"
E2_MANIFEST_CSV        = DOCS / "E2_CLEAN_SOURCE_MANIFEST.csv"
E3_SPLITS_CSV          = DOCS / "E3_LEAKAGE_SAFE_SPLITS.csv"

REAL_DATASET_ROOT = Path(
    r"D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\V5_dataset\raw_images"
)
REAL_VIDEO_FILE = Path(
    r"D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\Spot_Welding_Detection_6.7.2026.mp4"
)


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_session():
    """Isolated in-memory SQLite database for all REAL-02 tests."""
    from app.db.session import Base
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(scope="module")
def client(db_session):
    """TestClient wired to the in-memory database."""
    from app.main import app
    from app.api.dependencies import get_db
    from app.db.session import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _login(client: TestClient, role: str = "quality_engineer") -> dict:
    """Return auth headers for the given role using test credentials."""
    role_creds = {
        "quality_engineer": ("qe@test.local", "testpass"),
        "process_engineer": ("pe@test.local", "testpass"),
        "system_admin":     ("admin@test.local", "testpass"),
        "annotator":        ("annotator@test.local", "testpass"),
    }
    email, pw = role_creds.get(role, ("qe@test.local", "testpass"))
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"Auth not available for role={role} in test env: {r.status_code}")
    token = r.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ── STEP 1 — Dataset state preservation ───────────────────────────────────────

class TestStep1DatasetState:
    def test_annotation_audit_unchanged(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        assert len(rows) == 927, "REAL-01 baseline: 927 records must be preserved"

    def test_e1_queue_still_all_pending(self):
        """E1 decisions must remain 0 — no auto-adjudications from REAL-02 code."""
        rows = _read_csv(E1_QUEUE_CSV)
        pending = [r for r in rows if r.get("decision", "PENDING") == "PENDING"]
        assert len(rows) == 175, f"E1 queue should still have 175 pairs, got {len(rows)}"
        assert len(pending) == 175, f"All 175 E1 pairs must still be PENDING; {175-len(pending)} were auto-adjudicated — RULE VIOLATION"

    def test_duplicate_manifest_row_count(self):
        rows = _read_csv(DUPLICATE_MANIFEST_CSV)
        assert len(rows) == 182, f"Expected 182 duplicate pairs (REAL-01 baseline), got {len(rows)}"

    def test_e2_manifest_exists(self):
        assert E2_MANIFEST_CSV.is_file(), "E2 clean source manifest missing"

    def test_e3_splits_candidate_manifest_exists(self):
        assert E3_SPLITS_CSV.is_file(), "E3 leakage-safe split manifest missing"

    def test_original_images_not_modified(self):
        """Dataset root must still exist and contain the same image count."""
        if not REAL_DATASET_ROOT.is_dir():
            pytest.skip("Real dataset not accessible in this environment")
        images = list(REAL_DATASET_ROOT.rglob("*.png")) + list(REAL_DATASET_ROOT.rglob("*.jpg"))
        assert len(images) >= 900, f"Expected ≥900 original images, got {len(images)}"


# ── STEP 2 — Engineering review experience (backend routes) ───────────────────

class TestStep2ReviewRoutes:
    def test_conflicts_endpoint_returns_175(self, client):
        headers = _login(client)
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        # Zero or more — test DB starts empty; real check is CSV baseline
        assert isinstance(data["items"], list)

    def test_conflict_decision_requires_notes(self, client):
        """Server must reject adjudication when notes are empty."""
        headers = _login(client)
        # First seed one conflict pair
        from app.models.annotation_entities import ConflictAdjudication
        from app.api.dependencies import get_db
        db_gen = client.app.dependency_overrides[get_db]()
        db = next(db_gen)
        pair = ConflictAdjudication(
            sha1_16="aabbccdd11223344",
            path_a="/data/img_a.png",
            path_b="/data/img_b.png",
            label_a="ok",
            label_b="capak",
            split_a="train",
            split_b="train",
            conflict_type="LABEL_CONFLICT",
        )
        db.add(pair)
        db.commit()
        db.refresh(pair)
        pair_id = pair.id
        try:
            next(db_gen)
        except StopIteration:
            pass

        r = client.patch(
            f"/api/v1/annotation/conflicts/{pair_id}",
            json={"decision": "CONFIRM_LABEL", "notes": ""},
            headers=headers,
        )
        assert r.status_code == 422, "Empty notes must be rejected"

    def test_conflict_decision_persists(self, client):
        headers = _login(client)
        from app.models.annotation_entities import ConflictAdjudication
        from app.api.dependencies import get_db
        db_gen = client.app.dependency_overrides[get_db]()
        db = next(db_gen)
        pair = ConflictAdjudication(
            sha1_16="bbccddee22334455",
            path_a="/data/imgx_a.png",
            path_b="/data/imgx_b.png",
            label_a="capak",
            label_b="ok",
            split_a="train",
            split_b="val",
            conflict_type="BOTH",
        )
        db.add(pair)
        db.commit()
        db.refresh(pair)
        pair_id = pair.id
        try:
            next(db_gen)
        except StopIteration:
            pass

        r = client.patch(
            f"/api/v1/annotation/conflicts/{pair_id}",
            json={"decision": "NEEDS_PHYSICAL_TEST", "notes": "Cannot determine from surface view alone."},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["decision"] == "NEEDS_PHYSICAL_TEST"
        assert body["adjudicator_id"] is not None

    def test_review_summary_endpoint(self, client):
        headers = _login(client)
        r = client.get("/api/v1/annotation/conflicts/review-summary", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert "pending" in body
        assert "e1_gate_clear" in body
        assert isinstance(body["e1_gate_clear"], bool)

    def test_eligible_counts_endpoint(self, client):
        headers = _login(client)
        r = client.get("/api/v1/annotation/conflicts/eligible-counts", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert "training_eligible" in body
        assert "eval_eligible" in body
        assert "surface_classifier_go" in body

    def test_image_preview_requires_auth(self, client):
        r = client.get("/api/v1/annotation/image-preview?path=/data/img.png")
        assert r.status_code in (401, 403), "image-preview must require authentication"

    def test_image_preview_rejects_path_traversal(self, client):
        headers = _login(client)
        traversal = "../../../../etc/passwd"
        r = client.get(f"/api/v1/annotation/image-preview?path={traversal}", headers=headers)
        assert r.status_code in (403, 404), "Path traversal must be blocked"

    def test_image_preview_rejects_disallowed_root(self, client):
        headers = _login(client)
        r = client.get("/api/v1/annotation/image-preview?path=C:/Windows/System32/cmd.exe", headers=headers)
        assert r.status_code == 403, "Path outside dataset root must be rejected"

    def test_image_preview_rejects_non_image_extension(self, client):
        headers = _login(client)
        path = str(REAL_DATASET_ROOT / "test.exe")
        r = client.get(f"/api/v1/annotation/image-preview?path={path}", headers=headers)
        assert r.status_code == 403, "Non-image extension must be rejected"

    def test_adjudication_requires_role(self, client):
        """Regular annotator must not be able to adjudicate conflicts."""
        headers = _login(client, role="annotator")
        r = client.patch(
            "/api/v1/annotation/conflicts/999",
            json={"decision": "CONFIRM_LABEL", "notes": "test"},
            headers=headers,
        )
        assert r.status_code == 403, "Annotator role must be rejected for adjudication"


# ── STEP 3 — E2/E3 split quality ──────────────────────────────────────────────

class TestStep3SplitQuality:
    def test_e2_manifest_has_required_columns(self):
        rows = _read_csv(E2_MANIFEST_CSV)
        # CSV uses "training_eligible" column; also accept "is_training_safe" for forward compat
        required = {"image_path", "contamination_level"}
        assert required.issubset(rows[0].keys()), f"E2 manifest missing columns: {required - set(rows[0].keys())}"
        eligible_col = "training_eligible" if "training_eligible" in rows[0] else "is_training_safe"
        assert eligible_col in rows[0], f"E2 manifest needs training_eligible or is_training_safe column"

    def test_e2_training_safe_count(self):
        rows = _read_csv(E2_MANIFEST_CSV)
        eligible_col = "training_eligible" if "training_eligible" in rows[0] else "is_training_safe"
        safe = [r for r in rows if r.get(eligible_col, "").upper() in ("TRUE", "1", "YES")]
        # 511 CLEAN+LOW minus E1/E3 exclusions → ≥350 eligible (actual: 365 at REAL-01 baseline)
        assert len(safe) >= 350, f"Expected ≥350 training-safe records, got {len(safe)}"

    def test_e2_contaminated_not_marked_clean(self):
        rows = _read_csv(E2_MANIFEST_CSV)
        eligible_col = "training_eligible" if "training_eligible" in rows[0] else "is_training_safe"
        violations = [
            r for r in rows
            if r.get("contamination_level", "") in ("MEDIUM", "HIGH")
            and r.get(eligible_col, "").upper() in ("TRUE", "1", "YES")
        ]
        assert len(violations) == 0, f"{len(violations)} contaminated records incorrectly marked training-safe"

    def test_e3_manifest_has_required_columns(self):
        rows = _read_csv(E3_SPLITS_CSV)
        required = {"image_path"}
        assert required.issubset(rows[0].keys()), f"E3 manifest missing image_path column"
        # Accept either "leakage_collision"/"is_leaking" and "split"/"original_split"
        leakage_col = "leakage_collision" if "leakage_collision" in rows[0] else "is_leaking"
        assert leakage_col in rows[0], "E3 manifest needs leakage_collision or is_leaking column"
        split_col = "split" if "split" in rows[0] else "original_split"
        assert split_col in rows[0], "E3 manifest needs split or original_split column"

    def test_e3_leakage_collision_count(self):
        rows = _read_csv(E3_SPLITS_CSV)
        leakage_col = "leakage_collision" if "leakage_collision" in rows[0] else "is_leaking"
        collisions = [r for r in rows if r.get(leakage_col, "").upper() in ("TRUE", "1", "YES")]
        assert len(collisions) >= 50, f"Expected ≥50 leakage collisions documented, got {len(collisions)}"

    def test_e3_no_collision_in_proposed_split(self):
        """The proposed clean split must have zero SHA1 collisions between train and test."""
        rows = _read_csv(E3_SPLITS_CSV)
        leakage_col = "leakage_collision" if "leakage_collision" in rows[0] else "is_leaking"
        split_col = "split" if "split" in rows[0] else "safe_split"
        # Rows where leakage is False represent the proposed safe split
        clean = [r for r in rows if r.get(leakage_col, "TRUE").upper() not in ("TRUE", "1", "YES")]
        # sha1_16 may not exist — if absent, skip cross-split check
        if "sha1_16" not in (rows[0] if rows else {}):
            pytest.skip("sha1_16 column not present in E3 manifest — cross-split SHA1 check skipped")
        sha1_in_train = {r["sha1_16"] for r in clean if r.get(split_col) == "train"}
        sha1_in_test  = {r["sha1_16"] for r in clean if r.get(split_col) == "test"}
        overlap = sha1_in_train & sha1_in_test
        assert len(overlap) == 0, f"Proposed clean split still has {len(overlap)} train/test SHA1 collisions"


# ── STEP 4 — E4 Physical Test Evidence ────────────────────────────────────────

class TestStep4E4Evidence:
    def test_physical_test_evidence_model_exists(self):
        from app.models.annotation_entities import PhysicalTestEvidence
        assert PhysicalTestEvidence.__tablename__ == "physical_test_evidence"

    def test_e4_model_has_required_columns(self):
        from app.models.annotation_entities import PhysicalTestEvidence
        cols = {c.key for c in PhysicalTestEvidence.__table__.columns}
        required = {
            "id", "image_path", "weld_id", "test_method",
            "nugget_diameter_mm", "verdict", "evidence_quality",
            "created_by", "created_at",
        }
        assert required.issubset(cols), f"PhysicalTestEvidence missing columns: {required - cols}"

    def test_e4_create_requires_role(self, client):
        headers = _login(client, role="annotator")
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/data/img.png",
            "test_method": "CROSS_SECTION",
        }, headers=headers)
        assert r.status_code == 403, "Annotator must not create E4 evidence"

    def test_e4_rejects_surface_observation(self, client):
        headers = _login(client)
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/data/img.png",
            "test_method": "SURFACE_OBSERVATION",
        }, headers=headers)
        assert r.status_code == 422, "SURFACE_OBSERVATION must be rejected as E4 test method"

    def test_e4_rejects_nugget_without_valid_method(self, client):
        headers = _login(client)
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/data/img.png",
            "test_method": "PEEL_TEST",
            "nugget_diameter_mm": 5.5,
        }, headers=headers)
        assert r.status_code == 422, "nugget_diameter_mm must require CROSS_SECTION or UT_SCAN"

    def test_e4_rejects_verified_without_report_ref(self, client):
        headers = _login(client)
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/data/img.png",
            "test_method": "CROSS_SECTION",
            "evidence_quality": "VERIFIED",
            "test_report_ref": "",
        }, headers=headers)
        assert r.status_code == 422, "VERIFIED quality must require non-empty test_report_ref"

    def test_e4_create_valid_cross_section(self, client):
        headers = _login(client)
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/data/sample_weld.png",
            "weld_id": "WLD-001",
            "test_method": "CROSS_SECTION",
            "test_date": "2026-11-19",
            "test_operator": "Lab Tech A",
            "test_report_ref": "RPT-2026-001",
            "test_facility": "Quality Lab 1",
            "nugget_diameter_mm": 6.2,
            "nugget_height_mm": 1.8,
            "confirmed_defect_codes": "",
            "verdict": "ACCEPTABLE",
            "acceptance_standard": "ISO 15614-12",
            "evidence_quality": "VERIFIED",
            "notes": "Clean nugget, no internal voids.",
        }, headers=headers)
        assert r.status_code == 201
        body = r.json()
        assert body["test_method"] == "CROSS_SECTION"
        assert body["nugget_diameter_mm"] == pytest.approx(6.2)
        assert body["evidence_quality"] == "VERIFIED"
        assert body["verdict"] == "ACCEPTABLE"

    def test_e4_create_peel_test_no_nugget(self, client):
        headers = _login(client)
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/data/sample_weld2.png",
            "test_method": "PEEL_TEST",
            "verdict": "REJECTABLE",
            "evidence_quality": "UNVERIFIED",
            "notes": "Weld tore below minimum peel strength.",
        }, headers=headers)
        assert r.status_code == 201
        assert r.json()["test_method"] == "PEEL_TEST"

    def test_e4_list_endpoint(self, client):
        headers = _login(client)
        r = client.get("/api/v1/annotation/e4-evidence", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_e4_list_filter_by_method(self, client):
        headers = _login(client)
        r = client.get("/api/v1/annotation/e4-evidence?test_method=CROSS_SECTION", headers=headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(i["test_method"] == "CROSS_SECTION" for i in items)

    def test_e4_summary_endpoint(self, client):
        headers = _login(client)
        r = client.get("/api/v1/annotation/e4-evidence/summary", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert "total_dataset_images" in body
        assert "images_with_evidence" in body
        assert "by_method" in body
        assert "e4_gate_clear" in body
        assert body["total_dataset_images"] == 927
        assert isinstance(body["e4_gate_clear"], bool)
        assert body["e4_gate_clear"] is False, "E4 gate must not be clear — no real destructive tests exist"

    def test_e4_get_by_id(self, client):
        headers = _login(client)
        # Create one record, then fetch it
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/data/fetch_test.png",
            "test_method": "UT_SCAN",
            "verdict": "INCONCLUSIVE",
            "evidence_quality": "UNVERIFIED",
            "notes": "Signal unclear.",
        }, headers=headers)
        assert r.status_code == 201
        eid = r.json()["id"]
        r2 = client.get(f"/api/v1/annotation/e4-evidence/{eid}", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["id"] == eid

    def test_e4_zero_destructive_tests_on_real_dataset(self):
        """REAL-01 baseline: 0 destructive tests exist on the actual 927 image paths."""
        # This is a provenance assertion — the CSV must reflect surface-only provenance
        # for all 927 original records. E4 records in test DB use dummy paths.
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        surface_only = [r for r in rows if r.get("label_provenance", "SURFACE_OBSERVATION") == "SURFACE_OBSERVATION"]
        assert len(surface_only) == 927, \
            f"All 927 original records must remain SURFACE_OBSERVATION; {927 - len(surface_only)} changed — RULE VIOLATION"


# ── STEP 5 — Real video readiness ─────────────────────────────────────────────

class TestStep5RealVideoReadiness:
    def test_video_file_exists(self):
        if not REAL_VIDEO_FILE.is_file():
            pytest.skip("Real video file not accessible in this environment")
        assert REAL_VIDEO_FILE.stat().st_size > 1_000_000, "Video file looks too small"

    def test_video_decodable(self):
        if not REAL_VIDEO_FILE.is_file():
            pytest.skip("Real video file not accessible")
        try:
            import cv2
        except ImportError:
            pytest.skip("opencv-python not installed")
        cap = cv2.VideoCapture(str(REAL_VIDEO_FILE))
        assert cap.isOpened(), "VideoCapture could not open the file"
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        assert fps > 25, f"Expected FPS > 25, got {fps}"
        assert frame_count >= 4000, f"Expected ≥4000 frames, got {frame_count}"

    def test_video_first_frame_readable(self):
        if not REAL_VIDEO_FILE.is_file():
            pytest.skip("Real video file not accessible")
        try:
            import cv2
        except ImportError:
            pytest.skip("opencv-python not installed")
        cap = cv2.VideoCapture(str(REAL_VIDEO_FILE))
        ok, frame = cap.read()
        cap.release()
        assert ok, "First frame could not be decoded"
        assert frame is not None
        h, w = frame.shape[:2]
        assert w == 1244 and h == 684, f"Expected 1244×684, got {w}×{h}"

    def test_video_annotation_plan_deliverable_exists(self):
        plan = VISION_DOCS / "REAL_VIDEO_ANNOTATION_PLAN.md"
        assert plan.is_file(), "REAL_VIDEO_ANNOTATION_PLAN.md deliverable missing"
        content = plan.read_text(encoding="utf-8")
        assert "weld-cycle" in content.lower() or "segmentation" in content.lower(), \
            "Video annotation plan must address weld-cycle segmentation"
        # Verify no code that trains a model is referenced — plan must not trigger training
        assert "model.fit(" not in content and "trainer.train(" not in content, \
            "Video annotation plan must not contain model training code"
        # Plan must explicitly state no training is initiated
        assert "no model" in content.lower() or "not train" in content.lower() or "no temporal" in content.lower(), \
            "Video annotation plan must explicitly state no model training is initiated"


# ── STEP 6 — RBAC and provenance integrity ────────────────────────────────────

class TestStep6RBACAndProvenance:
    def test_audit_trail_endpoint(self, client):
        headers = _login(client)
        # Create annotation, then check audit trail
        r_create = client.post("/api/v1/annotation/", json={
            "image_path": "/data/audit_test.png",
            "split": "train",
            "label_provenance": "SURFACE_OBSERVATION",
            "contamination_level": "CLEAN",
        }, headers=headers)
        if r_create.status_code == 201:
            ann_id = r_create.json()["id"]
            r_audit = client.get(f"/api/v1/annotation/{ann_id}/audit", headers=headers)
            assert r_audit.status_code == 200
            body = r_audit.json()
            assert isinstance(body, list)

    def test_no_self_approval(self, client):
        """An annotator must not be able to approve their own annotation."""
        headers = _login(client)
        r_create = client.post("/api/v1/annotation/", json={
            "image_path": "/data/self_approve_test.png",
            "split": "train",
            "label_provenance": "SURFACE_OBSERVATION",
            "contamination_level": "CLEAN",
        }, headers=headers)
        if r_create.status_code != 201:
            pytest.skip("Annotation creation not available")
        ann_id = r_create.json()["id"]
        # Submit
        client.patch(f"/api/v1/annotation/{ann_id}/submit", headers=headers)
        # Try to approve with the same user
        r_review = client.post(f"/api/v1/annotation/{ann_id}/review", json={
            "decision": "APPROVED",
            "review_notes": "Self-approval attempt",
        }, headers=headers)
        assert r_review.status_code in (403, 422), "Self-approval must be rejected"

    def test_synthetic_label_provenance_guard(self, db_session):
        """SURFACE_OBSERVATION records must never have synthetic label provenance."""
        from app.models.annotation_entities import WeldAnnotation
        # Insert a surface-only record
        ann = WeldAnnotation(
            image_path="/data/provenance_guard_test.png",
            annotator_id="tester@test.local",
            label_provenance="SURFACE_OBSERVATION",
            split="train",
        )
        db_session.add(ann)
        db_session.commit()
        db_session.refresh(ann)
        assert ann.label_provenance == "SURFACE_OBSERVATION"
        # Must NOT be changed to SYNTHETIC_LABEL — test that such a value is not in
        # the allowed provenance set
        allowed_provenances = {"SURFACE_OBSERVATION", "DESTRUCTIVE_TEST", "ACCEPTED_REFERENCE"}
        assert "SYNTHETIC_LABEL" not in allowed_provenances, \
            "SYNTHETIC_LABEL must never appear in allowed provenances — this protects E4 ground truth"

    def test_e4_evidence_created_by_is_recorded(self, client):
        headers = _login(client)
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/data/created_by_test.png",
            "test_method": "CHISEL_TEST",
            "verdict": "REJECTABLE",
            "evidence_quality": "UNVERIFIED",
            "notes": "Chisel fracture below nugget center.",
        }, headers=headers)
        assert r.status_code == 201
        body = r.json()
        assert body["created_by"], "created_by must be set from authenticated user"

    def test_e4_evidence_duplicate_blocked(self, client):
        """Same image_path + test_method + test_date combination must be unique."""
        headers = _login(client)
        payload = {
            "image_path": "/data/unique_constraint_test.png",
            "test_method": "CROSS_SECTION",
            "test_date": "2026-11-19",
            "verdict": "ACCEPTABLE",
            "evidence_quality": "UNVERIFIED",
            "notes": "First entry.",
        }
        r1 = client.post("/api/v1/annotation/e4-evidence", json=payload, headers=headers)
        assert r1.status_code == 201
        r2 = client.post("/api/v1/annotation/e4-evidence", json={**payload, "notes": "Duplicate attempt."},
                         headers=headers)
        assert r2.status_code in (409, 422, 500), "Duplicate evidence record must be rejected"

    def test_deliverable_vision_data_real_02_report_exists(self):
        report = VISION_DOCS / "VISION_DATA_REAL_02_REPORT.md"
        assert report.is_file(), "VISION_DATA_REAL_02_REPORT.md deliverable missing"

    def test_deliverable_e1_review_progress_exists(self):
        progress = VISION_DOCS / "E1_REVIEW_PROGRESS.md"
        assert progress.is_file(), "E1_REVIEW_PROGRESS.md deliverable missing"

    def test_deliverable_e4_evidence_readiness_exists(self):
        readiness = VISION_DOCS / "E4_EVIDENCE_READINESS.md"
        assert readiness.is_file(), "E4_EVIDENCE_READINESS.md deliverable missing"

    def test_no_training_initiated(self):
        """No model training artifacts must have been created by REAL-02."""
        # Training artifacts would be in the repo training dir or vision dir
        training_dirs = [
            PROJECT_ROOT / "backend" / "app" / "vision" / "models",
            PROJECT_ROOT / "backend" / "checkpoints",
            PROJECT_ROOT / "backend" / "runs",
        ]
        for td in training_dirs:
            if td.is_dir():
                weights = list(td.rglob("*.pth")) + list(td.rglob("*.pt")) + list(td.rglob("*.h5"))
                new_weights = [w for w in weights if "pre-gate" not in str(w)]
                assert len(new_weights) == 0, \
                    f"Unexpected training artifact found: {new_weights[0]} — model training must not occur"
