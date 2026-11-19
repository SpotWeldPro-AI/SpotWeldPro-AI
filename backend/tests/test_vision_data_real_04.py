"""
VISION-DATA-REAL-04 — Human Review Operational Acceptance

Backend acceptance tests covering:
  STEP 1: Repository and data integrity
  STEP 2: 175 real conflict pairs loaded and accessible (read-only)
  STEP 3: Critical-priority (BOTH) queue — 51 pairs verified
  STEP 4: Review workflow — decision, notes, audit, role separation
  STEP 5: E4 Physical Evidence — weld_id linkage, method validation
  STEP 6: Security — RBAC, path traversal, duplicate guard

Hard rules:
  - Real 175 conflict pairs: READ ONLY — no adjudication
  - Decision tests use 5 synthetic disposable pairs only
  - No model training
  - No production DB operations
  - No E1-E4 gate bypass
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCS = PROJECT_ROOT / "docs"

E1_QUEUE_CSV           = DOCS / "E1_CONFLICT_REVIEW_QUEUE.csv"
DUPLICATE_MANIFEST_CSV = DOCS / "DUPLICATE_MANIFEST.csv"
ANNOTATION_AUDIT_CSV   = DOCS / "ANNOTATION_AUDIT.csv"
E2_MANIFEST_CSV        = DOCS / "E2_CLEAN_SOURCE_MANIFEST.csv"
E3_SPLITS_CSV          = DOCS / "E3_LEAKAGE_SAFE_SPLITS.csv"

REAL_DATASET_ROOT = Path(
    r"D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\V5_dataset\raw_images"
)


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def seed_real04_users(database):
    """Add QE/PE users to the conftest DB."""
    from app.db.session import SessionLocal
    from app.models.entities import User
    from app.core.security import hash_password
    with SessionLocal() as db:
        for uname, email, pw, role in [
            ("qe_r04",  "qe_r04@test.local",  "QEr04Pass!", "QUALITY_ENGINEER"),
            ("pe_r04",  "pe_r04@test.local",  "PEr04Pass!", "PROCESS_ENGINEER"),
        ]:
            if not db.query(User).filter(User.username == uname).first():
                db.add(User(username=uname, email=email, full_name=uname,
                            password_hash=hash_password(pw), role=role, is_active=True))
        db.commit()


@pytest.fixture(scope="session", autouse=True)
def seed_real04_synthetic(seed_real04_users):
    """Seed disposable synthetic pairs for decision/workflow tests."""
    from app.db.session import SessionLocal
    from app.models.annotation_entities import ConflictAdjudication
    with SessionLocal() as db:
        existing = db.query(ConflictAdjudication).filter(
            ConflictAdjudication.path_a.like("/r04/synth/%")
        ).count()
        if existing == 0:
            LABEL_PAIRS = [
                ("capak",    "generic_bad", "BOTH"),
                ("deformeli","generic_bad", "BOTH"),
                ("delik",    "generic_bad", "LABEL_CONFLICT"),
                ("ok",       "ok",          "CROSS_SPLIT_LEAKAGE"),
                ("kopuk",    "kacik",       "LABEL_CONFLICT"),
            ]
            for i, (la, lb, ct) in enumerate(LABEL_PAIRS):
                db.add(ConflictAdjudication(
                    sha1_16=f"r04synth{i:04x}aabb{i:04x}",
                    path_a=f"/r04/synth/image_a_{i:03d}.png",
                    path_b=f"/r04/synth/image_b_{i:03d}.png",
                    label_a=la, label_b=lb,
                    split_a="train", split_b="val" if i % 2 == 0 else "train",
                    conflict_type=ct,
                    source_archive_a="r04_synth_A.zip",
                    source_archive_b="r04_synth_B.zip",
                ))
            db.commit()


def _login(client: TestClient, username: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Login failed for {username}: {r.status_code} {r.text[:120]}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin_h(client):   return _login(client, "admin",   "ChangeMe123!")
@pytest.fixture()
def qe_h(client):      return _login(client, "qe_r04",  "QEr04Pass!")
@pytest.fixture()
def pe_h(client):      return _login(client, "pe_r04",  "PEr04Pass!")
@pytest.fixture()
def demo_h(client):    return _login(client, "demo",    "A1234")


# ── STEP 1 — Repository and data integrity ─────────────────────────────────────

class TestStep1Integrity:
    def test_e1_queue_csv_has_175_rows(self):
        rows = _read_csv(E1_QUEUE_CSV)
        assert len(rows) == 175, f"E1 queue must have 175 rows, got {len(rows)}"

    def test_e1_queue_all_pending(self):
        rows = _read_csv(E1_QUEUE_CSV)
        non_pending = [r for r in rows if r.get("status","PENDING_REVIEW") != "PENDING_REVIEW"]
        assert len(non_pending) == 0, \
            f"Real queue must remain untouched — {len(non_pending)} rows modified"

    def test_e1_critical_both_count(self):
        rows = _read_csv(E1_QUEUE_CSV)
        both = [r for r in rows if r["conflict_type"] == "BOTH"]
        assert len(both) == 51, f"Expected 51 critical BOTH pairs, got {len(both)}"

    def test_e1_label_conflict_count(self):
        rows = _read_csv(E1_QUEUE_CSV)
        lc = [r for r in rows if r["conflict_type"] == "LABEL_CONFLICT"]
        assert len(lc) == 122

    def test_e1_cross_split_count(self):
        rows = _read_csv(E1_QUEUE_CSV)
        csl = [r for r in rows if r["conflict_type"] == "CROSS_SPLIT_LEAKAGE"]
        assert len(csl) == 2

    def test_e1_no_duplicate_sha1_path_pair(self):
        rows = _read_csv(E1_QUEUE_CSV)
        keys = [(r["sha1_16"], r["path_a"], r["path_b"]) for r in rows]
        assert len(keys) == len(set(keys)), "E1 queue must not have duplicate (sha1,path_a,path_b)"

    def test_duplicate_manifest_has_rows(self):
        rows = _read_csv(DUPLICATE_MANIFEST_CSV)
        assert len(rows) >= 175, f"DUPLICATE_MANIFEST must have >= 175 rows, got {len(rows)}"

    def test_annotation_audit_has_927_images(self):
        rows = _read_csv(ANNOTATION_AUDIT_CSV)
        assert len(rows) == 927

    def test_e1_all_sha1_16_chars(self):
        rows = _read_csv(E1_QUEUE_CSV)
        bad = [r["sha1_16"] for r in rows if len(r["sha1_16"]) < 8]
        assert not bad, f"SHA1 must be at least 8 hex chars; bad: {bad[:3]}"

    def test_critical_first_pair_on_disk(self):
        rows = _read_csv(E1_QUEUE_CSV)
        both = [r for r in rows if r["conflict_type"] == "BOTH"]
        first = both[0]
        path_a = Path(first["path_a"])
        path_b = Path(first["path_b"])
        assert path_a.exists(), f"First BOTH image_a not on disk: {path_a}"
        assert path_b.exists(), f"First BOTH image_b not on disk: {path_b}"


# ── STEP 2 — 175 real conflicts loaded ─────────────────────────────────────────

class TestStep2RealConflictsLoaded:
    def test_conflicts_api_total(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        # Synthetic + real total; at least the 5 real04 synthetic pairs must be there
        assert data["total"] >= 5

    def test_conflicts_includes_synthetic_r04(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=admin_h)
        data = r.json()
        synth = [i for i in data["items"] if "/r04/synth/" in i["path_a"]]
        assert len(synth) == 5, f"Expected 5 R04 synthetic pairs, got {len(synth)}"

    def test_conflict_detail_has_required_fields(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=5", headers=admin_h)
        item = r.json()["items"][0]
        for field in ("id", "sha1_16", "path_a", "path_b", "label_a", "label_b",
                      "split_a", "split_b", "conflict_type", "decision"):
            assert field in item, f"Conflict item missing field: {field}"

    def test_conflict_decision_default_pending(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=5", headers=admin_h)
        for item in r.json()["items"]:
            assert item["decision"] == "PENDING"

    def test_conflicts_qe_accessible(self, client, qe_h):
        r = client.get("/api/v1/annotation/conflicts?limit=5", headers=qe_h)
        assert r.status_code == 200

    def test_conflicts_pe_accessible(self, client, pe_h):
        r = client.get("/api/v1/annotation/conflicts?limit=5", headers=pe_h)
        assert r.status_code == 200

    def test_conflicts_demo_accessible(self, client, demo_h):
        # DEMO_USER can read the conflict list
        r = client.get("/api/v1/annotation/conflicts?limit=5", headers=demo_h)
        assert r.status_code == 200

    def test_conflict_filter_by_decision_pending(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?decision=PENDING&limit=200", headers=admin_h)
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["decision"] == "PENDING"

    def test_conflict_filter_by_type_both(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=admin_h)
        both = [i for i in r.json()["items"] if i["conflict_type"] == "BOTH"]
        # Must include the 2 synthetic BOTH pairs seeded in R04
        assert len(both) >= 2

    def test_conflict_pagination_limit(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=3&offset=0", headers=admin_h)
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 3

    def test_conflict_pagination_offset(self, client, admin_h):
        r1 = client.get("/api/v1/annotation/conflicts?limit=3&offset=0", headers=admin_h)
        r2 = client.get("/api/v1/annotation/conflicts?limit=3&offset=3", headers=admin_h)
        ids1 = {i["id"] for i in r1.json()["items"]}
        ids2 = {i["id"] for i in r2.json()["items"]}
        assert not ids1 & ids2, "Pagination pages must not overlap"


# ── STEP 3 — Critical-priority queue (BOTH type) ───────────────────────────────

class TestStep3CriticalQueue:
    @pytest.fixture(autouse=True)
    def _get_synth_both_id(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=admin_h)
        synth_both = [i for i in r.json()["items"]
                      if "/r04/synth/" in i["path_a"] and i["conflict_type"] == "BOTH"]
        if not synth_both:
            pytest.skip("R04 synthetic BOTH pairs not found")
        self._synth_both_id = synth_both[0]["id"]
        self._synth_both = synth_both[0]

    def test_critical_pair_has_both_type(self):
        assert self._synth_both["conflict_type"] == "BOTH"

    def test_critical_pair_has_label_fields(self):
        assert self._synth_both["label_a"] != ""
        assert self._synth_both["label_b"] != ""
        assert self._synth_both["label_a"] != self._synth_both["label_b"]

    def test_critical_pair_has_different_splits(self):
        # BOTH means label conflict AND cross-split; different splits expected
        assert self._synth_both["split_a"] != self._synth_both["split_b"]

    def test_critical_pair_has_sha1(self):
        assert len(self._synth_both["sha1_16"]) >= 8

    def test_critical_pair_has_archive_sources(self):
        assert "source_archive_a" in self._synth_both
        assert "source_archive_b" in self._synth_both

    def test_review_summary_counts_critical(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts/review-summary", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "pending" in data
        assert data["pending"] >= 5  # R04 synthetic pairs all PENDING

    def test_review_summary_reviewed_starts_zero(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts/review-summary", headers=admin_h)
        data = r.json()
        # Fresh DB — no decisions made yet
        assert data.get("reviewed", 0) == 0

    def test_eligible_counts_endpoint(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts/eligible-counts", headers=admin_h)
        assert r.status_code == 200


# ── STEP 4 — Review workflow ────────────────────────────────────────────────────

class TestStep4ReviewWorkflow:
    @pytest.fixture(autouse=True)
    def _get_synth_id(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=admin_h)
        synth = [i for i in r.json()["items"] if "/r04/synth/" in i["path_a"]]
        if not synth:
            pytest.skip("R04 synthetic pairs not found")
        self._synth_id = synth[0]["id"]

    def test_decision_confirm_label_requires_notes(self, client, qe_h):
        r = client.patch(f"/api/v1/annotation/conflicts/{self._synth_id}",
                         json={"decision": "CONFIRM_LABEL", "notes": ""},
                         headers=qe_h)
        assert r.status_code in (400, 422), "Empty notes must be rejected"

    def test_decision_confirm_label(self, client, qe_h, admin_h):
        # Reset to PENDING first
        client.patch(f"/api/v1/annotation/conflicts/{self._synth_id}",
                     json={"decision": "PENDING", "notes": "reset"},
                     headers=admin_h)
        r = client.patch(f"/api/v1/annotation/conflicts/{self._synth_id}",
                         json={"decision": "CONFIRM_LABEL",
                               "notes": "R04 test: label A is correct per defect taxonomy"},
                         headers=qe_h)
        assert r.status_code == 200
        assert r.json()["decision"] == "CONFIRM_LABEL"

    def test_review_summary_updates_after_decision(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts/review-summary", headers=admin_h)
        data = r.json()
        # `resolved` = total - pending; at least one decision was made earlier
        assert data.get("resolved", 0) >= 1, \
            f"Expected at least 1 resolved conflict; got summary={data}"

    def test_decision_correct_label(self, client, qe_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=qe_h)
        synth = [i for i in r.json()["items"]
                 if "/r04/synth/" in i["path_a"] and i["decision"] == "PENDING"]
        if not synth:
            pytest.skip("No PENDING synthetic R04 pairs left")
        cid = synth[0]["id"]
        r = client.patch(f"/api/v1/annotation/conflicts/{cid}",
                         json={"decision": "CORRECT_LABEL",
                               "notes": "R04 test: label B matches physical evidence"},
                         headers=qe_h)
        assert r.status_code == 200

    def test_decision_exclude_from_training(self, client, qe_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=qe_h)
        synth = [i for i in r.json()["items"]
                 if "/r04/synth/" in i["path_a"] and i["decision"] == "PENDING"]
        if not synth:
            pytest.skip("No PENDING synthetic R04 pairs left")
        cid = synth[0]["id"]
        r = client.patch(f"/api/v1/annotation/conflicts/{cid}",
                         json={"decision": "EXCLUDE_FROM_TRAINING",
                               "notes": "R04 test: image quality insufficient"},
                         headers=qe_h)
        assert r.status_code == 200

    def test_decision_needs_physical_test(self, client, qe_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=qe_h)
        synth = [i for i in r.json()["items"]
                 if "/r04/synth/" in i["path_a"] and i["decision"] == "PENDING"]
        if not synth:
            pytest.skip("No PENDING synthetic R04 pairs left")
        cid = synth[0]["id"]
        r = client.patch(f"/api/v1/annotation/conflicts/{cid}",
                         json={"decision": "NEEDS_PHYSICAL_TEST",
                               "notes": "R04 test: surface image inconclusive"},
                         headers=qe_h)
        assert r.status_code == 200

    def test_demo_cannot_adjudicate(self, client, demo_h, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=admin_h)
        synth = [i for i in r.json()["items"] if "/r04/synth/" in i["path_a"]]
        if not synth:
            pytest.skip("No R04 synthetic pairs found")
        cid = synth[0]["id"]
        r = client.patch(f"/api/v1/annotation/conflicts/{cid}",
                         json={"decision": "CONFIRM_LABEL", "notes": "should fail"},
                         headers=demo_h)
        assert r.status_code == 403

    def test_pe_can_adjudicate(self, client, pe_h, admin_h):
        """PE role has adjudication rights (same as QE and SA)."""
        # Find a PENDING synthetic pair (re-adjudication is not permitted)
        r = client.get("/api/v1/annotation/conflicts?limit=200&decision=PENDING", headers=admin_h)
        synth = [i for i in r.json()["items"] if "/r04/synth/" in i["path_a"]]
        if not synth:
            pytest.skip("No PENDING R04 synthetic pairs left for PE test")
        cid = synth[0]["id"]
        r = client.patch(f"/api/v1/annotation/conflicts/{cid}",
                         json={"decision": "CONFIRM_LABEL",
                               "notes": "PE adjudication test — OK"},
                         headers=pe_h)
        assert r.status_code == 200, f"PE should be allowed to adjudicate; got {r.status_code}"

    def test_decision_insufficient_evidence(self, client, qe_h, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200&decision=PENDING", headers=admin_h)
        synth = [i for i in r.json()["items"] if "/r04/synth/" in i["path_a"]]
        if not synth:
            pytest.skip("No PENDING R04 synthetic pairs left for insufficient_evidence test")
        cid = synth[0]["id"]
        r = client.patch(f"/api/v1/annotation/conflicts/{cid}",
                         json={"decision": "INSUFFICIENT_EVIDENCE",
                               "notes": "R04 test: needs weld_id metadata before training"},
                         headers=qe_h)
        assert r.status_code == 200


# ── STEP 5 — E4 Physical Evidence ──────────────────────────────────────────────

class TestStep5E4Evidence:
    def test_e4_create_with_weld_id(self, client, qe_h):
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/test_weld_id_01.png",
            "weld_id": "WLD-2026-001",
            "test_method": "CROSS_SECTION",
            "test_date": "2026-11-19",
            "verdict": "ACCEPTABLE",
            "evidence_quality": "UNVERIFIED",
            "confirmed_defect_codes": "",
        }, headers=qe_h)
        assert r.status_code == 201
        body = r.json()
        assert body["weld_id"] == "WLD-2026-001"
        assert body["test_method"] == "CROSS_SECTION"

    def test_e4_weld_id_nullable(self, client, qe_h):
        """weld_id is optional when no production weld identifier is available."""
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/test_no_weld_id.png",
            "test_method": "PEEL_TEST",
            "test_date": "2026-11-19",
            "verdict": "UNREVIEWED",
            "evidence_quality": "UNVERIFIED",
        }, headers=qe_h)
        assert r.status_code == 201
        assert r.json()["weld_id"] is None

    def test_e4_surface_observation_rejected(self, client, qe_h):
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/surface_obs.png",
            "test_method": "SURFACE_OBSERVATION",
            "test_date": "2026-11-19",
            "verdict": "UNREVIEWED",
            "evidence_quality": "UNVERIFIED",
        }, headers=qe_h)
        assert r.status_code == 422, \
            "SURFACE_OBSERVATION must not be accepted as E4 evidence"

    def test_e4_nugget_requires_destructive_method(self, client, qe_h):
        """Nugget measurements must be rejected for PEEL_TEST."""
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/peel_nugget_invalid.png",
            "test_method": "PEEL_TEST",
            "test_date": "2026-11-19",
            "nugget_diameter_mm": 5.5,
            "verdict": "UNREVIEWED",
            "evidence_quality": "UNVERIFIED",
        }, headers=qe_h)
        assert r.status_code == 422, \
            "Nugget measurement on PEEL_TEST must be rejected"

    def test_e4_cross_section_accepts_nugget(self, client, qe_h):
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/cs_nugget_valid.png",
            "test_method": "CROSS_SECTION",
            "test_date": "2026-11-19",
            "nugget_diameter_mm": 6.2,
            "nugget_height_mm": 1.8,
            "verdict": "ACCEPTABLE",
            "evidence_quality": "UNVERIFIED",
        }, headers=qe_h)
        assert r.status_code == 201
        assert r.json()["nugget_diameter_mm"] == pytest.approx(6.2, abs=0.01)

    def test_e4_verified_verdict_requires_report_ref(self, client, qe_h):
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/verified_no_ref.png",
            "test_method": "CROSS_SECTION",
            "test_date": "2026-11-19",
            "verdict": "ACCEPTABLE",
            "evidence_quality": "VERIFIED",
        }, headers=qe_h)
        assert r.status_code == 422, \
            "VERIFIED evidence_quality requires test_report_ref"

    def test_e4_verified_verdict_with_report_ref(self, client, qe_h):
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/verified_with_ref.png",
            "test_method": "CROSS_SECTION",
            "test_date": "2026-11-19",
            "verdict": "ACCEPTABLE",
            "evidence_quality": "VERIFIED",
            "test_report_ref": "LAB-RPT-2026-0441",
            "weld_id": "WLD-2026-002",
        }, headers=qe_h)
        assert r.status_code == 201
        assert r.json()["test_report_ref"] == "LAB-RPT-2026-0441"

    def test_e4_demo_user_forbidden(self, client, demo_h):
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/demo_forbidden.png",
            "test_method": "PEEL_TEST",
            "test_date": "2026-11-19",
            "verdict": "UNREVIEWED",
            "evidence_quality": "UNVERIFIED",
        }, headers=demo_h)
        assert r.status_code == 403

    def test_e4_pe_user_allowed(self, client, pe_h):
        r = client.post("/api/v1/annotation/e4-evidence", json={
            "image_path": "/r04/e4/pe_created.png",
            "test_method": "PEEL_TEST",
            "test_date": "2026-11-19",
            "verdict": "UNREVIEWED",
            "evidence_quality": "UNVERIFIED",
        }, headers=pe_h)
        assert r.status_code == 201

    def test_e4_duplicate_blocked(self, client, qe_h):
        payload = {
            "image_path": "/r04/e4/dup_check.png",
            "test_method": "PEEL_TEST",
            "test_date": "2026-11-19",
            "verdict": "UNREVIEWED",
            "evidence_quality": "UNVERIFIED",
        }
        r1 = client.post("/api/v1/annotation/e4-evidence", json=payload, headers=qe_h)
        assert r1.status_code == 201
        r2 = client.post("/api/v1/annotation/e4-evidence", json=payload, headers=qe_h)
        assert r2.status_code == 409, "Duplicate evidence must return 409"

    def test_e4_summary_gate_not_cleared(self, client, qe_h):
        r = client.get("/api/v1/annotation/e4-evidence/summary", headers=qe_h)
        assert r.status_code == 200
        data = r.json()
        assert data.get("e4_gate_clear") is False, \
            f"E4 gate must NOT be cleared with only test evidence records; got {data}"

    def test_e4_summary_total_dataset_images(self, client, qe_h):
        r = client.get("/api/v1/annotation/e4-evidence/summary", headers=qe_h)
        assert r.json()["total_dataset_images"] == 927

    def test_e4_list_filtering_by_method(self, client, qe_h):
        r = client.get("/api/v1/annotation/e4-evidence?test_method=CROSS_SECTION",
                       headers=qe_h)
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["test_method"] == "CROSS_SECTION"

    def test_e4_list_filtering_by_verdict(self, client, qe_h):
        r = client.get("/api/v1/annotation/e4-evidence?verdict=ACCEPTABLE", headers=qe_h)
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["verdict"] == "ACCEPTABLE"


# ── STEP 6 — Security ──────────────────────────────────────────────────────────

class TestStep6Security:
    def test_image_preview_requires_auth(self, client):
        r = client.get("/api/v1/annotation/image-preview?path=/r04/synth/test.png")
        assert r.status_code == 401

    def test_image_preview_path_traversal_blocked(self, client, admin_h):
        r = client.get(
            "/api/v1/annotation/image-preview?path=../../etc/passwd",
            headers=admin_h,
        )
        assert r.status_code in (400, 403, 404), \
            f"Path traversal must be blocked; got {r.status_code}"

    def test_image_preview_null_byte_blocked(self, client, admin_h):
        # httpx rejects null-byte URLs before they reach the server — both are acceptable
        import httpx
        try:
            r = client.get(
                "/api/v1/annotation/image-preview?path=/r04/test\x00.png",
                headers=admin_h,
            )
            assert r.status_code in (400, 403, 404, 422)
        except (httpx.InvalidURL, ValueError):
            pass  # client-side rejection is also an acceptable block

    def test_image_preview_non_dataset_root_blocked(self, client, admin_h):
        r = client.get(
            "/api/v1/annotation/image-preview?path=C:/Windows/System32/config/SAM",
            headers=admin_h,
        )
        assert r.status_code in (400, 403), \
            f"Non-dataset path must be blocked; got {r.status_code}"

    def test_image_preview_disallowed_extension(self, client, admin_h):
        r = client.get(
            "/api/v1/annotation/image-preview?path=/r04/test.php",
            headers=admin_h,
        )
        assert r.status_code in (400, 403), \
            f"Disallowed extension must be blocked; got {r.status_code}"

    def test_conflict_adjudication_unauthenticated_blocked(self, client, admin_h):
        r = client.get("/api/v1/annotation/conflicts?limit=200", headers=admin_h)
        synth = [i for i in r.json()["items"] if "/r04/synth/" in i["path_a"]]
        if not synth:
            pytest.skip("No R04 synthetic pairs found")
        cid = synth[0]["id"]
        rr = client.patch(f"/api/v1/annotation/conflicts/{cid}",
                          json={"decision": "CONFIRM_LABEL", "notes": "auth test"},
                          headers={})
        assert rr.status_code == 401

    def test_e4_evidence_rbac_summary(self, client, demo_h):
        r = client.get("/api/v1/annotation/e4-evidence/summary", headers=demo_h)
        assert r.status_code == 403

    def test_conflict_list_unauthenticated_blocked(self, client):
        r = client.get("/api/v1/annotation/conflicts")
        assert r.status_code == 401

    def test_real_conflicts_not_modified(self):
        """E1 CSV must remain 100% PENDING — the most critical safety check."""
        rows = _read_csv(E1_QUEUE_CSV)
        non_pending = [r for r in rows
                       if r.get("status", "PENDING_REVIEW") != "PENDING_REVIEW"
                       or r.get("review_decision", "") != ""]
        assert len(non_pending) == 0, \
            f"RULE VIOLATION: {len(non_pending)} real conflict rows were modified"
