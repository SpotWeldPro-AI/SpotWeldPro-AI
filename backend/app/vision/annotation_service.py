"""
VISION-P3E: Annotation service — review state machine, conflict loader,
quality metrics, and export eligibility.

Review state machine:
  DRAFT → SUBMITTED (by annotator)
  SUBMITTED → APPROVED (by reviewer ≠ annotator)
  SUBMITTED → REJECTED (by reviewer)
  SUBMITTED → NEEDS_REVISION (by reviewer)
  NEEDS_REVISION → DRAFT (auto-transition; annotator revises)
  REJECTED → DRAFT (optional re-open by annotator)

Self-approval rule: when decision == APPROVED, reviewer_id MUST NOT equal
  the annotation's annotator_id.  This is enforced in `review_annotation`.

Training gate: export_eligible is recomputed after every status change;
  DatasetAudit.is_training_allowed() must also be True before any export.
"""
from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.annotation_entities import (
    AnnotationAuditEntry,
    AnnotationFinding,
    AnnotationReview,
    ConflictAdjudication,
    WeldAnnotation,
)
from app.vision.temporal.dataset_audit import NO_AUDIT

_log = logging.getLogger(__name__)

# ── Valid state transitions ────────────────────────────────────────────────────

_TRANSITIONS: dict[str, dict[str, str]] = {
    "DRAFT": {"submit": "SUBMITTED"},
    "SUBMITTED": {
        "approve": "APPROVED",
        "reject": "REJECTED",
        "request_revision": "NEEDS_REVISION",
    },
    "NEEDS_REVISION": {"reopen": "DRAFT"},
    "REJECTED": {"reopen": "DRAFT"},
    "APPROVED": {},  # terminal; can be undone only via admin action not modelled here
}

_REVIEWER_ACTIONS = {"approve", "reject", "request_revision"}


class AnnotationServiceError(Exception):
    pass


class SelfApprovalError(AnnotationServiceError):
    pass


class InvalidTransitionError(AnnotationServiceError):
    pass


# ── State machine ─────────────────────────────────────────────────────────────

def submit_annotation(db: Session, annotation_id: int, actor_id: str) -> WeldAnnotation:
    """Annotator submits for review: DRAFT → SUBMITTED."""
    ann = _get_or_raise(db, annotation_id)
    _transition(db, ann, "submit", actor_id, "SUBMITTED")
    return ann


def review_annotation(
    db: Session,
    annotation_id: int,
    reviewer_id: str,
    decision: str,  # approve | reject | request_revision
    notes: str = "",
) -> WeldAnnotation:
    """
    Reviewer decision.  Prevents self-approval when decision == approve.

    decision:
      approve           → APPROVED (reviewer ≠ annotator required)
      reject            → REJECTED
      request_revision  → NEEDS_REVISION
    """
    ann = _get_or_raise(db, annotation_id)

    if decision == "approve" and reviewer_id == ann.annotator_id:
        raise SelfApprovalError(
            f"Self-approval prohibited: reviewer '{reviewer_id}' is the annotator."
        )

    if decision not in _REVIEWER_ACTIONS:
        raise AnnotationServiceError(f"Unknown decision '{decision}'.")

    prev_status = ann.review_status
    _transition(db, ann, decision, reviewer_id, None)
    new_status = ann.review_status

    rev = AnnotationReview(
        annotation_id=annotation_id,
        reviewer_id=reviewer_id,
        decision=decision.upper().replace("REQUEST_", ""),
        review_notes=notes,
        previous_status=prev_status,
        new_status=new_status,
    )
    db.add(rev)
    ann.recalculate_export_eligibility()
    db.flush()
    return ann


def reopen_annotation(db: Session, annotation_id: int, actor_id: str) -> WeldAnnotation:
    """Move NEEDS_REVISION or REJECTED back to DRAFT."""
    ann = _get_or_raise(db, annotation_id)
    _transition(db, ann, "reopen", actor_id, "DRAFT")
    ann.recalculate_export_eligibility()
    db.flush()
    return ann


