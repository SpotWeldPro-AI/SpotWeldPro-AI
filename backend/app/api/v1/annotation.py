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

import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.error_codes import ApiErrorCode
from app.models.annotation_entities import (
    AnnotationAuditEntry,
    AnnotationFinding,
    ConflictAdjudication,
    PhysicalTestEvidence,
    WeldAnnotation,
)
from app.models.entities import User
from app.models.enums import UserRole

# Allowlisted root for image-preview — prevents path traversal outside the dataset
_DATASET_ROOTS = [
    Path(r"D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\V5_dataset\raw_images"),
]
_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
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


# ── Conflict adjudication (must be before /{annotation_id} to avoid route clash) ─

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


@router.get("/conflicts/review-summary")
def review_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Returns conflict adjudication counts. Available to PE/QE/SA."""
    if user.role not in _ADJUDICATION_ROLES:
        raise HTTPException(
            status_code=403,
            detail="PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN role required.",
        )
    return get_review_summary(db)


@router.get("/conflicts/eligible-counts")
def eligible_counts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Recalculate training/eval eligibility from current DB decisions. PE/QE/SA."""
    if user.role not in _ADJUDICATION_ROLES:
        raise HTTPException(
            status_code=403,
            detail="PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN role required.",
        )
    return get_eligible_counts_post_review(db)


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


