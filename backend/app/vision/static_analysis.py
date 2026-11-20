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

import math
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

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
    VisualFinding,
    VisualFindingCode,
    VisualFindingStatus,
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
        visual_findings = _classify_visual_findings(image.array)

        return StaticInspectionResult(
            inspection_id=inspection_id,
            timestamp=timestamp,
            image_type=image_type,
            status=status,
            image_metadata=image.metadata,
            electrode_indentation=electrode,
            defects=defects,
            nugget=nugget,
            visual_findings=visual_findings,
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


# ── Visual defect mode classifier ────────────────────────────────────────────

def _classify_visual_findings(bgr: np.ndarray) -> List[VisualFinding]:
    """
    Classify all 12 visual defect mode codes from pixel data only.

    Hard rules enforced here:
    - Filename, manifest ID, and synthetic metadata are NEVER used.
    - Only pixel values drive classification.
    - Supported modes return DETECTED or NOT_DETECTED.
    - Modes that cannot be assessed from this image return NOT_EVALUATED.
    - NORMAL_SURFACE is only reported DETECTED when no other weld defect is found.
    - Surface findings do NOT imply internal nugget acceptance.

    Supported (reliable, deterministic):
      IMAGE_BLUR, IMAGE_NOISE, INSUFFICIENT_LIGHTING,
      MISSING_WELD_INDICATION, MULTIPLE_WELD_POINTS, DOUBLE_SPOT_INDICATION,
      ELECTRODE_MISALIGNMENT, SURFACE_SPATTER, SUSPECTED_SURFACE_CRACK,
      SURFACE_DISCOLORATION, NORMAL_SURFACE.

    Partially supported (attempted; may return NOT_EVALUATED):
      ELLIPTICAL_INDENTATION — requires sufficient contour for fitEllipse.
    """
    findings: List[VisualFinding] = []
    h, w = bgr.shape[:2]
    gray = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2GRAY)

    # ── 1. IMAGE_BLUR — Laplacian variance ───────────────────────────────────
    lap_var = float(np.var(_cv2.Laplacian(gray, _cv2.CV_64F)))
    # Threshold 350 calibrated on 200×200 synthetic images: blur_variation (box filter)
    # gives ~255, normal sharp images give ~420+.  Adjust for real camera optics.
    is_blurry = lap_var < 350.0
    findings.append(VisualFinding(
        code=VisualFindingCode.IMAGE_BLUR,
        status=VisualFindingStatus.DETECTED if is_blurry else VisualFindingStatus.NOT_DETECTED,
        name_en="Image Blur",
        name_tr="Görüntü Bulanıklığı",
        evidence=f"Laplacian variance {lap_var:.1f} ({'<' if is_blurry else '>='} threshold 350.0).",
        source="Laplacian variance (CV deterministic)",
        limitations=(
            "Threshold calibrated on 200×200 synthetic images (box-filter blur). "
            "Real sensor out-of-focus blur requires separate calibration. "
            "High-noise images may also show low Laplacian variance."
        ),
        next_action_en="Recalibrate camera focus; re-inspect before accepting.",
        next_action_tr="Kamera odağını yeniden ayarlayın; kabul etmeden önce yeniden inceleyin.",
        internal_weld_integrity="Cannot assess — blurry image may mask real defect features.",
    ))

    # ── 2. IMAGE_NOISE — Gaussian residual ───────────────────────────────────
    blurred_n = _cv2.GaussianBlur(gray, (5, 5), 1.5)
    noise_mean = float(np.mean(np.abs(gray.astype(np.float32) - blurred_n.astype(np.float32))))
    is_noisy = noise_mean > 12.0
    findings.append(VisualFinding(
        code=VisualFindingCode.IMAGE_NOISE,
        status=VisualFindingStatus.DETECTED if is_noisy else VisualFindingStatus.NOT_DETECTED,
        name_en="Image Noise",
        name_tr="Görüntü Gürültüsü",
        evidence=f"Mean Gaussian residual {noise_mean:.1f} ({'>' if is_noisy else '<='} threshold 12.0).",
        source="Gaussian residual mean (CV deterministic)",
        limitations=(
            "Threshold calibrated on 200×200 synthetic images. "
            "Real sensor noise characteristics may differ."
        ),
        next_action_en="Check camera settings (ISO, gain); re-inspect with optimized sensor parameters.",
        next_action_tr="Kamera ayarlarını kontrol edin (ISO, kazanç); sensör parametrelerini optimize edip yeniden inceleyin.",
        internal_weld_integrity="Cannot assess — image noise may mask real defect features.",
    ))

    # ── 3. INSUFFICIENT_LIGHTING — mean brightness + gradient ────────────────
    mean_bri = float(np.mean(gray))
    std_bri = float(np.std(gray))
    left_mean = float(np.mean(gray[:, : w // 2]))
    right_mean = float(np.mean(gray[:, w // 2 :]))
    top_mean = float(np.mean(gray[: h // 2, :]))
    bot_mean = float(np.mean(gray[h // 2 :, :]))
    h_grad = abs(left_mean - right_mean) / max(mean_bri, 1.0)
    v_grad = abs(top_mean - bot_mean) / max(mean_bri, 1.0)
    is_dark = mean_bri < 60.0
    is_overexposed = mean_bri > 220.0 and std_bri < 25.0
    is_uneven = max(h_grad, v_grad) > 0.12
    is_lighting_issue = is_dark or is_overexposed or is_uneven
    if is_dark:
        lit_ev = f"Mean brightness {mean_bri:.0f}/255 — underexposed (threshold <60)."
    elif is_overexposed:
        lit_ev = f"Mean brightness {mean_bri:.0f}/255, std {std_bri:.0f} — overexposed."
    elif is_uneven:
        lit_ev = (
            f"Illumination gradient detected: H={h_grad*100:.0f}% V={v_grad*100:.0f}% "
            f"(threshold >12% half-image difference)."
        )
    else:
        lit_ev = f"Mean brightness {mean_bri:.0f}/255, std {std_bri:.0f} — acceptable."
    findings.append(VisualFinding(
        code=VisualFindingCode.INSUFFICIENT_LIGHTING,
        status=VisualFindingStatus.DETECTED if is_lighting_issue else VisualFindingStatus.NOT_DETECTED,
        name_en="Insufficient / Uneven Lighting",
        name_tr="Yetersiz / Düzensiz Aydınlatma",
        evidence=lit_ev,
        source="Mean brightness, std, and half-image gradient analysis (CV deterministic)",
        limitations=(
            "Gradient threshold (>15%) calibrated on synthetic images. "
            "Real illumination setups may require tuning."
        ),
        next_action_en="Adjust inspection lighting; verify illuminator calibration before re-inspection.",
        next_action_tr="İnceleme aydınlatmasını ayarlayın; yeniden incelemeden önce aydınlatıcı kalibrasyonunu doğrulayın.",
        internal_weld_integrity="Cannot assess — lighting conditions insufficient for reliable surface analysis.",
    ))

    # ── Electrode region detection (HoughCircles + dark contour fallback) ─────
    blurred_h = _cv2.GaussianBlur(gray, (9, 9), 2)
    min_r = max(5, min(w, h) // 20)
    max_r = min(w, h) // 3
    circles = _cv2.HoughCircles(
        blurred_h, _cv2.HOUGH_GRADIENT,
        dp=1.5, minDist=min(w, h) // 6,
        param1=60, param2=35,
        minRadius=min_r, maxRadius=max_r,
    )
    n_circles = 0
    all_circles: List[Tuple[int, int, int]] = []
    if circles is not None:
        for c in np.round(circles[0, :]).astype(int):
            all_circles.append((int(c[0]), int(c[1]), int(c[2])))
        n_circles = len(all_circles)
        all_circles.sort(key=lambda c: -c[2])  # largest radius first

    # Dark region contour fallback — detects non-circular weld marks
    mean_g = float(np.mean(gray))
    _, dark_mask = _cv2.threshold(
        gray, int(mean_g * 0.78), 255, _cv2.THRESH_BINARY_INV
    )
    ker = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (3, 3))
    dark_mask = _cv2.morphologyEx(dark_mask, _cv2.MORPH_OPEN, ker, iterations=1)
    dark_cnts, _ = _cv2.findContours(dark_mask, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
    weld_contour = None
    weld_area = 0.0
    for cnt in dark_cnts:
        area = float(_cv2.contourArea(cnt))
        if area < 0.005 * w * h or area > 0.5 * w * h:
            continue
        x, y, cw, ch = _cv2.boundingRect(cnt)
        in_central = (x > w * 0.05 and x + cw < w * 0.95
                      and y > h * 0.05 and y + ch < h * 0.95)
        if in_central and area > weld_area:
            weld_contour = cnt
            weld_area = area

    has_weld_region = weld_contour is not None

    # Primary electrode position
    if n_circles > 0:
        primary_cx, primary_cy, primary_r = all_circles[0]
    elif has_weld_region:
        x, y, cw, ch = _cv2.boundingRect(weld_contour)
        primary_cx, primary_cy = x + cw // 2, y + ch // 2
        primary_r = max(cw, ch) // 2
    else:
        primary_cx, primary_cy, primary_r = w // 2, h // 2, min(w, h) // 4

    # ── 4. MISSING_WELD_INDICATION ────────────────────────────────────────────
    is_missing = (n_circles == 0) and (not has_weld_region)
    findings.append(VisualFinding(
        code=VisualFindingCode.MISSING_WELD_INDICATION,
        status=VisualFindingStatus.DETECTED if is_missing else VisualFindingStatus.NOT_DETECTED,
        name_en="Missing Weld Indication",
        name_tr="Eksik Kaynak Belirtisi",
        evidence=(
            "No electrode indentation circle or dark weld region found."
            if is_missing else
            f"Electrode/weld region detected at ({primary_cx},{primary_cy}) r≈{primary_r}px."
        ),
        source="HoughCircles + dark contour fallback (CV deterministic)",
        limitations=(
            "Very faint impressions may pass the dark-region threshold and avoid detection. "
            "Physical inspection required for confirmation."
        ),
        next_action_en="Verify weld was performed; check PLC program and electrode contact records.",
        next_action_tr="Kaynağın yapıldığını doğrulayın; PLC programını ve elektrod temas kayıtlarını kontrol edin.",
        internal_weld_integrity=(
            "HIGH RISK: If confirmed missing, no nugget exists — structural bond absent."
            if is_missing else "Not assessed from surface image alone."
        ),
    ))

    # ── 5+6. MULTIPLE_WELD_POINTS + DOUBLE_SPOT_INDICATION ───────────────────
    if n_circles >= 3:
        st_multi, st_double = VisualFindingStatus.DETECTED, VisualFindingStatus.NOT_DETECTED
        ev_multi = f"{n_circles} electrode circles detected by HoughCircles."
        ev_double = f"{n_circles} circles detected — classified as MULTIPLE, not DOUBLE."
    elif n_circles == 2:
        st_multi, st_double = VisualFindingStatus.NOT_DETECTED, VisualFindingStatus.DETECTED
        sep = math.sqrt((all_circles[0][0]-all_circles[1][0])**2
                        + (all_circles[0][1]-all_circles[1][1])**2)
        ev_multi = "Only 2 circles detected."
        ev_double = f"2 electrode circles at separation {sep:.0f}px."
    else:
        st_multi, st_double = VisualFindingStatus.NOT_DETECTED, VisualFindingStatus.NOT_DETECTED
        ev_multi = "1 or 0 circles detected." if n_circles == 1 else "No circles detected."
        ev_double = ev_multi

    findings.append(VisualFinding(
        code=VisualFindingCode.MULTIPLE_WELD_POINTS,
        status=st_multi,
        name_en="Multiple Weld Points",
        name_tr="Çoklu Kaynak Noktası",
        evidence=ev_multi,
        source="HoughCircles count ≥3 (CV deterministic)",
        limitations="Circle detection may merge adjacent welds; separation threshold may need tuning.",
        next_action_en="Verify weld sequence program; check for robot program duplicate weld events.",
        next_action_tr="Kaynak sırası programını doğrulayın; robot programında tekrar kaynak olaylarını kontrol edin.",
        internal_weld_integrity="Multiple nuggets possible; HAZ overlap may affect each nugget.",
    ))
    findings.append(VisualFinding(
        code=VisualFindingCode.DOUBLE_SPOT_INDICATION,
        status=st_double,
        name_en="Double Spot Indication",
        name_tr="Çift Nokta Belirtisi",
        evidence=ev_double,
        source="HoughCircles count ==2 (CV deterministic)",
        limitations=(
            "Second circle may be an artifact (HAZ ring, lighting ring). "
            "Confirm visually; non-circular secondary marks are not counted."
        ),
        next_action_en="Inspect for duplicate weld event; check robot controller log for double-trigger.",
        next_action_tr="Tekrarlı kaynak olayını inceleyin; robot kontrolör günlüğünü çift tetikleme için kontrol edin.",
        internal_weld_integrity="Two adjacent nuggets risk HAZ interference. Cross-section recommended.",
    ))

    # ── 7. ELECTRODE_MISALIGNMENT (only when single circle found) ────────────
    if is_missing:
        misa_status = VisualFindingStatus.NOT_EVALUATED
        misa_ev = "Cannot assess — no electrode/weld region detected."
        misa_bbox = None
    elif n_circles != 1:
        # Ambiguous when 0 (no circle, but weld region) or >1 circles
        misa_status = VisualFindingStatus.NOT_EVALUATED
        misa_ev = (
            f"Cannot assess misalignment — {n_circles} circles detected "
            f"(requires exactly 1 for unambiguous offset measurement)."
        )
        misa_bbox = None
    else:
        cx_off = abs(primary_cx - w // 2) / w
        cy_off = abs(primary_cy - h // 2) / h
        max_off = max(cx_off, cy_off)
        is_misaligned = max_off > 0.10
        misa_status = (VisualFindingStatus.DETECTED if is_misaligned
                       else VisualFindingStatus.NOT_DETECTED)
        misa_ev = (
            f"Electrode center ({primary_cx},{primary_cy}) offset "
            f"{max_off*100:.0f}% from image center ({w//2},{h//2}) "
            f"({'exceeds' if is_misaligned else 'within'} 10% threshold)."
        )
        misa_bbox = (primary_cx - primary_r, primary_cy - primary_r,
                     2 * primary_r, 2 * primary_r) if is_misaligned else None

    findings.append(VisualFinding(
        code=VisualFindingCode.ELECTRODE_MISALIGNMENT,
        status=misa_status,
        name_en="Electrode Misalignment",
        name_tr="Elektrod Hizalama Hatası",
        evidence=misa_ev,
        source="HoughCircles center offset (CV deterministic; requires single circle)",
        limitations=(
            "Assumes weld should be centered in the frame. "
            "Intentional off-center framing will produce false positives. "
            "No absolute position reference — detection depends on camera framing."
        ),
        bbox_pixels=misa_bbox,
        next_action_en="Check robot TCP calibration; verify electrode alignment with weld symbol.",
        next_action_tr="Robot TCP kalibrasyonunu kontrol edin; elektrodu kaynak sembolü ile hizalayın.",
        internal_weld_integrity="Misaligned weld may produce off-center nugget; edge proximity increases failure risk.",
    ))

    # ── 8. ELLIPTICAL_INDENTATION — fitEllipse on dark region contour ─────────
    if is_missing or weld_contour is None:
        findings.append(VisualFinding(
            code=VisualFindingCode.ELLIPTICAL_INDENTATION,
            status=VisualFindingStatus.NOT_EVALUATED,
            name_en="Elliptical Indentation",
            name_tr="Eliptik İz / Asimetrik Kaynak",
            evidence="Cannot assess — no weld region contour detected.",
            source="cv2.fitEllipse on dark-region contour",
            limitations="Requires sufficient dark-region contour for ellipse fitting.",
            next_action_en="Re-inspect with higher resolution if elliptical impression is suspected.",
            next_action_tr="Eliptik iz şüphesi varsa daha yüksek çözünürlükle yeniden inceleyin.",
            internal_weld_integrity="Cannot assess.",
        ))
    elif len(weld_contour) < 5:
        findings.append(VisualFinding(
            code=VisualFindingCode.ELLIPTICAL_INDENTATION,
            status=VisualFindingStatus.NOT_EVALUATED,
            name_en="Elliptical Indentation",
            name_tr="Eliptik İz / Asimetrik Kaynak",
            evidence=f"Contour has only {len(weld_contour)} points — minimum 5 required for fitEllipse.",
            source="cv2.fitEllipse on dark-region contour",
            limitations="Insufficient contour points for ellipse fitting.",
            next_action_en="Re-inspect with higher resolution if elliptical impression is suspected.",
            next_action_tr="Eliptik iz şüphesi varsa daha yüksek çözünürlükle yeniden inceleyin.",
            internal_weld_integrity="Cannot assess.",
        ))
    else:
        try:
            (cx_e, cy_e), (ax1, ax2), _ = _cv2.fitEllipse(weld_contour)
            # fitEllipse returns RotatedRect (width, height); which axis is major
            # depends on rotation angle, so always take max/min explicitly.
            ax_major = max(float(ax1), float(ax2))
            ax_minor = max(min(float(ax1), float(ax2)), 1.0)
            aspect = ax_major / ax_minor
            ma, mi = ax_major, ax_minor
            is_elliptical = aspect > 1.4
            ell_bbox: Optional[Tuple[int, int, int, int]] = (
                (int(cx_e - ma / 2), int(cy_e - mi / 2), int(ma), int(mi))
                if is_elliptical else None
            )
            findings.append(VisualFinding(
                code=VisualFindingCode.ELLIPTICAL_INDENTATION,
                status=VisualFindingStatus.DETECTED if is_elliptical else VisualFindingStatus.NOT_DETECTED,
                name_en="Elliptical Indentation",
                name_tr="Eliptik İz / Asimetrik Kaynak",
                evidence=(
                    f"Dark-region contour fitted as ellipse: major={ma:.0f}px minor={mi:.0f}px "
                    f"aspect={aspect:.2f} ({'>' if is_elliptical else '<='} threshold 1.4)."
                ),
                source="cv2.fitEllipse on dark-region contour (CV deterministic)",
                limitations=(
                    "Ellipse fitting on small images may be unreliable. "
                    "Lighting gradients and noise can distort the fitted ellipse. "
                    "Treat as an indicator; confirm with higher-resolution re-inspection."
                ),
                bbox_pixels=ell_bbox,
                next_action_en="Inspect electrode face for wear or damage; check electrode holder alignment.",
                next_action_tr="Elektrod yüzeyini aşınma veya hasar için inceleyin; elektrod tutucu hizalamasını kontrol edin.",
                internal_weld_integrity="Elliptical impression may indicate asymmetric nugget. Cross-section recommended.",
            ))
        except Exception:
            findings.append(VisualFinding(
                code=VisualFindingCode.ELLIPTICAL_INDENTATION,
                status=VisualFindingStatus.NOT_EVALUATED,
                name_en="Elliptical Indentation",
                name_tr="Eliptik İz / Asimetrik Kaynak",
                evidence="fitEllipse raised an exception — contour may be degenerate.",
                source="cv2.fitEllipse on dark-region contour",
                limitations="Ellipse fitting failed; contour may be degenerate or too sparse.",
                next_action_en="Re-inspect with higher resolution if elliptical impression is suspected.",
                next_action_tr="Eliptik iz şüphesi varsa daha yüksek çözünürlükle yeniden inceleyin.",
                internal_weld_integrity="Cannot assess.",
            ))

    # ── 9. SURFACE_SPATTER — small anomalous regions at electrode periphery ───
    thresh_sp = _cv2.adaptiveThreshold(
        gray, 255, _cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        _cv2.THRESH_BINARY_INV, 51, 12,
    )
    ker_sp = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (3, 3))
    cleaned_sp = _cv2.morphologyEx(thresh_sp, _cv2.MORPH_OPEN, ker_sp, iterations=1)
    sp_cnts, _ = _cv2.findContours(cleaned_sp, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
    spatter_count = 0
    sp_min_dist = primary_r * 1.1
    sp_max_dist = primary_r * 2.5
    sp_min_area = 15
    sp_max_area = int(0.01 * w * h)
    for cnt in sp_cnts:
        area_px = float(_cv2.contourArea(cnt))
        if area_px < sp_min_area or area_px > sp_max_area:
            continue
        x, y, bw, bh = _cv2.boundingRect(cnt)
        cx_s, cy_s = x + bw // 2, y + bh // 2
        d = math.sqrt((cx_s - primary_cx) ** 2 + (cy_s - primary_cy) ** 2)
        if sp_min_dist <= d <= sp_max_dist:
            spatter_count += 1
    has_spatter = spatter_count >= 3
    findings.append(VisualFinding(
        code=VisualFindingCode.SURFACE_SPATTER,
        status=VisualFindingStatus.DETECTED if has_spatter else VisualFindingStatus.NOT_DETECTED,
        name_en="Surface Spatter / Flash",
        name_tr="Çapak / Kaynak Sıçraması",
        evidence=(
            f"{spatter_count} anomalous region(s) at electrode periphery "
            f"({'≥' if has_spatter else '<'} threshold 3)."
        ),
        source="Adaptive threshold + peripheral contour distance filter (CV deterministic)",
        limitations=(
            "Morphological analysis only — no semantic model loaded. "
            "Surface texture, contamination, or discoloration can produce false positives."
        ),
        next_action_en=(
            "Check process parameters (current, force, squeeze time); "
            "inspect electrode face for wear."
        ),
        next_action_tr=(
            "Kaynak prosesi parametrelerini kontrol edin (akım, kuvvet, sıkıştırma süresi); "
            "elektrod yüzeyini aşınma için inceleyin."
        ),
        internal_weld_integrity=(
            "Spatter indicates possible material ejection; nugget integrity not confirmed "
            "without destructive test."
        ),
    ))

    # ── 10. SUSPECTED_SURFACE_CRACK — elongated structures near electrode ─────
    # Use raw (un-opened) threshold: cracks are thin and morphological opening removes them.
    cr_cnts, _ = _cv2.findContours(thresh_sp, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
    crack_count = 0
    cr_max_area = int(0.02 * w * h)
    for cnt in cr_cnts:
        area_px = float(_cv2.contourArea(cnt))
        if area_px < 20 or area_px > cr_max_area or len(cnt) < 5:
            continue
        _, (ma_c, mi_c), _ = _cv2.minAreaRect(cnt)
        if mi_c < 1.0:
            continue
        aspect_c = max(ma_c, mi_c) / min(ma_c, mi_c)
        x, y, bw, bh = _cv2.boundingRect(cnt)
        cx_c, cy_c = x + bw // 2, y + bh // 2
        d = math.sqrt((cx_c - primary_cx) ** 2 + (cy_c - primary_cy) ** 2)
        if aspect_c > 3.5 and primary_r * 0.8 <= d <= primary_r * 2.2:
            crack_count += 1
    has_crack = crack_count >= 2
    findings.append(VisualFinding(
        code=VisualFindingCode.SUSPECTED_SURFACE_CRACK,
        status=VisualFindingStatus.DETECTED if has_crack else VisualFindingStatus.NOT_DETECTED,
        name_en="Suspected Surface Crack",
        name_tr="Şüpheli Yüzey Çatlağı",
        evidence=(
            f"{crack_count} elongated structure(s) (aspect >3.5) near electrode edge "
            f"({'≥' if has_crack else '<'} threshold 2)."
            if crack_count > 0 else
            "No elongated structures detected near electrode edge."
        ),
        source="Contour aspect-ratio filter at electrode periphery (CV deterministic)",
        limitations=(
            "SURFACE INDICATOR ONLY. Thin crack-like structures may be surface scratches, "
            "grain boundaries, or imaging artifacts. "
            "Metallographic cross-section or NDT required for confirmation. "
            "This indicator does NOT confirm an internal hot crack."
        ),
        next_action_en=(
            "Do not accept — escalate to qualified engineer; "
            "NDT or cross-section required for confirmation."
        ),
        next_action_tr=(
            "Kabul etmeyin — nitelikli mühendise iletin; "
            "onaylama için tahribatsız test veya kesit gereklidir."
        ),
        internal_weld_integrity="CAUTION: Surface crack indicators may propagate internally. NDT required.",
    ))

    # ── 11. SURFACE_DISCOLORATION — HSV saturation analysis ──────────────────
    hsv = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2HSV)
    s_ch = hsv[:, :, 1].astype(np.float32)
    v_ch = hsv[:, :, 2]
    mid_v = (v_ch > 50) & (v_ch < 220)
    s_mid = s_ch[mid_v]
    if len(s_mid) > 100:
        mean_sat = float(np.mean(s_mid))
        # High-saturation ratio uses S > 60/255 threshold to distinguish true heat-tint
        # colors (straw, blue oxide) from the slight warm-tone offset in normal gray metal.
        # Normal gray metal BGR offsets produce S ≈ 12–51; heat-tint straw ≈ 80.
        high_sat_ratio = float(np.mean(s_mid > 60.0))
    else:
        mean_sat = 0.0
        high_sat_ratio = 0.0
    is_discolored = high_sat_ratio > 0.03
    findings.append(VisualFinding(
        code=VisualFindingCode.SURFACE_DISCOLORATION,
        status=VisualFindingStatus.DETECTED if is_discolored else VisualFindingStatus.NOT_DETECTED,
        name_en="Surface Discoloration",
        name_tr="Yüzey Renk Değişimi / Isıl Renkleme",
        evidence=(
            f"Mid-brightness region: mean HSV saturation {mean_sat:.1f}/255, "
            f"strongly-saturated pixel ratio (S>60) {high_sat_ratio*100:.1f}%."
        ),
        source="HSV saturation analysis on mid-brightness pixels (CV deterministic)",
        limitations=(
            "Depends on camera color calibration and illumination color temperature. "
            "Grayscale or monochrome cameras cannot support this check. "
            "Thresholds calibrated on synthetic test images."
        ),
        next_action_en=(
            "Compare against oxide color reference chart; "
            "check heat input and shielding gas coverage."
        ),
        next_action_tr=(
            "Oksit renk referans tablosuyla karşılaştırın; "
            "ısı girdisini ve koruyucu gaz örtüsünü kontrol edin."
        ),
        internal_weld_integrity=(
            "Severe discoloration may indicate excessive heat input; "
            "HAZ properties may be affected."
        ),
    ))

    # ── 12. NORMAL_SURFACE — derived last (no other weld defect DETECTED) ─────
    _WELD_DEFECT_CODES = {
        VisualFindingCode.SURFACE_SPATTER,
        VisualFindingCode.SUSPECTED_SURFACE_CRACK,
        VisualFindingCode.SURFACE_DISCOLORATION,
        VisualFindingCode.ELECTRODE_MISALIGNMENT,
        VisualFindingCode.MISSING_WELD_INDICATION,
        VisualFindingCode.DOUBLE_SPOT_INDICATION,
        VisualFindingCode.MULTIPLE_WELD_POINTS,
        VisualFindingCode.ELLIPTICAL_INDENTATION,
    }
    _QUALITY_CODES = {
        VisualFindingCode.IMAGE_BLUR,
        VisualFindingCode.IMAGE_NOISE,
        VisualFindingCode.INSUFFICIENT_LIGHTING,
    }
    detected_codes = {f.code for f in findings if f.status == VisualFindingStatus.DETECTED}
    has_weld_issue = bool(detected_codes & _WELD_DEFECT_CODES)
    has_quality_issue = bool(detected_codes & _QUALITY_CODES)

    if is_missing:
        norm_status = VisualFindingStatus.NOT_EVALUATED
        norm_ev = "Cannot assess normal surface — no electrode/weld region detected."
    elif has_weld_issue or has_quality_issue:
        issues = sorted(c.value for c in detected_codes & (_WELD_DEFECT_CODES | _QUALITY_CODES))
        norm_status = VisualFindingStatus.NOT_DETECTED
        norm_ev = f"Issues detected: {', '.join(issues)}."
    else:
        norm_status = VisualFindingStatus.DETECTED
        norm_ev = (
            f"Electrode region detected at ({primary_cx},{primary_cy}) r≈{primary_r}px. "
            "No weld defect indicators and no image quality issues found."
        )
    findings.append(VisualFinding(
        code=VisualFindingCode.NORMAL_SURFACE,
        status=norm_status,
        name_en="Normal Surface",
        name_tr="Normal Yüzey",
        evidence=norm_ev,
        source="Composite: all 11 prior detectors (CV deterministic)",
        limitations=(
            "SURFACE OBSERVATION ONLY. 'Normal surface' does NOT confirm nugget acceptance. "
            "A visually normal weld may have an undersized nugget (incomplete fusion). "
            "Metallographic cross-section or UT required for nugget acceptance."
        ),
        next_action_en=(
            "Apply acceptance criteria to measurement results; "
            "conduct periodic destructive peel/chisel tests."
        ),
        next_action_tr=(
            "Ölçüm sonuçlarına kabul kriterlerini uygulayın; "
            "periyodik tahribatlı soyma/keski testi yapın."
        ),
        internal_weld_integrity=(
            "NOT CONFIRMED by surface analysis alone. "
            "Requires calibrated measurement or destructive test for nugget acceptance."
        ),
    ))

    return findings


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
