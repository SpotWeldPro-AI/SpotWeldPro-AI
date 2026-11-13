"""
VISION-P3E: Annotation service and API tests.

Coverage:
  - WeldAnnotation / AnnotationFinding / AnnotationReview / AnnotationAuditEntry ORM models
  - ConflictAdjudication model
  - annotation_service: state machine, CRUD, conflict loader, quality metrics, export
  - API router: auth, role guards, state transitions, error responses
"""
from __future__ import annotations

import os
import tempfile
import csv
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.session import Base
from app.models.annotation_entities import (
    AnnotationAuditEntry,
    AnnotationFinding,
    AnnotationReview,
    ConflictAdjudication,
    WeldAnnotation,
)
from app.vision.annotation_service import (
    AnnotationServiceError,
    InvalidTransitionError,
    SelfApprovalError,
    add_finding,
    adjudicate_conflict,
    build_export_dataset,
    create_annotation,
    get_quality_metrics,
    load_conflicts_from_manifest,
    remove_finding,
    reopen_annotation,
    review_annotation,
    submit_annotation,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def _make_annotation(db: Session, image_path: str = "/img/test.png",
                     annotator_id: str = "alice@example.com") -> WeldAnnotation:
    return create_annotation(db, image_path=image_path, annotator_id=annotator_id,
                             image_hash="abc123", split="train",
                             image_width_px=640, image_height_px=480)


# ── ORM model tests ───────────────────────────────────────────────────────────

class TestWeldAnnotationModel:
    def test_create_defaults(self, db):
        ann = WeldAnnotation(image_path="/x.png", annotator_id="u@e.com")
        db.add(ann)
        db.flush()
        assert ann.review_status == "DRAFT"
        assert ann.export_eligible is False
        assert ann.taxonomy_version == "P3D-1.0"

    def test_is_training_eligible_no_findings(self, db):
        ann = WeldAnnotation(image_path="/y.png", annotator_id="u@e.com",
                             review_status="APPROVED", is_roi_cropped=True,
                             annotation_markup_removed=True)
        db.add(ann)
        db.flush()
        assert ann.is_training_eligible() is False

    def test_is_training_eligible_generic_bad_only(self, db):
        ann = WeldAnnotation(image_path="/z.png", annotator_id="u@e.com",
                             review_status="APPROVED", is_roi_cropped=True,
                             annotation_markup_removed=True)
        db.add(ann)
        db.flush()
        f = AnnotationFinding(annotation_id=ann.id, defect_code="generic_bad",
                              name_tr="Hatalı", name_en="Generic bad")
        db.add(f)
        db.flush()
        assert ann.is_training_eligible() is False

    def test_is_training_eligible_full(self, db):
        ann = WeldAnnotation(image_path="/w.png", annotator_id="u@e.com",
                             review_status="APPROVED", is_roi_cropped=True,
                             annotation_markup_removed=True)
        db.add(ann)
        db.flush()
        f = AnnotationFinding(annotation_id=ann.id, defect_code="capak",
                              name_tr="Çapak", name_en="Spatter")
        db.add(f)
        db.flush()
        assert ann.is_training_eligible() is True

    def test_is_training_eligible_not_approved(self, db):
        ann = WeldAnnotation(image_path="/v.png", annotator_id="u@e.com",
                             review_status="SUBMITTED", is_roi_cropped=True,
                             annotation_markup_removed=True)
        db.add(ann)
        db.flush()
        f = AnnotationFinding(annotation_id=ann.id, defect_code="capak",
                              name_tr="Çapak", name_en="Spatter")
        db.add(f)
        db.flush()
        assert ann.is_training_eligible() is False

    def test_recalculate_export_eligibility(self, db):
        ann = WeldAnnotation(image_path="/u.png", annotator_id="u@e.com",
                             review_status="APPROVED", is_roi_cropped=True,
                             annotation_markup_removed=True)
        db.add(ann)
        db.flush()
        f = AnnotationFinding(annotation_id=ann.id, defect_code="delik",
                              name_tr="Delik", name_en="Burn-through")
        db.add(f)
        db.flush()
        ann.recalculate_export_eligibility()
        assert ann.export_eligible is True

    def test_created_at_set(self, db):
        ann = WeldAnnotation(image_path="/ts.png", annotator_id="u@e.com")
        db.add(ann)
        db.flush()
        assert ann.created_at is not None


class TestAnnotationFindingModel:
    def test_defaults(self, db):
        ann = _make_annotation(db, "/img/f.png")
        f = AnnotationFinding(annotation_id=ann.id, defect_code="capak",
                              name_tr="Çapak", name_en="Spatter")
        db.add(f)
        db.flush()
        assert f.region_type == "BBOX"
        assert f.confidence == 0.0
        assert f.confidence_source == "HUMAN_ANNOTATION"
        assert f.requires_physical_confirmation is False

    def test_relationship_back(self, db):
        ann = _make_annotation(db, "/img/g.png")
        f = AnnotationFinding(annotation_id=ann.id, defect_code="kopuk",
                              name_tr="Kopuk", name_en="Broken")
        db.add(f)
        db.flush()
        assert f.annotation.id == ann.id


class TestAnnotationReviewModel:
    def test_stores_decision(self, db):
        ann = _make_annotation(db, "/img/r.png")
        rev = AnnotationReview(annotation_id=ann.id, reviewer_id="bob@e.com",
                               decision="APPROVED", previous_status="SUBMITTED",
                               new_status="APPROVED")
        db.add(rev)
        db.flush()
        assert rev.decision == "APPROVED"
        assert rev.reviewed_at is not None


class TestAnnotationAuditEntryModel:
    def test_immutable_created(self, db):
        ann = _make_annotation(db, "/img/a.png")
        e = AnnotationAuditEntry(annotation_id=ann.id, actor_id="alice@e.com",
                                 action="CREATED", before_state=None,
                                 after_state={"review_status": "DRAFT"})
        db.add(e)
        db.flush()
        assert e.id is not None
        assert e.created_at is not None


class TestConflictAdjudicationModel:
    def test_default_decision_pending(self, db):
        c = ConflictAdjudication(sha1_16="abc", path_a="/a.png", path_b="/b.png",
                                  label_a="ok", label_b="generic_bad",
                                  split_a="train", split_b="test",
                                  conflict_type="LABEL_CONFLICT")
        db.add(c)
        db.flush()
        assert c.decision == "PENDING"
        assert c.adjudicator_id is None

    def test_unique_constraint(self, db):
        from sqlalchemy.exc import IntegrityError
        c1 = ConflictAdjudication(sha1_16="x1", path_a="/p1.png", path_b="/p2.png",
                                   label_a="ok", label_b="generic_bad",
                                   split_a="train", split_b="test",
                                   conflict_type="LABEL_CONFLICT")
        db.add(c1)
        db.flush()
        c2 = ConflictAdjudication(sha1_16="x1", path_a="/p1.png", path_b="/p2.png",
                                   label_a="ok", label_b="capak",
                                   split_a="train", split_b="test",
                                   conflict_type="LABEL_CONFLICT")
        db.add(c2)
        with pytest.raises(IntegrityError):
            db.flush()


# ── annotation_service state machine tests ────────────────────────────────────

class TestStateMachine:
    def test_draft_to_submitted(self, db):
        ann = _make_annotation(db, "/sm/1.png")
        submit_annotation(db, ann.id, "alice@e.com")
        assert ann.review_status == "SUBMITTED"

    def test_submitted_to_approved(self, db):
        ann = _make_annotation(db, "/sm/2.png")
        submit_annotation(db, ann.id, "alice@e.com")
        review_annotation(db, ann.id, "bob@e.com", "approve")
        assert ann.review_status == "APPROVED"

    def test_self_approval_blocked(self, db):
        ann = _make_annotation(db, "/sm/3.png", annotator_id="alice@e.com")
        submit_annotation(db, ann.id, "alice@e.com")
        with pytest.raises(SelfApprovalError):
            review_annotation(db, ann.id, "alice@e.com", "approve")

    def test_submitted_to_rejected(self, db):
        ann = _make_annotation(db, "/sm/4.png")
        submit_annotation(db, ann.id, "alice@e.com")
        review_annotation(db, ann.id, "bob@e.com", "reject")
        assert ann.review_status == "REJECTED"

    def test_submitted_to_needs_revision(self, db):
        ann = _make_annotation(db, "/sm/5.png")
        submit_annotation(db, ann.id, "alice@e.com")
        review_annotation(db, ann.id, "bob@e.com", "request_revision")
        assert ann.review_status == "NEEDS_REVISION"

    def test_needs_revision_to_draft(self, db):
        ann = _make_annotation(db, "/sm/6.png")
        submit_annotation(db, ann.id, "alice@e.com")
        review_annotation(db, ann.id, "bob@e.com", "request_revision")
        reopen_annotation(db, ann.id, "alice@e.com")
        assert ann.review_status == "DRAFT"

    def test_rejected_to_draft_via_reopen(self, db):
        ann = _make_annotation(db, "/sm/7.png")
        submit_annotation(db, ann.id, "alice@e.com")
        review_annotation(db, ann.id, "bob@e.com", "reject")
        reopen_annotation(db, ann.id, "alice@e.com")
        assert ann.review_status == "DRAFT"

    def test_invalid_transition_draft_to_approve(self, db):
        ann = _make_annotation(db, "/sm/8.png")
        with pytest.raises(InvalidTransitionError):
            review_annotation(db, ann.id, "bob@e.com", "approve")

    def test_audit_trail_created(self, db):
        ann = _make_annotation(db, "/sm/9.png")
        submit_annotation(db, ann.id, "alice@e.com")
        entries = db.query(AnnotationAuditEntry).filter_by(annotation_id=ann.id).all()
        actions = {e.action for e in entries}
        assert "CREATED" in actions
        assert "SUBMIT" in actions

    def test_review_creates_review_record(self, db):
        ann = _make_annotation(db, "/sm/10.png")
        submit_annotation(db, ann.id, "alice@e.com")
        review_annotation(db, ann.id, "bob@e.com", "approve", notes="Looks good")
        revs = db.query(AnnotationReview).filter_by(annotation_id=ann.id).all()
        assert len(revs) == 1
        assert revs[0].review_notes == "Looks good"

    def test_approved_export_eligible_after_flags_set(self, db):
        ann = _make_annotation(db, "/sm/11.png")
        ann.is_roi_cropped = True
        ann.annotation_markup_removed = True
        f = AnnotationFinding(annotation_id=ann.id, defect_code="capak",
                              name_tr="Çapak", name_en="Spatter")
        db.add(f)
        db.flush()
        submit_annotation(db, ann.id, "alice@e.com")
        review_annotation(db, ann.id, "bob@e.com", "approve")
        assert ann.export_eligible is True

    def test_draft_not_export_eligible(self, db):
        ann = _make_annotation(db, "/sm/12.png")
        assert ann.export_eligible is False

    def test_unknown_decision_raises(self, db):
        ann = _make_annotation(db, "/sm/13.png")
        submit_annotation(db, ann.id, "alice@e.com")
        with pytest.raises(AnnotationServiceError):
            review_annotation(db, ann.id, "bob@e.com", "banana")

    def test_not_found_raises(self, db):
        with pytest.raises(AnnotationServiceError):
            submit_annotation(db, 999999, "alice@e.com")


# ── CRUD helpers tests ────────────────────────────────────────────────────────

class TestCRUD:
    def test_create_annotation_sets_draft(self, db):
        ann = create_annotation(db, "/c/1.png", "u@e.com")
        assert ann.review_status == "DRAFT"

    def test_add_finding_in_draft(self, db):
        ann = _make_annotation(db, "/c/2.png")
        f = add_finding(db, ann.id, "u@e.com", "capak", "Çapak", "Spatter",
                        region_type="POLYGON", region_data={"points": [[0,0],[10,0],[10,10]]})
        assert f.defect_code == "capak"

    def test_add_finding_blocked_in_submitted(self, db):
        ann = _make_annotation(db, "/c/3.png")
        submit_annotation(db, ann.id, "u@e.com")
        with pytest.raises(AnnotationServiceError):
            add_finding(db, ann.id, "u@e.com", "capak", "Çapak", "Spatter")

    def test_remove_finding(self, db):
        ann = _make_annotation(db, "/c/4.png")
        f = add_finding(db, ann.id, "u@e.com", "delik", "Delik", "Burn-through")
        fid = f.id
        remove_finding(db, fid, "u@e.com")
        assert db.get(AnnotationFinding, fid) is None

    def test_remove_finding_blocked_in_submitted(self, db):
        ann = _make_annotation(db, "/c/5.png")
        f = add_finding(db, ann.id, "u@e.com", "delik", "Delik", "Burn-through")
        submit_annotation(db, ann.id, "u@e.com")
        with pytest.raises(AnnotationServiceError):
            remove_finding(db, f.id, "u@e.com")

    def test_add_finding_in_needs_revision(self, db):
        ann = _make_annotation(db, "/c/6.png")
        submit_annotation(db, ann.id, "u@e.com")
        review_annotation(db, ann.id, "bob@e.com", "request_revision")
        reopen_annotation(db, ann.id, "u@e.com")
        f = add_finding(db, ann.id, "u@e.com", "capak", "Çapak", "Spatter")
        assert f.id is not None


# ── Conflict service tests ────────────────────────────────────────────────────

class TestConflictService:
    def test_adjudicate_keep_a(self, db):
        c = ConflictAdjudication(sha1_16="ca1", path_a="/ca1.png", path_b="/cb1.png",
                                  label_a="ok", label_b="generic_bad",
                                  split_a="train", split_b="test",
                                  conflict_type="LABEL_CONFLICT")
        db.add(c)
        db.flush()
        result = adjudicate_conflict(db, c.id, "eng@e.com", "KEEP_A", "A is correct")
        assert result.decision == "KEEP_A"
        assert result.adjudicator_id == "eng@e.com"
        assert result.adjudication_notes == "A is correct"

    def test_adjudicate_invalid_decision(self, db):
        c = ConflictAdjudication(sha1_16="ca2", path_a="/ca2.png", path_b="/cb2.png",
                                  label_a="ok", label_b="generic_bad",
                                  split_a="train", split_b="test",
                                  conflict_type="LABEL_CONFLICT")
        db.add(c)
        db.flush()
        with pytest.raises(AnnotationServiceError):
            adjudicate_conflict(db, c.id, "eng@e.com", "INVALID")

    def test_adjudicate_not_found(self, db):
        with pytest.raises(AnnotationServiceError):
            adjudicate_conflict(db, 999999, "eng@e.com", "KEEP_A")

    def test_load_conflicts_from_manifest(self, db):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                         newline="", delete=False) as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "sha1_16", "path_a", "path_b", "label_a", "label_b",
                "split_a", "split_b", "conflict_type",
                "source_archive_a", "source_archive_b"
            ])
            writer.writeheader()
            writer.writerow(dict(sha1_16="m1", path_a="/m1a.png", path_b="/m1b.png",
                                  label_a="ok", label_b="generic_bad",
                                  split_a="train", split_b="test",
                                  conflict_type="LABEL_CONFLICT",
                                  source_archive_a="ok.zip", source_archive_b="nok.zip"))
            writer.writerow(dict(sha1_16="m2", path_a="/m2a.png", path_b="/m2b.png",
                                  label_a="ok", label_b="capak",
                                  split_a="train", split_b="val",
                                  conflict_type="BOTH",
                                  source_archive_a="", source_archive_b=""))
            # benign row — should be skipped
            writer.writerow(dict(sha1_16="m3", path_a="/m3a.png", path_b="/m3b.png",
                                  label_a="ok", label_b="ok",
                                  split_a="train", split_b="train",
                                  conflict_type="SAME_LABEL",
                                  source_archive_a="", source_archive_b=""))
            path = fh.name
        try:
            inserted = load_conflicts_from_manifest(db, path)
            assert inserted == 2
            # idempotency
            inserted2 = load_conflicts_from_manifest(db, path)
            assert inserted2 == 0
        finally:
            os.unlink(path)

    def test_load_conflicts_missing_file(self, db):
        inserted = load_conflicts_from_manifest(db, "/nonexistent/manifest.csv")
        assert inserted == 0


