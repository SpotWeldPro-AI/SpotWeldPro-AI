"""
Static inspection engine for SpotWeldPro.

Operates on a PreprocessedImage and returns a StaticInspectionResult.

Measurement labeling rules:
  - MEASURED: derived from calibrated pixel measurement; requires CalibrationConfig.
  - NOT_AVAILABLE: detection found a feature but calibration is absent, so mm value
    cannot be reported. The pixel-level detection still happened.
  - PREDICTED: reserved for future model-based inference; never used here.

Quality classification rules:
  - Status is NOT_EVALUATED unless AcceptanceCriteria are explicitly supplied.
  - Thresholds are never hard-coded inside this module.
  - Criteria must carry a version string; "unversioned" is accepted but noted.

Limitations (stated explicitly to avoid false claims):
  - Electrode indentation detection uses Hough circles. Performance degrades with
    poor lighting, out-of-focus images, or non-circular cap faces.
  - Defect detection is morphological only; no semantic classifier is loaded.
    Regions are labeled "anomalous_region", not specific defect types.
  - Cross-section nugget detection uses Otsu thresholding. It assumes the nugget
    has measurably different brightness from the surrounding material. Etched
    metallographic samples with clear contrast work best.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

try:
    import cv2 as _cv2
    _CV2_AVAILABLE = True
except ImportError:
    _cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False

from app.vision.preprocessing import PreprocessedImage
from app.vision.schemas import (
    AcceptanceCriteria,
    CalibrationConfig,
    DefectRegion,
    ElectrodeIndentation,
    ImageType,
    InspectionStatus,
    MeasurementSource,
    NuggetMeasurement,
    StaticInspectionResult,
)


class StaticAnalysisError(RuntimeError):
    """Raised when the analysis engine cannot proceed (e.g. OpenCV unavailable)."""


class StaticInspectionEngine:
    """Entry point for static weld inspection."""

    def inspect(
        self,
        image: PreprocessedImage,
        image_type: ImageType = ImageType.UNKNOWN,
        calibration: Optional[CalibrationConfig] = None,
        criteria: Optional[AcceptanceCriteria] = None,
    ) -> StaticInspectionResult:
        if not _CV2_AVAILABLE:
            raise StaticAnalysisError(
                "opencv-python-headless is required for static analysis. "
                "Install with: pip install 'opencv-python-headless>=4.8'"
            )

        inspection_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        notes: list[str] = list(image.notes)
        review_notes: list[str] = []

        electrode: Optional[ElectrodeIndentation] = None
        defects: List[DefectRegion] = []
        nugget: Optional[NuggetMeasurement] = None

        if image_type in (ImageType.SURFACE, ImageType.UNKNOWN):
            electrode = _detect_electrode_indentation(image.array, calibration, review_notes)
            defects = _detect_surface_defects(image.array, calibration)

        if image_type == ImageType.CROSS_SECTION:
            nugget = _detect_nugget_cross_section(image.array, calibration, review_notes)
            defects = _detect_surface_defects(image.array, calibration)

        if image_type == ImageType.UNKNOWN:
            notes.append(
                "Image type was not specified. Provide image_type=SURFACE or "
                "CROSS_SECTION for more accurate analysis."
            )

        status = _derive_status(electrode, defects, nugget, criteria, review_notes)

        return StaticInspectionResult(
            inspection_id=inspection_id,
            timestamp=timestamp,
            image_type=image_type,
            status=status,
            image_metadata=image.metadata,
            electrode_indentation=electrode,
            defects=defects,
            nugget=nugget,
            preprocessing_notes=notes,
            review_notes=review_notes,
            calibration=calibration,
        )


# ── Detection sub-functions ───────────────────────────────────────────────────

def _detect_electrode_indentation(
    bgr: np.ndarray,
    calibration: Optional[CalibrationConfig],
    review_notes: list[str],
) -> ElectrodeIndentation:
    """
    Detect the electrode indentation circle using Hough circle transform.

    Returns an ElectrodeIndentation. If no circle is found, source is NOT_AVAILABLE.
    """
    gray = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2GRAY)
    blurred = _cv2.GaussianBlur(gray, (9, 9), 2)

    h, w = gray.shape
    min_r = max(5, min(w, h) // 20)
    max_r = min(w, h) // 3

    circles = _cv2.HoughCircles(
        blurred,
        _cv2.HOUGH_GRADIENT,
        dp=1.5,
        minDist=min(w, h) // 4,
        param1=60,
        param2=25,
        minRadius=min_r,
        maxRadius=max_r,
    )

    if circles is None:
        review_notes.append(
            "No electrode indentation circle detected. "
            "Verify image focus, lighting, and that the indentation is visible."
        )
        return ElectrodeIndentation(
            source=MeasurementSource.NOT_AVAILABLE,
            confidence=0.0,
            contour_quality="not_assessed",
            notes=["HoughCircles found no candidate."],
        )

    circles_i = np.round(circles[0, :]).astype(int)
    cx, cy, r = int(circles_i[0, 0]), int(circles_i[0, 1]), int(circles_i[0, 2])
    diameter_px = r * 2.0
    confidence = _circle_edge_confidence(gray, cx, cy, r)
    contour_quality = (
        "good" if confidence > 0.65
        else "fair" if confidence > 0.35
        else "poor"
    )

    if calibration is not None:
        ppmm = calibration.pixels_per_mm
        diameter_mm = round(diameter_px / ppmm, 3)
        area_mm2 = round(np.pi * (diameter_px / 2 / ppmm) ** 2, 4)
        source = MeasurementSource.MEASURED
    else:
        diameter_mm = None
        area_mm2 = None
        source = MeasurementSource.NOT_AVAILABLE
        review_notes.append(
            "Electrode indentation detected in pixels but calibration is absent; "
            "mm values are unavailable. Provide pixels_per_mm for metric output."
        )

    return ElectrodeIndentation(
        diameter_mm=diameter_mm,
        area_mm2=area_mm2,
        source=source,
        confidence=round(confidence, 3),
        contour_quality=contour_quality,
        notes=[f"Circle center ({cx},{cy}), radius {r} px."],
    )


def _circle_edge_confidence(gray: np.ndarray, cx: int, cy: int, r: int) -> float:
    """
    Estimate detection confidence from edge contrast along the circle perimeter.
    Samples 36 points just inside and outside the radius and computes mean contrast.
    """
    h, w = gray.shape
    angles = np.linspace(0, 2 * np.pi, 36, endpoint=False)
    inner, outer = [], []
    for a in angles:
        xi = int(cx + max(1, r - 4) * np.cos(a))
        yi = int(cy + max(1, r - 4) * np.sin(a))
        xo = int(cx + (r + 4) * np.cos(a))
        yo = int(cy + (r + 4) * np.sin(a))
        if 0 <= xi < w and 0 <= yi < h:
            inner.append(float(gray[yi, xi]))
        if 0 <= xo < w and 0 <= yo < h:
            outer.append(float(gray[yo, xo]))
    if not inner or not outer:
        return 0.3
    contrast = abs(float(np.mean(inner)) - float(np.mean(outer)))
    return min(1.0, contrast / 80.0)


def _detect_surface_defects(
    bgr: np.ndarray,
    calibration: Optional[CalibrationConfig],
) -> List[DefectRegion]:
    """
    Detect anomalous surface regions using adaptive thresholding and morphology.

    All detected regions are labeled "anomalous_region"; no semantic defect
    classification is applied (no classifier model is loaded).
    """
    gray = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2GRAY)
    thresh = _cv2.adaptiveThreshold(
        gray, 255,
        _cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        _cv2.THRESH_BINARY_INV,
        blockSize=51, C=12,
    )
    kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = _cv2.morphologyEx(thresh, _cv2.MORPH_OPEN, kernel, iterations=1)
    cleaned = _cv2.morphologyEx(cleaned, _cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = _cv2.findContours(
        cleaned, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE
    )

    img_area = gray.shape[0] * gray.shape[1]
    min_px = max(80, img_area // 15000)
    max_px = img_area // 8

    defects: List[DefectRegion] = []
    for cnt in contours:
        area_px = float(_cv2.contourArea(cnt))
        if area_px < min_px or area_px > max_px:
            continue
        x, y, bw, bh = _cv2.boundingRect(cnt)
        if calibration is not None:
            ppmm2 = calibration.pixels_per_mm ** 2
            area_mm2 = round(area_px / ppmm2, 4)
            source = MeasurementSource.MEASURED
        else:
            area_mm2 = None
            source = MeasurementSource.NOT_AVAILABLE
        defects.append(DefectRegion(
            label="anomalous_region",
            bbox_pixels=(x, y, bw, bh),
            area_mm2=area_mm2,
            source=source,
            confidence=0.25,
        ))
    return defects


def _detect_nugget_cross_section(
    bgr: np.ndarray,
    calibration: Optional[CalibrationConfig],
    review_notes: list[str],
) -> NuggetMeasurement:
    """
    Detect nugget boundary in a cross-section image using Otsu thresholding.

    Best results with etched metallographic samples where the nugget shows
    clear brightness contrast against the base metal.
    """
    gray = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2GRAY)
    blurred = _cv2.GaussianBlur(gray, (5, 5), 1)
    _, thresh = _cv2.threshold(blurred, 0, 255, _cv2.THRESH_BINARY + _cv2.THRESH_OTSU)

    kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
    cleaned = _cv2.morphologyEx(thresh, _cv2.MORPH_CLOSE, kernel, iterations=2)
    cleaned = _cv2.morphologyEx(cleaned, _cv2.MORPH_OPEN, kernel, iterations=2)

    contours, _ = _cv2.findContours(
        cleaned, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        review_notes.append("No nugget boundary found after Otsu thresholding.")
        return NuggetMeasurement(
            source=MeasurementSource.NOT_AVAILABLE,
            notes=["No contours found."],
        )

    # Pick the most circular contour with area > 500 px
    best_cnt = None
    best_circ = 0.0
    for cnt in contours:
        area = float(_cv2.contourArea(cnt))
        perim = float(_cv2.arcLength(cnt, True))
        if perim < 1 or area < 500:
            continue
        circ = (4.0 * np.pi * area) / (perim ** 2)
        if circ > best_circ:
            best_circ = circ
            best_cnt = cnt

    if best_cnt is None:
        review_notes.append("No suitably circular contour found in cross-section.")
        return NuggetMeasurement(
            source=MeasurementSource.NOT_AVAILABLE,
            notes=["All contours had circularity < threshold or area < 500 px."],
        )

    (_, _), radius_px = _cv2.minEnclosingCircle(best_cnt)
    diameter_px = float(radius_px) * 2.0
    area_px = float(_cv2.contourArea(best_cnt))

    nns: list[str] = [
        f"Best contour: diameter {diameter_px:.1f} px, "
        f"circularity {best_circ:.3f}."
    ]

    if calibration is not None:
        ppmm = calibration.pixels_per_mm
        diameter_mm = round(diameter_px / ppmm, 3)
        area_mm2 = round(area_px / (ppmm ** 2), 4)
        source = MeasurementSource.MEASURED
    else:
        diameter_mm = None
        area_mm2 = None
        source = MeasurementSource.NOT_AVAILABLE
        review_notes.append(
            "Nugget boundary found but calibration absent; mm values unavailable."
        )

    return NuggetMeasurement(
        diameter_mm=diameter_mm,
        area_mm2=area_mm2,
        source=source,
        notes=nns,
    )


# ── Status derivation ─────────────────────────────────────────────────────────

def _derive_status(
    electrode: Optional[ElectrodeIndentation],
    defects: List[DefectRegion],
    nugget: Optional[NuggetMeasurement],
    criteria: Optional[AcceptanceCriteria],
    review_notes: list[str],
) -> InspectionStatus:
    """
    Derive InspectionStatus from results and acceptance criteria.

    Without criteria: NOT_EVALUATED (never assume OK).
    With criteria: evaluate rules and return OK / NOK / REVIEW.
    """
    if criteria is None:
        return InspectionStatus.NOT_EVALUATED

    if criteria.criteria_version == "unversioned":
        review_notes.append(
            "Acceptance criteria have no version string. "
            "Version and attribute criteria before using them for production decisions."
        )

    nok_reasons: list[str] = []
    review_reasons: list[str] = []

    # Nugget diameter checks
    if nugget is not None and nugget.diameter_mm is not None:
        if (
            criteria.min_nugget_diameter_mm is not None
            and nugget.diameter_mm < criteria.min_nugget_diameter_mm
        ):
            nok_reasons.append(
                f"Nugget diameter {nugget.diameter_mm:.3f} mm < "
                f"minimum {criteria.min_nugget_diameter_mm} mm "
                f"(criteria {criteria.criteria_version})."
            )
        if (
            criteria.max_nugget_diameter_mm is not None
            and nugget.diameter_mm > criteria.max_nugget_diameter_mm
        ):
            review_reasons.append(
                f"Nugget diameter {nugget.diameter_mm:.3f} mm > "
                f"maximum {criteria.max_nugget_diameter_mm} mm; review required."
            )

    # Defect count check
    if criteria.max_allowed_defects is not None and len(defects) > criteria.max_allowed_defects:
        nok_reasons.append(
            f"{len(defects)} anomalous regions detected; "
            f"maximum allowed: {criteria.max_allowed_defects}."
        )

    # Uncalibrated measurements degrade to REVIEW even if other rules pass
    any_uncalibrated = (
        (nugget is not None and nugget.source == MeasurementSource.NOT_AVAILABLE)
        or (electrode is not None and electrode.source == MeasurementSource.NOT_AVAILABLE)
    )
    if any_uncalibrated:
        review_reasons.append(
            "Some measurements could not be expressed in physical units (calibration absent). "
            "Provide pixels_per_mm to enable metric evaluation."
        )

    if nok_reasons:
        review_notes.extend(nok_reasons)
        return InspectionStatus.NOK
    if review_reasons:
        review_notes.extend(review_reasons)
        return InspectionStatus.REVIEW
    return InspectionStatus.OK