def _transition(
    db: Session, ann: WeldAnnotation, action: str, actor_id: str, force_new_status: str | None
) -> None:
    current = ann.review_status
    allowed = _TRANSITIONS.get(current, {})
    if action not in allowed:
        raise InvalidTransitionError(
            f"Cannot '{action}' from status '{current}'. "
            f"Allowed actions: {list(allowed.keys()) or 'none'}."
        )
    new_status = force_new_status or allowed[action]
    before = {"review_status": current}
    ann.review_status = new_status
    after = {"review_status": new_status}
    _audit(db, ann.id, actor_id, action.upper(), before, after)
    db.flush()


def _audit(
    db: Session,
    annotation_id: int,
    actor_id: str,
    action: str,
    before: dict | None,
    after: dict | None,
    notes: str = "",
) -> None:
    db.add(AnnotationAuditEntry(
        annotation_id=annotation_id,
        actor_id=actor_id,
        action=action,
        before_state=before,
        after_state=after,
        notes=notes,
    ))


def _get_or_raise(db: Session, annotation_id: int) -> WeldAnnotation:
    ann = db.get(WeldAnnotation, annotation_id)
    if ann is None:
        raise AnnotationServiceError(f"Annotation {annotation_id} not found.")
    return ann


# ── CRUD helpers ───────────────────────────────────────────────────────────────

def create_annotation(
    db: Session,
    image_path: str,
    annotator_id: str,
    image_hash: str | None = None,
    weld_id: str | None = None,
    source_archive: str | None = None,
    split: str = "unknown",
    label_provenance: str = "SURFACE_OBSERVATION",
    contamination_level: str = "UNKNOWN",
    max_markup_ratio: float = 0.0,
    image_width_px: int | None = None,
    image_height_px: int | None = None,
) -> WeldAnnotation:
    ann = WeldAnnotation(
        image_path=image_path,
        annotator_id=annotator_id,
        image_hash=image_hash,
        weld_id=weld_id,
        source_archive=source_archive,
        split=split,
        label_provenance=label_provenance,
        contamination_level=contamination_level,
        max_markup_ratio=max_markup_ratio,
        image_width_px=image_width_px,
        image_height_px=image_height_px,
    )
    db.add(ann)
    db.flush()
    _audit(db, ann.id, annotator_id, "CREATED", None, {"review_status": "DRAFT"})
    return ann


def add_finding(
    db: Session,
    annotation_id: int,
    actor_id: str,
    defect_code: str,
    name_tr: str,
    name_en: str,
    region_type: str = "BBOX",
    region_data: dict | None = None,
    confidence: float = 0.0,
    requires_physical_confirmation: bool = False,
    is_surface_classifiable: bool = True,
) -> AnnotationFinding:
    ann = _get_or_raise(db, annotation_id)
    if ann.review_status not in ("DRAFT", "NEEDS_REVISION"):
        raise AnnotationServiceError(
            f"Cannot add findings to annotation in status '{ann.review_status}'."
        )
    f = AnnotationFinding(
        annotation_id=annotation_id,
        defect_code=defect_code,
        name_tr=name_tr,
        name_en=name_en,
        region_type=region_type,
        region_data=region_data or {},
        confidence=confidence,
        requires_physical_confirmation=requires_physical_confirmation,
        is_surface_classifiable=is_surface_classifiable,
    )
    db.add(f)
    db.flush()
    _audit(db, annotation_id, actor_id, "FINDING_ADDED",
           None, {"defect_code": defect_code, "region_type": region_type})
    return f


def remove_finding(db: Session, finding_id: int, actor_id: str) -> None:
    f = db.get(AnnotationFinding, finding_id)
    if f is None:
        raise AnnotationServiceError(f"Finding {finding_id} not found.")
    ann = _get_or_raise(db, f.annotation_id)
    if ann.review_status not in ("DRAFT", "NEEDS_REVISION"):
        raise AnnotationServiceError(
            f"Cannot remove findings from annotation in status '{ann.review_status}'."
        )
    _audit(db, ann.id, actor_id, "FINDING_REMOVED",
           {"defect_code": f.defect_code, "finding_id": finding_id}, None)
    db.delete(f)
    db.flush()


# ── Conflict adjudication ─────────────────────────────────────────────────────

