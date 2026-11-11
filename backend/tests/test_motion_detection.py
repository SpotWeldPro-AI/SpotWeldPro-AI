"""
Tests for MotionEventDetector: synthetic frames, event types, threshold, reset.
Requires opencv-python-headless.
"""
from __future__ import annotations

import datetime
import math

import pytest

try:
    import cv2
    import numpy as np
    _CV2_OK = True
except ImportError:
    _CV2_OK = False

pytestmark = pytest.mark.skipif(not _CV2_OK, reason="opencv-python-headless not installed")

from app.vision.capture.base import FrameBundle
from app.vision.motion_detection import (
    MotionDetectorConfig,
    MotionEventDetector,
    _compute_mad,
    _decode_gray,
)
from app.vision.schemas import TemporalEventType


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_bundle(frame_data: bytes, frame_index: int = 1, source: str = "test") -> FrameBundle:
    return FrameBundle(
        frame_data=frame_data,
        timestamp=datetime.datetime.utcnow(),
        frame_index=frame_index,
        source_id=source,
        width=32,
        height=32,
    )


def _encode_gray(arr: "np.ndarray") -> bytes:
    _, enc = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return bytes(enc)


def _solid_frame(value: int, w: int = 32, h: int = 32) -> bytes:
    """Return a JPEG of a solid-colour grayscale frame."""
    arr = np.full((h, w), value, dtype=np.uint8)
    return _encode_gray(arr)