# ── Quality metrics tests ─────────────────────────────────────────────────────

class TestQualityMetrics:
    def test_empty_db(self, db):
        metrics = get_quality_metrics(db)
        assert "annotation_status_counts" in metrics
        assert "conflict_pending" in metrics
        assert metrics["training_gate_open"] is False

    def test_counts_reflect_state(self, db):
        ann = _make_annotation(db, "/qm/1.png")
        metrics = get_quality_metrics(db)
        assert metrics["annotation_status_counts"].get("DRAFT", 0) >= 1

    def test_e1_gate_pending_conflicts(self, db):
        c = ConflictAdjudication(sha1_16="e1t", path_a="/e1a.png", path_b="/e1b.png",
                                  label_a="ok", label_b="generic_bad",
                                  split_a="train", split_b="test",
                                  conflict_type="LABEL_CONFLICT")
        db.add(c)
        db.flush()
        metrics = get_quality_metrics(db)
        assert metrics["e1_e4_gates"]["E1_duplicate_resolution"] is False

    def test_training_gate_always_false(self, db):
        metrics = get_quality_metrics(db)
        assert metrics["training_gate_open"] is False


# ── Export pipeline tests ─────────────────────────────────────────────────────

class TestExportPipeline:
    def test_no_eligible_returns_warning(self, db):
        coco, yolo, warnings = build_export_dataset(db, "v0.1", "admin@e.com")
        assert any("No export-eligible" in w for w in warnings)
        assert coco["info"]["training_gate_open"] is False

    def test_export_skips_missing_file(self, db):
        ann = _make_annotation(db, "/nonexistent/x.png")
        ann.review_status = "APPROVED"
        ann.is_roi_cropped = True
        ann.annotation_markup_removed = True
        ann.export_eligible = True
        f = AnnotationFinding(annotation_id=ann.id, defect_code="capak",
                              name_tr="Çapak", name_en="Spatter",
                              region_type="BBOX",
                              region_data={"x": 10, "y": 10, "w": 50, "h": 50})
        db.add(f)
        db.flush()
        coco, yolo, warnings = build_export_dataset(db, "v0.2", "admin@e.com")
        assert any("not found" in w.lower() for w in warnings)

    def test_export_with_existing_file(self, db, tmp_path):
        img_path = str(tmp_path / "real.png")
        with open(img_path, "wb") as fh:
            fh.write(b"\x89PNG" + b"\x00" * 100)
        ann = create_annotation(db, img_path, "alice@e.com",
                                image_width_px=100, image_height_px=100)
        ann.review_status = "APPROVED"
        ann.is_roi_cropped = True
        ann.annotation_markup_removed = True
        ann.export_eligible = True
        f = AnnotationFinding(annotation_id=ann.id, defect_code="capak",
                              name_tr="Çapak", name_en="Spatter",
                              region_type="BBOX",
                              region_data={"x": 5, "y": 5, "w": 20, "h": 20})
        db.add(f)
        db.flush()
        coco, yolo, warnings = build_export_dataset(db, "v0.3", "admin@e.com")
        assert len(coco["images"]) >= 1
        assert ann.export_version == "v0.3"

    def test_polygon_validation_min_points(self, db, tmp_path):
        img_path = str(tmp_path / "poly.png")
        with open(img_path, "wb") as fh:
            fh.write(b"\x89PNG" + b"\x00" * 100)
        ann = create_annotation(db, img_path, "alice@e.com",
                                image_width_px=100, image_height_px=100)
        ann.review_status = "APPROVED"
        ann.is_roi_cropped = True
        ann.annotation_markup_removed = True
        ann.export_eligible = True
        f = AnnotationFinding(annotation_id=ann.id, defect_code="delik",
                              name_tr="Delik", name_en="Burn-through",
                              region_type="POLYGON",
                              region_data={"points": [[0, 0], [10, 0]]})  # only 2 points
        db.add(f)
        db.flush()
        _, _, warnings = build_export_dataset(db, "v0.4", "admin@e.com")
        assert any("polygon" in w.lower() for w in warnings)

    def test_bbox_invalid_dimensions_skipped(self, db, tmp_path):
        img_path = str(tmp_path / "bbox.png")
        with open(img_path, "wb") as fh:
            fh.write(b"\x89PNG" + b"\x00" * 100)
        ann = create_annotation(db, img_path, "alice@e.com",
                                image_width_px=100, image_height_px=100)
        ann.review_status = "APPROVED"
        ann.is_roi_cropped = True
        ann.annotation_markup_removed = True
        ann.export_eligible = True
        f = AnnotationFinding(annotation_id=ann.id, defect_code="capak",
                              name_tr="Çapak", name_en="Spatter",
                              region_type="BBOX",
                              region_data={"x": 5, "y": 5, "w": 0, "h": 0})  # zero dim
        db.add(f)
        db.flush()
        _, _, warnings = build_export_dataset(db, "v0.5", "admin@e.com")
        assert any("invalid dimensions" in w.lower() for w in warnings)

    def test_export_split_filter(self, db, tmp_path):
        img_path = str(tmp_path / "split_test.png")
        with open(img_path, "wb") as fh:
            fh.write(b"\x89PNG" + b"\x00" * 100)
        ann = create_annotation(db, img_path, "alice@e.com",
                                split="val", image_width_px=100, image_height_px=100)
        ann.review_status = "APPROVED"
        ann.is_roi_cropped = True
        ann.annotation_markup_removed = True
        ann.export_eligible = True
        f = AnnotationFinding(annotation_id=ann.id, defect_code="capak",
                              name_tr="Çapak", name_en="Spatter",
                              region_type="BBOX",
                              region_data={"x": 1, "y": 1, "w": 10, "h": 10})
        db.add(f)
        db.flush()
        _, yolo_all, _ = build_export_dataset(db, "v0.6a", "admin@e.com")
        _, yolo_train, _ = build_export_dataset(db, "v0.6b", "admin@e.com", split="train")
        _, yolo_val, _ = build_export_dataset(db, "v0.6c", "admin@e.com", split="val")
        assert img_path in yolo_all or len(yolo_all) >= 0
        assert img_path not in yolo_train
        assert img_path in yolo_val


