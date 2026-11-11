"""
Tests for the benchmark module: report structure, synthetic adapter, no-frame case.
"""
from __future__ import annotations

import datetime
from typing import Iterator, Optional

import pytest

try:
    import cv2
    import numpy as np
    _CV2_OK = True
except ImportError:
    _CV2_OK = False

pytestmark = pytest.mark.skipif(not _CV2_OK, reason="opencv-python-headless not installed")

from app.vision.capture.base import CaptureAdapter, FrameBundle
from app.vision.benchmark import BenchmarkReport, run_capture_benchmark


# ── Synthetic adapter for benchmarking ────────────────────────────────────────

def _make_jpeg(w=16, h=16) -> bytes:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    _, enc = cv2.imencode(".jpg", arr)
    return bytes(enc)


class SyntheticAdapter(CaptureAdapter):
    def __init__(self, n_frames: int = 50) -> None:
        self._n = n_frames
        self._open = False
        self._count = 0
        self._data = _make_jpeg()

    @property
    def source_id(self) -> str:
        return "synthetic://bench"

    def open(self) -> None:
        self._open = True
        self._count = 0

    def close(self) -> None:
        self._open = False

    def is_open(self) -> bool:
        return self._open

    def read_frame(self) -> Optional[FrameBundle]:
        if not self._open or self._count >= self._n:
            return None
        self._count += 1
        return FrameBundle(
            frame_data=self._data,
            timestamp=datetime.datetime.utcnow(),
            frame_index=self._count,
            source_id=self.source_id,
            width=16, height=16,
        )

    def frames(self, max_frames=None) -> Iterator[FrameBundle]:
        self.open()
        try:
            count = 0
            while (max_frames is None or count < max_frames):
                fb = self.read_frame()
                if fb is None:
                    break
                yield fb
                count += 1
        finally:
            self.close()

    def nominal_fps(self) -> Optional[float]:
        return None


class EmptyAdapter(SyntheticAdapter):
    def read_frame(self) -> Optional[FrameBundle]:
        return None


class TestBenchmarkReport:

    def test_report_delivered_frames_matches(self):
        adapter = SyntheticAdapter(n_frames=30)
        report = run_capture_benchmark(adapter, n_frames=30)
        assert report.n_frames_delivered == 30
        assert report.n_frames_dropped == 0

    def test_report_fps_positive(self):
        adapter = SyntheticAdapter(n_frames=50)
        report = run_capture_benchmark(adapter, n_frames=50)
        assert report.fps_sustained > 0

    def test_report_latency_non_negative(self):
        adapter = SyntheticAdapter(n_frames=20)
        report = run_capture_benchmark(adapter, n_frames=20)
        assert report.latency_ms_min >= 0
        assert report.latency_ms_max >= report.latency_ms_min
        assert report.latency_ms_mean >= 0
        assert report.latency_ms_p95 >= 0

    def test_report_elapsed_positive(self):
        adapter = SyntheticAdapter(n_frames=10)
        report = run_capture_benchmark(adapter, n_frames=10)
        assert report.elapsed_wall_s > 0

    def test_report_no_frames_delivers_zero(self):
        adapter = EmptyAdapter(n_frames=0)
        report = run_capture_benchmark(adapter, n_frames=10)
        assert report.n_frames_delivered == 0
        assert report.fps_sustained == 0.0
        assert len(report.warnings) > 0

    def test_report_summary_contains_fps(self):
        adapter = SyntheticAdapter(n_frames=10)
        report = run_capture_benchmark(adapter, n_frames=10)
        summary = report.summary()
        assert "FPS" in summary

    def test_report_to_dict_serializable(self):
        import json
        adapter = SyntheticAdapter(n_frames=10)
        report = run_capture_benchmark(adapter, n_frames=10)
        d = report.to_dict()
        # Must be JSON-serializable
        json.dumps(d)

    def test_report_hardware_info_populated(self):
        adapter = SyntheticAdapter(n_frames=5)
        report = run_capture_benchmark(adapter, n_frames=5)
        assert "platform" in report.hardware_info
        assert "python_version" in report.hardware_info
        assert "opencv_version" in report.hardware_info

    def test_report_test_description_set(self):
        adapter = SyntheticAdapter(n_frames=5)
        report = run_capture_benchmark(adapter, n_frames=5, description="my_test")
        assert report.test_description == "my_test"

    def test_report_p95_lte_max(self):
        adapter = SyntheticAdapter(n_frames=50)
        report = run_capture_benchmark(adapter, n_frames=50)
        assert report.latency_ms_p95 <= report.latency_ms_max + 0.001  # allow float rounding

    def test_report_fewer_frames_than_requested_recorded(self):
        """If adapter runs out before n_frames, delivered < requested."""
        adapter = SyntheticAdapter(n_frames=5)  # only 5 frames
        report = run_capture_benchmark(adapter, n_frames=20)
        assert report.n_frames_delivered == 5
        assert report.n_frames_requested == 20
        assert report.n_frames_dropped == 15