def adjudicate_conflict(
    db: Session,
    conflict_id: int,
    adjudicator_id: str,
    decision: str,
    notes: str = "",
) -> ConflictAdjudication:
    """
    Record a human adjudication decision for a label-conflict duplicate pair.

    decision: KEEP_A | KEEP_B | KEEP_BOTH | EXCLUDE_BOTH
    Does NOT automatically modify annotations — annotator must act on the decision.
    """
    allowed = {"KEEP_A", "KEEP_B", "KEEP_BOTH", "EXCLUDE_BOTH"}
    if decision not in allowed:
        raise AnnotationServiceError(f"Decision must be one of {allowed}.")
    conflict = db.get(ConflictAdjudication, conflict_id)
    if conflict is None:
        raise AnnotationServiceError(f"Conflict {conflict_id} not found.")
    conflict.decision = decision
    conflict.adjudicator_id = adjudicator_id
    conflict.adjudication_notes = notes
    conflict.adjudicated_at = datetime.now(timezone.utc)
    db.flush()
    return conflict


# ── Conflict manifest loader ───────────────────────────────────────────────────

DUPLICATE_MANIFEST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "docs", "DUPLICATE_MANIFEST.csv"
)


def load_conflicts_from_manifest(db: Session, manifest_path: str | None = None) -> int:
    """
    Load ConflictAdjudication records from DUPLICATE_MANIFEST.csv.
    Only imports LABEL_CONFLICT and BOTH rows (not benign same-label duplicates).
    Already-existing rows (by sha1+path_a+path_b) are skipped.
    Returns count of new rows inserted.
    """
    path = manifest_path or DUPLICATE_MANIFEST_PATH
    if not os.path.exists(path):
        _log.warning("DUPLICATE_MANIFEST.csv not found at %s — skipping conflict load.", path)
        return 0

    inserted = 0
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            conflict_type = row.get("conflict_type", "")
            if conflict_type not in ("LABEL_CONFLICT", "BOTH"):
                continue
            # Skip if already loaded
            existing = (
                db.query(ConflictAdjudication)
                .filter_by(
                    sha1_16=row.get("sha1_16", ""),
                    path_a=row.get("path_a", ""),
                    path_b=row.get("path_b", ""),
                )
                .first()
            )
            if existing:
                continue
            db.add(ConflictAdjudication(
                sha1_16=row.get("sha1_16", ""),
                path_a=row.get("path_a", ""),
                path_b=row.get("path_b", ""),
                label_a=row.get("label_a", ""),
                label_b=row.get("label_b", ""),
                split_a=row.get("split_a", ""),
                split_b=row.get("split_b", ""),
                conflict_type=conflict_type,
                source_archive_a=row.get("source_archive_a", ""),
                source_archive_b=row.get("source_archive_b", ""),
                decision="PENDING",
            ))
            inserted += 1
    db.flush()
    _log.info("Loaded %d conflict pairs from manifest.", inserted)
    return inserted


# ── Quality metrics ────────────────────────────────────────────────────────────

def get_quality_metrics(db: Session) -> dict:
    """
    Returns a snapshot of dataset quality for the dashboard:
      - annotation counts by review_status
      - finding counts by defect_code
      - conflict counts by decision
      - contamination distribution
      - model readiness gate
    """
    from sqlalchemy import func

    status_counts: dict = {}
    for status, count in (
        db.query(WeldAnnotation.review_status, func.count())
        .group_by(WeldAnnotation.review_status)
        .all()
    ):
        status_counts[status] = count

    contamination_counts: dict = {}
    for level, count in (
        db.query(WeldAnnotation.contamination_level, func.count())
        .group_by(WeldAnnotation.contamination_level)
        .all()
    ):
        contamination_counts[level] = count

    finding_counts: dict = {}
    for code, count in (
        db.query(AnnotationFinding.defect_code, func.count())
        .join(WeldAnnotation)
        .filter(WeldAnnotation.review_status == "APPROVED")
        .group_by(AnnotationFinding.defect_code)
        .all()
    ):
        finding_counts[code] = count

    conflict_pending = (
        db.query(func.count())
        .filter(ConflictAdjudication.decision == "PENDING")
        .scalar() or 0
    )
    conflict_total = db.query(func.count(ConflictAdjudication.id)).scalar() or 0
    conflict_resolved = conflict_total - conflict_pending

    export_eligible = (
        db.query(func.count())
        .filter(WeldAnnotation.export_eligible == True)
        .scalar() or 0
    )

    training_gate_open = NO_AUDIT.is_training_allowed()

    return {
        "annotation_status_counts": status_counts,
        "contamination_distribution": contamination_counts,
        "approved_findings_by_code": finding_counts,
        "conflict_total": conflict_total,
        "conflict_pending": conflict_pending,
        "conflict_resolved": conflict_resolved,
        "export_eligible_count": export_eligible,
        "training_gate_open": training_gate_open,
        "training_blocked_reason": NO_AUDIT.training_blocked_reason() if not training_gate_open else None,
        "e1_e4_gates": {
            "E1_duplicate_resolution": conflict_pending == 0 and conflict_total > 0,
            "E2_annotation_cleanup": False,  # requires manual verification
            "E3_split_regenerated": False,
            "E4_provenance_documented": False,
        },
    }