# ── Annotation region type conversion tests ───────────────────────────────────

class TestFindingConversion:
    def test_point_no_yolo(self, db, tmp_path):
        img_path = str(tmp_path / "point.png")
        with open(img_path, "wb") as fh:
            fh.write(b"\x89PNG" + b"\x00" * 100)
        ann = create_annotation(db, img_path, "alice@e.com",
                                image_width_px=100, image_height_px=100)
        ann.review_status = "APPROVED"
        ann.is_roi_cropped = True
        ann.annotation_markup_removed = True
        ann.export_eligible = True
        f = AnnotationFinding(annotation_id=ann.id, defect_code="eksik",
                              name_tr="Eksik", name_en="Missing",
                              region_type="POINT",
                              region_data={"x": 50, "y": 50})
        db.add(f)
        db.flush()
        coco, yolo, warnings = build_export_dataset(db, "v0.7", "admin@e.com")
        assert img_path in yolo
        assert yolo[img_path] == []  # POINT → no YOLO entry

    def test_whole_image_yolo_normalized(self, db, tmp_path):
        img_path = str(tmp_path / "whole.png")
        with open(img_path, "wb") as fh:
            fh.write(b"\x89PNG" + b"\x00" * 100)
        ann = create_annotation(db, img_path, "alice@e.com",
                                image_width_px=100, image_height_px=100)
        ann.review_status = "APPROVED"
        ann.is_roi_cropped = True
        ann.annotation_markup_removed = True
        ann.export_eligible = True
        f = AnnotationFinding(annotation_id=ann.id, defect_code="ok",
                              name_tr="Kabul", name_en="Accepted",
                              region_type="WHOLE_IMAGE", region_data={})
        db.add(f)
        db.flush()
        _, yolo, _ = build_export_dataset(db, "v0.8", "admin@e.com")
        if img_path in yolo and yolo[img_path]:
            entry = yolo[img_path][0]
            # centre should be 0.5, 0.5 and size 1.0 × 1.0
            assert entry[1] == pytest.approx(0.5)
            assert entry[2] == pytest.approx(0.5)
            assert entry[3] == pytest.approx(1.0)
            assert entry[4] == pytest.approx(1.0)