@router.delete("/{annotation_id}/finding/{finding_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
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
            detail={
                "error_code": ApiErrorCode.PERMISSION_DENIED,
                "message": "Dataset export requires QUALITY_ENGINEER or SYSTEM_ADMIN role.",
            },
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


# ── Image preview (read-only, path-allowlisted) ────────────────────────────────

@router.get("/image-preview")
def image_preview(
    path: str = Query(..., description="Absolute path to dataset image (read-only)"),
    user: User = Depends(get_current_user),
) -> FileResponse:
    """
    Serve a dataset image for side-by-side display in the conflict review UI.

    Security:
    - Requires authentication.
    - Path must resolve to within one of the _DATASET_ROOTS (no symlink escape).
    - Extension must be in _ALLOWED_EXTENSIONS.
    - File must exist.
    - Original images are NEVER modified by this endpoint.
    """
    try:
        p = Path(path).resolve()
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid path.")

    if p.suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail="File type not permitted.")

    allowed = any(
        str(p).startswith(str(root.resolve()))
        for root in _DATASET_ROOTS
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Path is outside the allowed dataset root.")

    if not p.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")

    mime, _ = mimetypes.guess_type(str(p))
    return FileResponse(str(p), media_type=mime or "image/png")


# ── E4 Physical Test Evidence ──────────────────────────────────────────────────

_VALID_TEST_METHODS = {
    "CROSS_SECTION", "PEEL_TEST", "CHISEL_TEST", "UT_SCAN",
    "XRF", "RADIOGRAPHIC", "OTHER",
}
_VALID_VERDICTS = {"ACCEPTABLE", "REJECTABLE", "INCONCLUSIVE", "UNREVIEWED"}
_VALID_EVIDENCE_QUALITY = {"VERIFIED", "UNVERIFIED", "INSUFFICIENT"}
_E4_ROLES = {UserRole.PROCESS_ENGINEER, UserRole.QUALITY_ENGINEER, UserRole.SYSTEM_ADMIN}


class PhysicalTestEvidenceCreate(BaseModel):
    image_path: str
    weld_id: str | None = None
    test_method: str = Field(..., description="CROSS_SECTION|PEEL_TEST|CHISEL_TEST|UT_SCAN|XRF|RADIOGRAPHIC|OTHER")
    test_date: str | None = None
    test_operator: str | None = None
    test_report_ref: str | None = None
    test_facility: str | None = None
    nugget_diameter_mm: float | None = None
    nugget_height_mm: float | None = None
    confirmed_defect_codes: str = ""
    verdict: str = "UNREVIEWED"
    acceptance_standard: str | None = None
    evidence_quality: str = "UNVERIFIED"
    notes: str = ""


def _ser_evidence(e: PhysicalTestEvidence) -> dict:
    return {
        "id": e.id,
        "image_path": e.image_path,
        "weld_id": e.weld_id,
        "test_method": e.test_method,
        "test_date": e.test_date,
        "test_operator": e.test_operator,
        "test_report_ref": e.test_report_ref,
        "test_facility": e.test_facility,
        "nugget_diameter_mm": e.nugget_diameter_mm,
        "nugget_height_mm": e.nugget_height_mm,
        "confirmed_defect_codes": e.confirmed_defect_codes,
        "verdict": e.verdict,
        "acceptance_standard": e.acceptance_standard,
        "evidence_quality": e.evidence_quality,
        "notes": e.notes,
        "created_by": e.created_by,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@router.post("/e4-evidence", status_code=status.HTTP_201_CREATED)
def create_e4_evidence(
    body: PhysicalTestEvidenceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Record a physical test evidence entry for E4 ground truth.

    Rules enforced:
    - PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN only.
    - test_method MUST NOT be SURFACE_OBSERVATION.
    - nugget_diameter_mm requires CROSS_SECTION or UT_SCAN method.
    - VERIFIED evidence_quality requires a non-empty test_report_ref.
    - image_path is stored as a read-only reference; original files are not modified.
    """
    if user.role not in _E4_ROLES:
        raise HTTPException(status_code=403, detail="E4 evidence entry requires PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN.")

    if body.test_method not in _VALID_TEST_METHODS:
        raise HTTPException(status_code=422, detail=f"test_method must be one of {sorted(_VALID_TEST_METHODS)}. SURFACE_OBSERVATION is not permitted here.")

    if body.verdict not in _VALID_VERDICTS:
        raise HTTPException(status_code=422, detail=f"verdict must be one of {sorted(_VALID_VERDICTS)}.")

    if body.evidence_quality not in _VALID_EVIDENCE_QUALITY:
        raise HTTPException(status_code=422, detail=f"evidence_quality must be one of {sorted(_VALID_EVIDENCE_QUALITY)}.")

    if body.nugget_diameter_mm is not None and body.test_method not in {"CROSS_SECTION", "UT_SCAN"}:
        raise HTTPException(status_code=422, detail="nugget_diameter_mm requires test_method=CROSS_SECTION or UT_SCAN.")

    if body.evidence_quality == "VERIFIED" and not (body.test_report_ref or "").strip():
        raise HTTPException(status_code=422, detail="VERIFIED evidence requires a non-empty test_report_ref.")

    record = PhysicalTestEvidence(
        image_path=body.image_path,
        weld_id=body.weld_id,
        test_method=body.test_method,
        test_date=body.test_date,
        test_operator=body.test_operator,
        test_report_ref=body.test_report_ref,
        test_facility=body.test_facility,
        nugget_diameter_mm=body.nugget_diameter_mm,
        nugget_height_mm=body.nugget_height_mm,
        confirmed_defect_codes=body.confirmed_defect_codes or "",
        verdict=body.verdict,
        acceptance_standard=body.acceptance_standard,
        evidence_quality=body.evidence_quality,
        notes=body.notes,
        created_by=user.email,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _ser_evidence(record)


@router.get("/e4-evidence")
def list_e4_evidence(
    image_path: str | None = Query(None),
    weld_id: str | None = Query(None),
    test_method: str | None = Query(None),
    verdict: str | None = Query(None),
    evidence_quality: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role not in _E4_ROLES:
        raise HTTPException(status_code=403, detail="E4 evidence query requires PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN.")
    q = db.query(PhysicalTestEvidence)
    if image_path:
        q = q.filter(PhysicalTestEvidence.image_path == image_path)
    if weld_id:
        q = q.filter(PhysicalTestEvidence.weld_id == weld_id)
    if test_method:
        q = q.filter(PhysicalTestEvidence.test_method == test_method)
    if verdict:
        q = q.filter(PhysicalTestEvidence.verdict == verdict)
    if evidence_quality:
        q = q.filter(PhysicalTestEvidence.evidence_quality == evidence_quality)
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"total": total, "offset": offset, "limit": limit, "items": [_ser_evidence(e) for e in items]}


@router.get("/e4-evidence/summary")
def e4_evidence_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Coverage summary: how many weld images have physical test evidence."""
    if user.role not in _E4_ROLES:
        raise HTTPException(status_code=403, detail="E4 summary requires PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN.")
    from sqlalchemy import func as sa_func
    total = db.query(PhysicalTestEvidence).count()
    total_dataset = 927

    images_with_evidence = (
        db.query(sa_func.count(sa_func.distinct(PhysicalTestEvidence.image_path))).scalar() or 0
    )

    by_method_rows = (
        db.query(PhysicalTestEvidence.test_method, sa_func.count())
        .group_by(PhysicalTestEvidence.test_method).all()
    )
    by_verdict_rows = (
        db.query(PhysicalTestEvidence.verdict, sa_func.count())
        .group_by(PhysicalTestEvidence.verdict).all()
    )
    by_quality_rows = (
        db.query(PhysicalTestEvidence.evidence_quality, sa_func.count())
        .group_by(PhysicalTestEvidence.evidence_quality).all()
    )

    verified = dict(by_quality_rows).get("VERIFIED", 0)
    return {
        "total": total,
        "total_evidence_records": total,
        "images_with_evidence": images_with_evidence,
        "total_dataset_images": total_dataset,
        "coverage_pct": round(images_with_evidence / total_dataset * 100, 1) if total_dataset > 0 else 0.0,
        "by_method": dict(by_method_rows),
        "by_verdict": dict(by_verdict_rows),
        "by_quality": dict(by_quality_rows),
        "verified_evidence_count": verified,
        "e4_gate_clear": verified >= total_dataset,
        "e4_gate_progress": f"{verified}/{total_dataset}",
        "e4_gap_pct": round((total_dataset - images_with_evidence) / total_dataset * 100, 1) if total_dataset > 0 else 100.0,
    }


@router.get("/e4-evidence/{evidence_id}")
def get_e4_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if user.role not in _E4_ROLES:
        raise HTTPException(status_code=403, detail="E4 evidence query requires PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN.")
    record = db.get(PhysicalTestEvidence, evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence record not found.")
    return _ser_evidence(record)


