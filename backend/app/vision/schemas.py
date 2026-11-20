"""
Shared types for the SpotWeldPro vision subsystem.

Design principles enforced here:
- MeasurementSource labels every measurement: MEASURED, PREDICTED, or NOT_AVAILABLE.
  Never omit this field or assume a value is calibrated.
- InspectionStatus distinguishes OK / NOK / REVIEW / UNKNOWN / NOT_EVALUATED.
  NOT_EVALUATED is the default when no AcceptanceCriteria are supplied.
- AcceptanceCriteria must be versioned and attributed; thresholds are never hard-coded.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class InspectionStatus(str, Enum):
    OK = "OK"
    NOK = "NOK"
    REVIEW = "REVIEW"
    UNKNOWN = "UNKNOWN"
    NOT_EVALUATED = "NOT_EVALUATED"


class MeasurementSource(str, Enum):
    MEASURED = "MEASURED"           # derived from calibrated pixel measurement
    PREDICTED = "PREDICTED"         # inferred by a model; model_id must be supplied
    NOT_AVAILABLE = "NOT_AVAILABLE"  # calibration or detection not available


class ImageType(str, Enum):
    SURFACE = "SURFACE"               # electrode face or weld surface view
    CROSS_SECTION = "CROSS_SECTION"   # metallurgical cross-section
    UNKNOWN = "UNKNOWN"               # caller did not specify; detection may be inaccurate


class ROIConfig(BaseModel):
    x: int = Field(..., ge=0, description="Left edge of ROI in pixels")
    y: int = Field(..., ge=0, description="Top edge of ROI in pixels")
    width: int = Field(..., gt=0, description="Width of ROI in pixels")
    height: int = Field(..., gt=0, description="Height of ROI in pixels")


class CalibrationConfig(BaseModel):
    pixels_per_mm: float = Field(..., gt=0.0, description="Scale factor from calibration target")
    reference_method: str = Field(
        default="user_supplied",
        description="How calibration was established (e.g. 'ruler_target', 'known_electrode_diameter')",
    )


class ImageMetadata(BaseModel):
    width_px: int
    height_px: int
    channels: int
    format_detected: str
    file_size_bytes: int


class ElectrodeIndentation(BaseModel):
    diameter_mm: Optional[float] = Field(None, description="Measured diameter; None if uncalibrated")
    area_mm2: Optional[float] = Field(None, description="Approximate indentation area; None if uncalibrated")
    source: MeasurementSource
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Detection confidence 0–1")
    contour_quality: str = Field(default="not_assessed", description="'good', 'fair', 'poor', 'not_assessed'")
    notes: List[str] = Field(default_factory=list)


class DefectRegion(BaseModel):
    label: str = Field(description="Descriptive label, e.g. 'anomalous_region'")
    bbox_pixels: Tuple[int, int, int, int] = Field(description="x, y, width, height in pixels")
    area_mm2: Optional[float] = Field(None, description="Defect area; None if uncalibrated")
    source: MeasurementSource
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class NuggetMeasurement(BaseModel):
    diameter_mm: Optional[float] = Field(None, description="Nugget diameter; None if uncalibrated")
    area_mm2: Optional[float] = Field(None, description="Nugget cross-section area; None if uncalibrated")
    source: MeasurementSource
    notes: List[str] = Field(default_factory=list)


class AcceptanceCriteria(BaseModel):
    """
    Configurable acceptance rules.

    Thresholds are never hard-coded inside the engine. The caller supplies
    criteria derived from verified destructive testing or accepted standards,
    and must version and attribute them.
    """
    min_nugget_diameter_mm: Optional[float] = Field(None, gt=0.0)
    max_nugget_diameter_mm: Optional[float] = Field(None, gt=0.0)
    max_allowed_defects: Optional[int] = Field(None, ge=0)
    criteria_version: str = Field(default="unversioned")
    criteria_source: str = Field(
        default="user_supplied",
        description="Where the threshold values come from (standard, DOE, destructive test log, etc.)",
    )


class VisualFindingCode(str, Enum):
    """
    Canonical codes for the 12 visual defect mode categories assessed by the
    static inspection engine.  Codes are assessed from pixel data only —
    never inferred from filenames, manifest IDs, or synthetic metadata.
    """
    NORMAL_SURFACE          = "NORMAL_SURFACE"
    ELLIPTICAL_INDENTATION  = "ELLIPTICAL_INDENTATION"
    ELECTRODE_MISALIGNMENT  = "ELECTRODE_MISALIGNMENT"
    SURFACE_SPATTER         = "SURFACE_SPATTER"
    SUSPECTED_SURFACE_CRACK = "SUSPECTED_SURFACE_CRACK"
    SURFACE_DISCOLORATION   = "SURFACE_DISCOLORATION"
    MISSING_WELD_INDICATION = "MISSING_WELD_INDICATION"
    DOUBLE_SPOT_INDICATION  = "DOUBLE_SPOT_INDICATION"
    IMAGE_BLUR              = "IMAGE_BLUR"
    INSUFFICIENT_LIGHTING   = "INSUFFICIENT_LIGHTING"
    IMAGE_NOISE             = "IMAGE_NOISE"
    MULTIPLE_WELD_POINTS    = "MULTIPLE_WELD_POINTS"


class VisualFindingStatus(str, Enum):
    DETECTED      = "DETECTED"       # algorithm found evidence
    NOT_DETECTED  = "NOT_DETECTED"   # algorithm ran; evidence absent
    NOT_EVALUATED = "NOT_EVALUATED"  # algorithm cannot assess this mode


class VisualFinding(BaseModel):
    """
    Result of evaluating one visual defect mode code.

    Design rules:
    - evidence describes what the algorithm actually observed (never fabricated).
    - source names the exact algorithm used.
    - limitations states what the algorithm cannot guarantee.
    - confidence is omitted unless the algorithm produces a calibrated score.
    - bbox_pixels is included only when the finding is spatially localized.
    - internal_weld_integrity carries a separate note; surface findings do NOT
      imply internal nugget acceptance.
    """
    code: VisualFindingCode
    status: VisualFindingStatus
    name_en: str
    name_tr: str
    evidence: str = Field(description="What the algorithm observed (pixel-level facts only)")
    source: str = Field(description="Detection algorithm / method")
    limitations: str = Field(description="Limitations and caveats of this algorithm")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Only present when technically calibrated; omit otherwise",
    )
    bbox_pixels: Optional[Tuple[int, int, int, int]] = Field(
        None, description="(x, y, w, h) region bbox; None when not spatially localized",
    )
    next_action_en: str = Field(description="Recommended engineering next action (EN)")
    next_action_tr: str = Field(description="Önerilen mühendislik sonraki adımı (TR)")
    internal_weld_integrity: str = Field(
        description="Separate note on internal weld integrity (surface analysis cannot confirm)",
    )


class StaticInspectionResult(BaseModel):
    inspection_id: str
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    image_type: ImageType
    status: InspectionStatus
    image_metadata: ImageMetadata
    electrode_indentation: Optional[ElectrodeIndentation] = None
    defects: List[DefectRegion] = Field(default_factory=list)
    nugget: Optional[NuggetMeasurement] = None
    visual_findings: List[VisualFinding] = Field(
        default_factory=list,
        description="All 12 visual defect mode assessments (DETECTED/NOT_DETECTED/NOT_EVALUATED)",
    )
    preprocessing_notes: List[str] = Field(default_factory=list)
    review_notes: List[str] = Field(default_factory=list)
    calibration: Optional[CalibrationConfig] = None


# ── Live monitoring types (Phase 2) ───────────────────────────────────────────

class TemporalEventType(str, Enum):
    """
    Event types reported by deterministic frame-differencing analysis.

    MOTION_DETECTED and IDLE describe pixel-level activity only.
    They do NOT imply weld quality, weld presence, or any pass/fail judgment.
    WELD_CYCLE_BOUNDARY is a heuristic window boundary based on motion onset/end;
    it is not a confirmed weld event and must not be used as a quality gate.
    """
    MOTION_DETECTED = "MOTION_DETECTED"
    IDLE = "IDLE"
    WELD_CYCLE_BOUNDARY = "WELD_CYCLE_BOUNDARY"


class TemporalEvent(BaseModel):
    event_type: TemporalEventType
    timestamp_ms: float = Field(description="Milliseconds since POSIX epoch")
    frame_index: int
    magnitude: float = Field(description="Mean absolute pixel change 0–255")
    threshold: float = Field(description="Threshold used for MOTION/IDLE classification")
    is_above_threshold: bool
    source_id: str
    note: str = Field(
        default="MOTION_DETECTED does not imply weld presence or quality.",
        description="Reminder that this is a pixel-level observation, not a quality judgment",
    )


class WeldCycleState(str, Enum):
    IDLE = "IDLE"
    MOTION_ONSET = "MOTION_ONSET"
    ACTIVE_MOTION = "ACTIVE_MOTION"
    MOTION_END = "MOTION_END"


class WeldEventRecord(BaseModel):
    """
    A heuristically detected motion window that may correspond to a weld cycle.

    This record is based on frame-differencing magnitude only.
    Weld quality is NOT assessed here and must not be inferred from this record.
    Validation against destructive testing is required before this is used
    for any production-line quality decision.
    """
    record_id: str
    source_id: str
    start_timestamp_ms: float
    end_timestamp_ms: float
    duration_ms: float
    frame_count: int
    peak_magnitude: float
    mean_magnitude: float
    state: WeldCycleState
    note: str = Field(
        default=(
            "Weld cycle boundary is inferred from motion magnitude only. "
            "Weld quality is NOT assessed. Destructive test validation required."
        )
    )


class WorkerState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    RECONNECTING = "RECONNECTING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class LiveStreamMetrics(BaseModel):
    source_id: str
    fps_actual: Optional[float] = None
    fps_nominal: Optional[float] = None
    frames_total: int = 0
    frames_dropped: int = 0
    last_frame_age_ms: Optional[float] = None
    queue_depth: int = 0
    worker_state: WorkerState = WorkerState.NOT_STARTED
    error_message: Optional[str] = None


class LiveStreamStatus(BaseModel):
    state: str = Field(description="ACTIVE | IDLE | FRAMEWORK_ONLY | ERROR")
    source_id: Optional[str] = None
    metrics: Optional[LiveStreamMetrics] = None
    inference_model: Optional[str] = Field(
        default=None,
        description="Loaded inference model identifier. None until a validated model is registered.",
    )
    note: str = ""