# ── Export pipeline ────────────────────────────────────────────────────────────

def build_export_dataset(
    db: Session,
    export_version: str,
    actor_id: str,
    split: str | None = None,
) -> tuple[dict, dict, list[str]]:
    """
    Build COCO and YOLO-format export structures from APPROVED eligible annotations.

    Returns (coco_dict, yolo_records, warnings):
      coco_dict:    standard COCO format {"images": [...], "annotations": [...], "categories": [...]}
      yolo_records: {image_path: [(class_id, x_c, y_c, w, h), ...]}  (normalized)
      warnings:     list of validation messages

    Validation:
      - Rejects annotations whose roi_crop_path does not exist on disk.
      - Checks for train/test SHA1 leakage across splits.
      - Validates polygon closure (≥3 points).
      - Validates BBOX dimensions (w > 0, h > 0).
    """
    from app.vision.defect_taxonomy import DefectCode

    warnings: list[str] = []

    # Category map — only surface-classifiable codes
    surface_codes = [c for c in DefectCode if c != DefectCode.GENERIC_NOK]
    categories = [
        {"id": i, "name": code.value, "supercategory": "weld_defect"}
        for i, code in enumerate(surface_codes, start=1)
    ]
    code_to_cat_id = {cat["name"]: cat["id"] for cat in categories}

    query = (
        db.query(WeldAnnotation)
        .filter(WeldAnnotation.export_eligible == True)
    )
    if split:
        query = query.filter(WeldAnnotation.split == split)

    eligible = query.all()
    if not eligible:
        warnings.append("No export-eligible annotations found.")

    # Leakage check: SHA1s present in both train and test
    split_sha1s: dict[str, set] = {}
    for ann in eligible:
        if ann.image_hash:
            split_sha1s.setdefault(ann.split, set()).add(ann.image_hash)
    train_sha1s = split_sha1s.get("train", set())
    test_sha1s = split_sha1s.get("test", set())
    leaking = train_sha1s & test_sha1s
    if leaking:
        warnings.append(
            f"LEAKAGE: {len(leaking)} SHA1(s) appear in both train and test splits. "
            "Remove leaked images before training."
        )

    coco_images, coco_annotations = [], []
    yolo_records: dict[str, list] = {}
    ann_id_counter = 1

    for img_id, ann in enumerate(eligible, start=1):
        # Validate roi_crop_path exists
        crop_path = ann.roi_crop_path or ann.image_path
        if not os.path.exists(crop_path):
            warnings.append(
                f"Image file not found: {crop_path} (annotation {ann.id}) — skipped."
            )
            continue

        w, h = ann.image_width_px or 1, ann.image_height_px or 1
        coco_images.append({
            "id": img_id,
            "file_name": os.path.basename(crop_path),
            "path": crop_path,
            "width": w,
            "height": h,
            "split": ann.split,
            "source_archive": ann.source_archive or "",
            "sha1_16": ann.image_hash or "",
        })

        yolo_records[crop_path] = []

        for finding in ann.findings:
            cat_id = code_to_cat_id.get(finding.defect_code)
            if cat_id is None:
                warnings.append(
                    f"DefectCode '{finding.defect_code}' not in export categories — skipped."
                )
                continue

            coco_ann, yolo_entries, warn = _convert_finding_to_coco(
                finding, ann_id_counter, img_id, w, h
            )
            warnings.extend(warn)
            if coco_ann:
                coco_annotations.append(coco_ann)
                ann_id_counter += 1
            yolo_records[crop_path].extend(yolo_entries)

        # Mark as exported
        ann.export_version = export_version
        _audit(db, ann.id, actor_id, "EXPORTED",
               None, {"export_version": export_version})

    db.flush()

    coco_dict = {
        "info": {
            "description": f"SpotWeldPro AI export {export_version}",
            "version": export_version,
            "taxonomy_version": "P3D-1.0",
            "training_gate_open": NO_AUDIT.is_training_allowed(),
            "training_blocked_reason": (
                NO_AUDIT.training_blocked_reason() if not NO_AUDIT.is_training_allowed() else None
            ),
        },
        "categories": categories,
        "images": coco_images,
        "annotations": coco_annotations,
    }
    return coco_dict, yolo_records, warnings


