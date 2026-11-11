"""POST /api/v1/vision/static/inspect — Authenticated static image inspection.

ACCESS POLICY: Requires authenticated user (any role).

What this endpoint does:
  - Accepts an image upload plus optional calibration and ROI parameters.
  - Returns a StaticInspectionResult with labeled measurements.
  - Reports InspectionStatus = NOT_EVALUATED unless acceptance criteria are supplied.
  - Every measurement carries a MeasurementSource label (MEASURED / NOT_AVAILABLE).

What this endpoint does NOT do:
  - Never fabricates measurements or invents quality verdicts.
  - Does not store images or inspection results (stateless; persistence is a Phase 2 scope).
  - Does not actuate any external system or PLC.
  - Does not apply standards-based thresholds unless the caller explicitly supplies them.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import get_current_user
from app.vision.preprocessing import ImagePreprocessor, PreprocessingError
from app.vision.schemas import (
    AcceptanceCriteria,
    CalibrationConfig,
    ImageType,
    ROIConfig,
    StaticInspectionResult,
)
from app.vision.static_analysis import StaticAnalysisError, StaticInspectionEngine

router = APIRouter(prefix="/vision/static", tags=["Vision - Static Inspection"])

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/inspect", response_model=StaticInspectionResult)
async def inspect_image(
    image: UploadFile = File(..., description="Image file: JPEG, PNG, TIFF, BMP, or WebP"),
    image_type: ImageType = Form(
        ImageType.UNKNOWN,
        description="SURFACE for electrode views; CROSS_SECTION for metallographic images.",
    ),
    pixels_per_mm: Optional[float] = Form(
        None,
        gt=0.0,
        description="Calibration scale factor. Required for mm measurements.",
    ),
    roi_x: Optional[int] = Form(None, ge=0, description="ROI left edge (px)"),
    roi_y: Optional[int] = Form(None, ge=0, description="ROI top edge (px)"),
    roi_w: Optional[int] = Form(None, gt=0, description="ROI width (px)"),
    roi_h: Optional[int] = Form(None, gt=0, description="ROI height (px)"),
    min_nugget_diameter_mm: Optional[float] = Form(
        None, gt=0.0, description="Acceptance criterion: minimum nugget diameter (mm)."
    ),
    max_nugget_diameter_mm: Optional[float] = Form(
        None, gt=0.0, description="Acceptance criterion: maximum nugget diameter (mm)."
    ),
    max_allowed_defects: Optional[int] = Form(
        None, ge=0, description="Acceptance criterion: maximum defect count."
    ),
    criteria_version: str = Form(
        "unversioned",
        description="Version string for the acceptance criteria. Always attribute and version criteria.",
    ),
    _user=Depends(get_current_user),
) -> StaticInspectionResult:
    """
    Analyze a weld inspection image (surface view or cross-section).

    **mm measurements** require `pixels_per_mm`.
    **Quality status** (OK/NOK/REVIEW) requires at least one acceptance criterion.
    Without criteria, `status` is `NOT_EVALUATED`.
    """
    raw = await image.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error_code": "IMAGE_TOO_LARGE",
                "message": (
                    f"Image exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
                ),
            },
        )

    # Build optional sub-objects
    calibration: Optional[CalibrationConfig] = (
        CalibrationConfig(pixels_per_mm=pixels_per_mm) if pixels_per_mm is not None else None
    )
    roi: Optional[ROIConfig] = (
        ROIConfig(x=roi_x, y=roi_y, width=roi_w, height=roi_h)
        if all(v is not None for v in [roi_x, roi_y, roi_w, roi_h])
        else None
    )
    criteria: Optional[AcceptanceCriteria] = (
        AcceptanceCriteria(
            min_nugget_diameter_mm=min_nugget_diameter_mm,
            max_nugget_diameter_mm=max_nugget_diameter_mm,
            max_allowed_defects=max_allowed_defects,
            criteria_version=criteria_version,
            criteria_source="api_request",
        )
        if any(v is not None for v in [min_nugget_diameter_mm, max_nugget_diameter_mm, max_allowed_defects])
        else None
    )

    # Preprocessing
    try:
        preprocessor = ImagePreprocessor()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error_code": "VISION_UNAVAILABLE", "message": str(exc)},
        )

    try:
        img = preprocessor.load_and_validate(raw, filename=image.filename or "")
    except PreprocessingError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "INVALID_IMAGE", "message": str(exc)},
        )

    if roi is not None:
        try:
            img = preprocessor.apply_roi(img, roi)
        except PreprocessingError as exc:
            raise HTTPException(
                status_code=422,
                detail={"error_code": "INVALID_ROI", "message": str(exc)},
            )

    # Analysis
    try:
        engine = StaticInspectionEngine()
        return engine.inspect(img, image_type=image_type, calibration=calibration, criteria=criteria)
    except StaticAnalysisError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error_code": "ANALYSIS_ERROR", "message": str(exc)},
        )
