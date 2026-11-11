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


class StaticInspectionResult(BaseModel):
    inspection_id: str
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    image_type: ImageType
    status: InspectionStatus
    image_metadata: ImageMetadata
    electrode_indentation: Optional[ElectrodeIndentation] = None
    defects: List[DefectRegion] = Field(default_factory=list)
    nugget: Optional[NuggetMeasurement] = None
    preprocessing_notes: List[str] = Field(default_factory=list)
    review_notes: List[str] = Field(default_factory=list)
    calibration: Optional[CalibrationConfig] = None