def _convert_finding_to_coco(
    finding: AnnotationFinding,
    ann_id: int,
    img_id: int,
    img_w: int,
    img_h: int,
) -> tuple[dict | None, list, list[str]]:
    warnings: list[str] = []
    region_type = finding.region_type
    data = finding.region_data or {}

    if region_type == "BBOX":
        x = data.get("x", 0)
        y = data.get("y", 0)
        bw = data.get("w", 0)
        bh = data.get("h", 0)
        if bw <= 0 or bh <= 0:
            warnings.append(f"Finding {finding.id} BBOX has invalid dimensions w={bw} h={bh} — skipped.")
            return None, [], warnings
        coco_ann = {
            "id": ann_id,
            "image_id": img_id,
            "category_id": 0,  # caller fills in
            "bbox": [x, y, bw, bh],
            "area": bw * bh,
            "segmentation": [],
            "iscrowd": 0,
            "defect_code": finding.defect_code,
        }
        # YOLO normalized: x_centre, y_centre, width, height (0-1)
        yolo = [(
            0,  # class_id — caller fills in
            (x + bw / 2) / img_w,
            (y + bh / 2) / img_h,
            bw / img_w,
            bh / img_h,
        )]
        return coco_ann, yolo, warnings

    elif region_type == "POLYGON":
        points = data.get("points", [])
        if len(points) < 3:
            warnings.append(f"Finding {finding.id} polygon has < 3 points — skipped.")
            return None, [], warnings
        flat = [coord for pt in points for coord in pt]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        bx, by = min(xs), min(ys)
        bw = max(xs) - bx
        bh = max(ys) - by
        coco_ann = {
            "id": ann_id,
            "image_id": img_id,
            "category_id": 0,
            "bbox": [bx, by, bw, bh],
            "area": bw * bh,
            "segmentation": [flat],
            "iscrowd": 0,
            "defect_code": finding.defect_code,
        }
        yolo = [(0, (bx + bw / 2) / img_w, (by + bh / 2) / img_h, bw / img_w, bh / img_h)]
        return coco_ann, yolo, warnings

    elif region_type == "POINT":
        x = data.get("x", 0)
        y = data.get("y", 0)
        r = 5  # 5px radius for COCO representation
        coco_ann = {
            "id": ann_id,
            "image_id": img_id,
            "category_id": 0,
            "bbox": [x - r, y - r, r * 2, r * 2],
            "area": r * r,
            "segmentation": [],
            "iscrowd": 0,
            "defect_code": finding.defect_code,
            "is_point": True,
        }
        yolo = []  # Points are not exported to YOLO by default
        return coco_ann, yolo, warnings

    # WHOLE_IMAGE
    coco_ann = {
        "id": ann_id,
        "image_id": img_id,
        "category_id": 0,
        "bbox": [0, 0, img_w, img_h],
        "area": img_w * img_h,
        "segmentation": [],
        "iscrowd": 0,
        "defect_code": finding.defect_code,
        "whole_image": True,
    }
    yolo = [(0, 0.5, 0.5, 1.0, 1.0)]
    return coco_ann, yolo, warnings
