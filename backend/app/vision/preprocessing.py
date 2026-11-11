"""
Image preprocessing pipeline for SpotWeldPro static inspection.

Responsibilities:
- Format and size validation
- OpenCV decoding and grayscale detection
- ROI extraction (clamped to image bounds)
- Optional CLAHE contrast enhancement
- Calibration plumbing

Requires opencv-python-headless>=4.8.
If OpenCV is absent, ImagePreprocessor.__init__ raises RuntimeError with install guidance.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

try:
    import cv2 as _cv2
    _CV2_AVAILABLE = True
except ImportError:
    _cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False

from app.vision.schemas import CalibrationConfig, ImageMetadata, ROIConfig

_MAX_IMAGE_BYTES = 50 * 1024 * 1024
_MIN_DIMENSION = 32
_MAX_DIMENSION = 16384


class PreprocessingError(ValueError):
    """Raised for invalid images or impossible ROI configurations."""


@dataclass
class PreprocessedImage:
    """OpenCV BGR array plus metadata accumulated during preprocessing."""
    array: np.ndarray           # dtype uint8, shape (H, W, 3) BGR
    width: int
    height: int
    channels: int
    metadata: ImageMetadata
    notes: list[str] = field(default_factory=list)
    roi_applied: bool = False
    clahe_applied: bool = False


class ImagePreprocessor:
    """
    Load, validate, and preprocess weld inspection images.

    Raises RuntimeError on construction if OpenCV is not installed.
    """

    def __init__(self, max_bytes: int = _MAX_IMAGE_BYTES) -> None:
        if not _CV2_AVAILABLE:
            raise RuntimeError(
                "opencv-python-headless is required for image preprocessing. "
                "Install with: pip install 'opencv-python-headless>=4.8'"
            )
        self._max_bytes = max_bytes

    def load_and_validate(
        self,
        raw_bytes: bytes,
        filename: str = "",
    ) -> PreprocessedImage:
        """
        Decode and validate raw image bytes.

        Raises PreprocessingError for empty input, images that cannot be decoded,
        images below the minimum dimension, and files over the size limit.
        """
        notes: list[str] = []

        if len(raw_bytes) == 0:
            raise PreprocessingError("Image file is empty.")
        if len(raw_bytes) > self._max_bytes:
            raise PreprocessingError(
                f"Image exceeds maximum allowed size of "
                f"{self._max_bytes // (1024 * 1024)} MB."
            )

        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        img = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
        if img is None:
            raise PreprocessingError(
                "Could not decode image. "
                "Supported formats: JPEG, PNG, TIFF, BMP, WebP."
            )

        h, w = img.shape[:2]
        channels = img.shape[2] if img.ndim == 3 else 1

        if w < _MIN_DIMENSION or h < _MIN_DIMENSION:
            raise PreprocessingError(
                f"Image is too small: {w}×{h} px. "
                f"Minimum is {_MIN_DIMENSION}×{_MIN_DIMENSION} px."
            )
        if w > _MAX_DIMENSION or h > _MAX_DIMENSION:
            notes.append(
                f"Image dimensions {w}×{h} px exceed the recommended maximum of "
                f"{_MAX_DIMENSION}×{_MAX_DIMENSION} px; processing may be slow."
            )

        if _is_effectively_grayscale(img):
            notes.append(
                "Image appears to be grayscale; some color-based detection is unavailable."
            )

        fmt = _detect_format(raw_bytes, filename)

        metadata = ImageMetadata(
            width_px=w,
            height_px=h,
            channels=channels,
            format_detected=fmt,
            file_size_bytes=len(raw_bytes),
        )
        return PreprocessedImage(
            array=img,
            width=w,
            height=h,
            channels=channels,
            metadata=metadata,
            notes=notes,
        )

    def apply_roi(self, img: PreprocessedImage, roi: ROIConfig) -> PreprocessedImage:
        """
        Crop the image to the specified ROI.

        Coordinates are clamped to the image boundary. Raises PreprocessingError
        if the resulting crop area is zero (ROI entirely outside the image).
        """
        x1 = max(0, roi.x)
        y1 = max(0, roi.y)
        x2 = min(img.width, roi.x + roi.width)
        y2 = min(img.height, roi.y + roi.height)

        if x2 <= x1 or y2 <= y1:
            raise PreprocessingError(
                f"ROI ({roi.x},{roi.y})+({roi.width}×{roi.height}) is "
                f"entirely outside image bounds ({img.width}×{img.height})."
            )

        cropped = img.array[y1:y2, x1:x2]
        new_h, new_w = cropped.shape[:2]
        notes = img.notes + [f"ROI applied: ({x1},{y1})–({x2},{y2})."]

        return PreprocessedImage(
            array=cropped,
            width=new_w,
            height=new_h,
            channels=img.channels,
            metadata=ImageMetadata(
                width_px=new_w,
                height_px=new_h,
                channels=img.channels,
                format_detected=img.metadata.format_detected,
                file_size_bytes=img.metadata.file_size_bytes,
            ),
            notes=notes,
            roi_applied=True,
            clahe_applied=img.clahe_applied,
        )

    def apply_clahe(
        self,
        img: PreprocessedImage,
        clip_limit: float = 2.0,
        tile_size: int = 8,
    ) -> PreprocessedImage:
        """
        Apply CLAHE (Contrast Limited Adaptive Histogram Equalization).

        Returns a new PreprocessedImage with enhanced contrast. The enhanced
        image is converted back to BGR so downstream code handles a single format.
        """
        gray = _cv2.cvtColor(img.array, _cv2.COLOR_BGR2GRAY)
        clahe = _cv2.createCLAHE(
            clipLimit=clip_limit,
            tileGridSize=(tile_size, tile_size),
        )
        enhanced_gray = clahe.apply(gray)
        enhanced_bgr = _cv2.cvtColor(enhanced_gray, _cv2.COLOR_GRAY2BGR)
        notes = img.notes + [
            f"CLAHE enhancement applied (clipLimit={clip_limit}, tile={tile_size}×{tile_size})."
        ]
        return PreprocessedImage(
            array=enhanced_bgr,
            width=img.width,
            height=img.height,
            channels=img.channels,
            metadata=img.metadata,
            notes=notes,
            roi_applied=img.roi_applied,
            clahe_applied=True,
        )


def _is_effectively_grayscale(bgr: np.ndarray, tolerance: int = 5) -> bool:
    """True if the image has near-zero color saturation (R ≈ G ≈ B)."""
    if bgr.ndim < 3 or bgr.shape[2] < 3:
        return True
    b = bgr[:, :, 0].astype(np.int32)
    g = bgr[:, :, 1].astype(np.int32)
    r = bgr[:, :, 2].astype(np.int32)
    mean_diff = float(np.mean(np.abs(r - g) + np.abs(g - b)))
    return mean_diff < tolerance


def _detect_format(raw_bytes: bytes, filename: str) -> str:
    """Format detection from magic bytes, falling back to file extension."""
    if len(raw_bytes) >= 3 and raw_bytes[:3] == b'\xff\xd8\xff':
        return "JPEG"
    if len(raw_bytes) >= 8 and raw_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "PNG"
    if len(raw_bytes) >= 4 and raw_bytes[:4] in (b'II*\x00', b'MM\x00*'):
        return "TIFF"
    if len(raw_bytes) >= 2 and raw_bytes[:2] == b'BM':
        return "BMP"
    if len(raw_bytes) >= 12 and raw_bytes[:4] == b'RIFF' and raw_bytes[8:12] == b'WEBP':
        return "WebP"
    if '.' in filename:
        return filename.rsplit('.', 1)[-1].upper()
    return "UNKNOWN"
