"""
Deterministic motion/event detection for the live vision pipeline.

IMPORTANT — interpretation rules:
- MOTION_DETECTED means the frame-to-frame pixel difference exceeds the threshold.
  It does NOT imply a weld is happening, complete, or defective.
- IDLE means pixel change is below threshold.
- These are pixel-level observations only. Weld quality assessment requires
  a trained, validated model and confirmed ground truth from destructive testing.

Algorithm: mean absolute difference (MAD) of consecutive grayscale frames.
No model weights are used. Deterministic and hardware-agnostic.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import cv2 as _cv2
    import numpy as _np
    _CV2_AVAILABLE = True
except ImportError:
    _cv2 = None  # type: ignore[assignment]
    _np = None   # type: ignore[assignment]
    _CV2_AVAILABLE = False

from app.vision.capture.base import FrameBundle
from app.vision.schemas import TemporalEvent, TemporalEventType

_DEFAULT_THRESHOLD = 8.0   # MAD value above which motion is declared
_DEFAULT_BLUR_KSIZE = 5    # Gaussian blur before differencing (reduce noise)


@dataclass
class MotionDetectorConfig:
    threshold: float = _DEFAULT_THRESHOLD
    blur_ksize: int = _DEFAULT_BLUR_KSIZE
    min_frame_gap_ms: float = 0.0  # skip if frames arrive faster than this


class MotionDetectionError(RuntimeError):
    """Raised when detection cannot proceed (e.g. cv2 unavailable or corrupt frame)."""


class MotionEventDetector:
    """
    Frame-differencing motion detector.

    Usage::

        detector = MotionEventDetector()
        event = detector.detect(prev_bundle, curr_bundle)
        # event.event_type is MOTION_DETECTED or IDLE
    """

    def __init__(self, config: Optional[MotionDetectorConfig] = None) -> None:
        self._cfg = config or MotionDetectorConfig()
        self._last_gray: Optional[object] = None  # numpy array

    def reset(self) -> None:
        """Clear the previous-frame buffer (e.g. after a source reconnect)."""
        self._last_gray = None

    def detect(self, bundle: FrameBundle) -> TemporalEvent:
        """
        Compute motion magnitude for `bundle` relative to the previous frame.

        On the first call (no prior frame), magnitude is 0.0 and event_type is IDLE.
        Never fabricates or invents motion; returns real pixel-difference only.
        """
        if not _CV2_AVAILABLE:
            raise MotionDetectionError(
                "opencv-python-headless is required for motion detection. "
                "Install with: pip install 'opencv-python-headless>=4.8'"
            )

        gray = _decode_gray(bundle.frame_data)
        if gray is None:
            raise MotionDetectionError(
                f"Could not decode frame {bundle.frame_index} from {bundle.source_id}."
            )

        if self._last_gray is None:
            self._last_gray = gray
            return TemporalEvent(
                event_type=TemporalEventType.IDLE,
                timestamp_ms=bundle.timestamp.timestamp() * 1000.0,
                frame_index=bundle.frame_index,
                magnitude=0.0,
                threshold=self._cfg.threshold,
                is_above_threshold=False,
                source_id=bundle.source_id,
            )

        magnitude = _compute_mad(self._last_gray, gray, self._cfg.blur_ksize)
        self._last_gray = gray

        above = magnitude > self._cfg.threshold
        return TemporalEvent(
            event_type=TemporalEventType.MOTION_DETECTED if above else TemporalEventType.IDLE,
            timestamp_ms=bundle.timestamp.timestamp() * 1000.0,
            frame_index=bundle.frame_index,
            magnitude=round(float(magnitude), 4),
            threshold=self._cfg.threshold,
            is_above_threshold=above,
            source_id=bundle.source_id,
        )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _decode_gray(jpeg_bytes: bytes):
    """Decode JPEG bytes to a grayscale numpy array. Returns None on failure."""
    try:
        buf = _np.frombuffer(jpeg_bytes, dtype=_np.uint8)
        img = _cv2.imdecode(buf, _cv2.IMREAD_GRAYSCALE)
        return img
    except Exception:
        return None


def _compute_mad(prev, curr, blur_ksize: int) -> float:
    """
    Mean Absolute Difference between two grayscale frames.
    Both are blurred to reduce sensor noise before differencing.
    """
    k = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
    p = _cv2.GaussianBlur(prev, (k, k), 0)
    c = _cv2.GaussianBlur(curr, (k, k), 0)
    diff = _cv2.absdiff(p, c)
    return float(_np.mean(diff))