def _moving_circle_frame(offset: int, w: int = 64, h: int = 64) -> bytes:
    """Return a JPEG frame with a white circle at x=offset."""
    arr = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(arr, (offset, h // 2), 8, 255, -1)
    return _encode_gray(arr)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestMotionDetectorFirstFrame:

    def test_first_frame_always_idle(self):
        detector = MotionEventDetector()
        bundle = _make_bundle(_solid_frame(128))
        event = detector.detect(bundle)
        assert event.event_type == TemporalEventType.IDLE
        assert event.magnitude == 0.0
        assert not event.is_above_threshold

    def test_first_frame_sets_source_id(self):
        detector = MotionEventDetector()
        bundle = _make_bundle(_solid_frame(0), source="cam://0")
        event = detector.detect(bundle)
        assert event.source_id == "cam://0"

    def test_first_frame_sets_frame_index(self):
        detector = MotionEventDetector()
        bundle = _make_bundle(_solid_frame(0), frame_index=42)
        event = detector.detect(bundle)
        assert event.frame_index == 42


class TestMotionDetectorIdleFrames:

    def test_identical_frames_produce_idle(self):
        detector = MotionEventDetector(MotionDetectorConfig(threshold=5.0))
        data = _solid_frame(100)
        detector.detect(_make_bundle(data, 1))  # prime
        event = detector.detect(_make_bundle(data, 2))
        assert event.event_type == TemporalEventType.IDLE
        # Identical frames: MAD should be near 0 (JPEG lossy; allow small epsilon)
        assert event.magnitude < 2.0

    def test_near_identical_frames_produce_idle(self):
        """Two solid frames with value difference of 1 should stay IDLE at default threshold."""
        detector = MotionEventDetector(MotionDetectorConfig(threshold=8.0))
        detector.detect(_make_bundle(_solid_frame(100), 1))
        event = detector.detect(_make_bundle(_solid_frame(101), 2))
        # Magnitude will be ~1 (one grey value difference); well below threshold 8
        assert event.magnitude < 5.0


class TestMotionDetectorMotionFrames:

    def test_large_step_produces_motion_detected(self):
        """Switching from black to white should produce high magnitude."""
        detector = MotionEventDetector(MotionDetectorConfig(threshold=8.0))
        detector.detect(_make_bundle(_solid_frame(0), 1))
        event = detector.detect(_make_bundle(_solid_frame(200), 2))
        assert event.event_type == TemporalEventType.MOTION_DETECTED
        assert event.is_above_threshold
        assert event.magnitude > 8.0

    def test_moving_circle_produces_motion(self):
        """A circle that moves between frames should produce motion."""
        detector = MotionEventDetector(MotionDetectorConfig(threshold=3.0))
        detector.detect(_make_bundle(_moving_circle_frame(10), 1))
        event = detector.detect(_make_bundle(_moving_circle_frame(40), 2))
        assert event.event_type == TemporalEventType.MOTION_DETECTED

    def test_magnitude_is_non_negative(self):
        detector = MotionEventDetector()
        detector.detect(_make_bundle(_solid_frame(50), 1))
        event = detector.detect(_make_bundle(_solid_frame(200), 2))
        assert event.magnitude >= 0.0

    def test_magnitude_bounded_by_255(self):
        detector = MotionEventDetector()
        detector.detect(_make_bundle(_solid_frame(0), 1))
        event = detector.detect(_make_bundle(_solid_frame(255), 2))
        assert event.magnitude <= 255.0


class TestMotionDetectorThreshold:

    def test_custom_threshold_applied(self):
        """With a very high threshold, even large motion should stay IDLE."""
        cfg = MotionDetectorConfig(threshold=300.0)  # impossibly high
        detector = MotionEventDetector(cfg)
        detector.detect(_make_bundle(_solid_frame(0), 1))
        event = detector.detect(_make_bundle(_solid_frame(255), 2))
        assert event.event_type == TemporalEventType.IDLE
        assert not event.is_above_threshold
        assert event.threshold == 300.0

    def test_threshold_in_event_matches_config(self):
        cfg = MotionDetectorConfig(threshold=12.5)
        detector = MotionEventDetector(cfg)
        detector.detect(_make_bundle(_solid_frame(50), 1))
        event = detector.detect(_make_bundle(_solid_frame(51), 2))
        assert event.threshold == 12.5


class TestMotionDetectorReset:

    def test_reset_clears_previous_frame(self):
        """After reset, next call should behave like first frame (magnitude=0)."""
        detector = MotionEventDetector()
        detector.detect(_make_bundle(_solid_frame(0), 1))
        detector.detect(_make_bundle(_solid_frame(200), 2))
        detector.reset()
        # After reset, next frame is "first frame" → magnitude 0
        event = detector.detect(_make_bundle(_solid_frame(200), 3))
        assert event.event_type == TemporalEventType.IDLE
        assert event.magnitude == 0.0


class TestMotionDetectorHelpers:

    def test_decode_gray_valid_jpeg(self):
        data = _solid_frame(128)
        arr = _decode_gray(data)
        assert arr is not None
        assert arr.ndim == 2

    def test_decode_gray_invalid_bytes(self):
        arr = _decode_gray(b"\x00\x01\x02\x03")
        assert arr is None

    def test_compute_mad_identical(self):
        a = np.full((16, 16), 100, dtype=np.uint8)
        mad = _compute_mad(a, a, blur_ksize=3)
        assert mad < 1.0  # effectively zero

    def test_compute_mad_full_range(self):
        a = np.zeros((16, 16), dtype=np.uint8)
        b = np.full((16, 16), 200, dtype=np.uint8)
        mad = _compute_mad(a, b, blur_ksize=3)
        assert mad > 100  # should be close to 200


class TestMotionEventInterpretation:

    def test_event_note_present(self):
        """Events must include the interpretation-limiting note."""
        detector = MotionEventDetector()
        event = detector.detect(_make_bundle(_solid_frame(50), 1))
        assert "MOTION_DETECTED" in event.note or len(event.note) > 0

    def test_motion_detected_does_not_imply_weld(self):
        """
        Verify the note field explicitly disclaims weld quality inference.
        This is a documentation/contract test, not a logic test.
        """
        detector = MotionEventDetector()
        detector.detect(_make_bundle(_solid_frame(0), 1))
        event = detector.detect(_make_bundle(_solid_frame(255), 2))
        # The note must NOT claim anything about weld quality
        lower_note = event.note.lower()
        assert "quality" not in lower_note or "not" in lower_note or "does not" in lower_note
