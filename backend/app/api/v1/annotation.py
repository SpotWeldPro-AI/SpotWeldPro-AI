"""
VISION-P3E: Annotation management API.

Endpoints:
  POST   /api/v1/annotation/                   Create annotation record
  GET    /api/v1/annotation/                   List annotations (filterable)
  GET    /api/v1/annotation/{id}               Get annotation + findings
  PATCH  /api/v1/annotation/{id}/submit        Submit for review (DRAFT → SUBMITTED)
  POST   /api/v1/annotation/{id}/finding       Add a finding
  DELETE /api/v1/annotation/{id}/finding/{fid} Remove a finding
  POST   /api/v1/annotation/{id}/review        Reviewer decision
  POST   /api/v1/annotation/{id}/reopen        Reopen (NEEDS_REVISION / REJECTED → DRAFT)
  GET    /api/v1/annotation/{id}/audit         Audit trail for one annotation

  GET    /api/v1/annotation/conflicts          List conflict pairs (paginated, filterable)
  PATCH  /api/v1/annotation/conflicts/{cid}    Adjudicate a conflict pair

  GET    /api/v1/annotation/dashboard          Quality metrics dashboard
  POST   /api/v1/annotation/export             Build export (COCO + YOLO)
  POST   /api/v1/annotation/load-conflicts     Load manifest (admin only)

ACCESS POLICY:
  - Any authenticated user may create annotations and add findings.
  - Review decisions require a different user than the annotator (self-approval blocked).
  - Conflict adjudication: PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN only.
  - Export: QUALITY_ENGINEER or SYSTEM_ADMIN only.
  - load-conflicts: SYSTEM_ADMIN only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.annotation_entities import (
    AnnotationAuditEntry,
    AnnotationFinding,
    ConflictAdjudication,
    WeldAnnotation,
)
from app.models.entities import User
from app.models.enums import UserRole
from app.vision.annotation_service import (
    AnnotationServiceError,
    InvalidTransitionError,
    SelfApprovalError,
    add_finding,
    adjudicate_conflict,
    build_export_dataset,
    create_annotation,
    get_eligible_counts_post_review,
    get_quality_metrics,
    get_review_summary,
    load_conflicts_from_manifest,
    load_e1_queue_from_manifest,
    remove_finding,
    reopen_annotation,
    review_annotation,
    submit_annotation,
)

router = APIRouter(prefix="/annotation", tags=["Vision - Annotation"])

_ADJUDICATION_ROLES = {UserRole.PROCESS_ENGINEER, UserRole.QUALITY_ENGINEER, UserRole.SYSTEM_ADMIN}
_EXPORT_ROLES = {UserRole.QUALITY_ENGINEER, UserRole.SYSTEM_ADMIN}


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AnnotationCreate(BaseModel):
    image_path: str = Field(..., description="Absolute path to original image (read-only reference)")
    image_hash: str | None = None
    weld_id: str | None = None
    source_archive: str | None = None
    split: str = "unknown"
    label_provenance: str = "SURFACE_OBSERVATION"
    contamination_level: str = "UNKNOWN"
    max_markup_ratio: float = 0.0
    image_width_px: int | None = None
    image_height_px: int | None = None


class FindingCreate(BaseModel):
    defect_code: str
    name_tr: str
    name_en: str
    region_type: str = "BBOX"
    region_data: dict = Field(default_factory=dict)
    confidence: float = 0.0
    requires_physical_confirmation: bool = False
    is_surface_classifiable: bool = True


class ReviewDecision(BaseModel):
    decision: str = Field(..., description="approve | reject | request_revision")
    notes: str = ""


class AdjudicationDecision(BaseModel):
    decision: str = Field(..., description="KEEP_A | KEEP_B | KEEP_BOTH | EXCLUDE_BOTH")
    notes: str = ""


class ExportRequest(BaseModel):
    export_version: str
    split: str | None = None


# ── Serialisers ────────────────────────────────────────────────────────────────

def _ser_finding(f: AnnotationFinding) -> dict:
    return {
        "id": f.id,
        "defect_code": f.defect_code,
        "name_tr": f.name_tr,
        "name_en": f.name_en,
        "region_type": f.region_type,
        "region_data": f.region_data,
        "confidence": f.confidence,
        "confidence_source": f.confidence_source,
        "requires_physical_confirmation": f.requires_physical_confirmation,
        "is_surface_classifiable": f.is_surface_classifiable,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _ser_annotation(ann: WeldAnnotation, include_findings: bool = True) -> dict:
    out = {
        "id": ann.id,
        "image_path": ann.image_path,
        "roi_crop_path": ann.roi_crop_path,
        "image_hash": ann.image_hash,
        "weld_id": ann.weld_id,
        "source_archive": ann.source_archive,
        "split": ann.split,
        "label_provenance": ann.label_provenance,
        "contamination_level": ann.contamination_level,
        "max_markup_ratio": ann.max_markup_ratio,
        "is_roi_cropped": ann.is_roi_cropped,
        "annotation_markup_removed": ann.annotation_markup_removed,
        "image_width_px": ann.image_width_px,
        "image_height_px": ann.image_height_px,
        "annotator_id": ann.annotator_id,
        "review_status": ann.review_status,
        "taxonomy_version": ann.taxonomy_version,
        "export_eligible": ann.export_eligible,
        "export_version": ann.export_version,
        "created_at": ann.created_at.isoformat() if ann.created_at else None,
        "updated_at": ann.updated_at.isoformat() if ann.updated_at else None,
    }
    if include_findings:
        out["findings"] = [_ser_finding(f) for f in ann.findings]
    return out


def _ser_conflict(c: ConflictAdjudication) -> dict:
    return {
        "id": c.id,
        "sha1_16": c.sha1_16,
        "path_a": c.path_a,
        "path_b": c.path_b,
        "label_a": c.label_a,
        "label_b": c.label_b,
        "split_a": c.split_a,
        "split_b": c.split_b,
        "conflict_type": c.conflict_type,
        "source_archive_a": c.source_archive_a,
        "source_archive_b": c.source_archive_b,
        "decision": c.decision,
        "adjudicator_id": c.adjudicator_id,
        "adjudication_notes": c.adjudication_notes,
        "adjudicated_at": c.adjudicated_at.isoformat() if c.adjudicated_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ── Annotation CRUD ────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
def create(
    body: AnnotationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ann = create_annotation(
        db,
        image_path=body.image_path,
        annotator_id=user.email,
        image_hash=body.image_hash,
        weld_id=body.weld_id,
        source_archive=body.source_archive,
        split=body.split,
        label_provenance=body.label_provenance,
        contamination_level=body.contamination_level,
        max_markup_ratio=body.max_markup_ratio,
        image_width_px=body.image_width_px,
        image_height_px=body.image_height_px,
    )
    db.commit()
    return _ser_annotation(ann)


@router.get("/")
def list_annotations(
    review_status: str | None = Query(None),
    split: str | None = Query(None),
    contamination_level: str | None = Query(None),
    export_eligible: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    q = db.query(WeldAnnotation)
    if review_status:
        q = q.filter(WeldAnnotation.review_status == review_status)
    if split:
        q = q.filter(WeldAnnotation.split == split)
    if contamination_level:
        q = q.filter(WeldAnnotation.contamination_level == contamination_level)
    if export_eligible is not None:
        q = q.filter(WeldAnnotation.export_eligible == export_eligible)
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_ser_annotation(a, include_findings=False) for a in items],
    }


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return get_quality_metrics(db)


@router.get("/{annotation_id}")
def get_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ann = db.get(WeldAnnotation, annotation_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Annotation not found.")
    return _ser_annotation(ann)


@router.patch("/{annotation_id}/submit")
def submit(
    annotation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        ann = submit_annotation(db, annotation_id, user.email)
        db.commit()
    except (AnnotationServiceError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ser_annotation(ann)


@router.post("/{annotation_id}/finding", status_code=status.HTTP_201_CREATED)
def add_finding_ep(
    annotation_id: int,
    body: FindingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        f = add_finding(
            db,
            annotation_id=annotation_id,
            actor_id=user.email,
            defect_code=body.defect_code,
            name_tr=body.name_tr,
            name_en=body.name_en,
            region_type=body.region_type,
            region_data=body.region_data,
            confidence=body.confidence,
            requires_physical_confirmation=body.requires_physical_confirmation,
            is_surface_classifiable=body.is_surface_classifiable,
        )
        db.commit()
    except AnnotationServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ser_finding(f)


@router.delete("/{annotation_id}/finding/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_finding_ep(
    annotation_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        remove_finding(db, finding_id, user.email)
        db.commit()
    except AnnotationServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{annotation_id}/review")
def review(
    annotation_id: int,
    body: ReviewDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        ann = review_annotation(db, annotation_id, user.email, body.decision, body.notes)
        db.commit()
    except SelfApprovalError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (AnnotationServiceError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ser_annotation(ann)


@router.post("/{annotation_id}/reopen")
def reopen(
    annotation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        ann = reopen_annotation(db, annotation_id, user.email)
        db.commit()
    except (AnnotationServiceError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ser_annotation(ann)


@router.get("/{annotation_id}/audit")
def get_audit(
    annotation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ann = db.get(WeldAnnotation, annotation_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Annotation not found.")
    entries = (
        db.query(AnnotationAuditEntry)
        .filter(AnnotationAuditEntry.annotation_id == annotation_id)
        .order_by(AnnotationAuditEntry.created_at)
        .all()
    )
    return {
        "annotation_id": annotation_id,
        "entries": [
            {
                "id": e.id,
                "actor_id": e.actor_id,
                "action": e.action,
                "before_state": e.before_state,
                "after_state": e.after_state,
                "notes": e.notes,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }


# ── Conflict adjudication ─────────────────────────────────────────────────────

@router.get("/conflicts")
def list_conflicts(
    decision: str | None = Query(None, description="Filter by decision: PENDING | KEEP_A | ..."),
    conflict_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    q = db.query(ConflictAdjudication)
    if decision:
        q = q.filter(ConflictAdjudication.decision == decision)
    if conflict_type:
        q = q.filter(ConflictAdjudication.conflict_type == conflict_type)
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_ser_conflict(c) for c in items],
    }


@router.patch("/conflicts/{conflict_id}")
def adjudicate(
    conflict_id: int,
    body: AdjudicationDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role not in _ADJUDICATION_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Conflict adjudication requires PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN role.",
        )
    try:
        conflict = adjudicate_conflict(db, conflict_id, user.email, body.decision, body.notes)
        db.commit()
    except AnnotationServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _ser_conflict(conflict)


# ── Export ─────────────────────────────────────────────────────────────────────

@router.post("/export")
def export_dataset(
    body: ExportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role not in _EXPORT_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Dataset export requires QUALITY_ENGINEER or SYSTEM_ADMIN role.",
        )
    coco, yolo, warnings = build_export_dataset(
        db, body.export_version, user.email, body.split
    )
    db.commit()
    return {
        "export_version": body.export_version,
        "coco_image_count": len(coco.get("images", [])),
        "coco_annotation_count": len(coco.get("annotations", [])),
        "yolo_image_count": len(yolo),
        "warnings": warnings,
        "training_gate_open": coco["info"]["training_gate_open"],
        "training_blocked_reason": coco["info"]["training_blocked_reason"],
        "coco": coco,
    }


# ── Admin: load conflict manifest ─────────────────────────────────────────────

@router.post("/load-conflicts", status_code=status.HTTP_200_OK)
def load_conflicts(
    manifest_path: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(status_code=403, detail="SYSTEM_ADMIN role required.")
    inserted = load_conflicts_from_manifest(db, manifest_path)
    db.commit()
    return {"inserted": inserted}


# ── P3I: E1 queue loader (loads from E1_CONFLICT_REVIEW_QUEUE.csv) ─────────────

@router.post("/load-e1-queue", status_code=status.HTTP_200_OK)
def load_e1_queue(
    manifest_path: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Load ConflictAdjudication records from E1_CONFLICT_REVIEW_QUEUE.csv (P3H output).
    Includes CROSS_SPLIT_LEAKAGE rows in addition to LABEL_CONFLICT and BOTH.
    SYSTEM_ADMIN only.
    """
    if user.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(status_code=403, detail="SYSTEM_ADMIN role required.")
    inserted = load_e1_queue_from_manifest(db, manifest_path)
    db.commit()
    return {"inserted": inserted}


# ── P3I: Review summary ────────────────────────────────────────────────────────

@router.get("/conflicts/review-summary")
def review_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Returns conflict adjudication counts by decision value.
    Available to PROCESS_ENGINEER, QUALITY_ENGINEER, SYSTEM_ADMIN.
    """
    if user.role not in _ADJUDICATION_ROLES:
        raise HTTPException(
            status_code=403,
            detail="PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN role required.",
        )
    return get_review_summary(db)


# ── P3I: Eligible counts post-review ──────────────────────────────────────────

@router.get("/conflicts/eligible-counts")
def eligible_counts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Recalculate training-eligible and eval-eligible sample counts using
    decisions recorded in the conflict_adjudications table.

    Does not count contaminated or unverifiable records as qualified.
    Available to PROCESS_ENGINEER, QUALITY_ENGINEER, SYSTEM_ADMIN.
    """
    if user.role not in _ADJUDICATION_ROLES:
        raise HTTPException(
            status_code=403,
            detail="PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN role required.",
        )
    return get_eligible_counts_post_review(db)
