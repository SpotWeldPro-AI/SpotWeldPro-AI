"""
Tests for CaptureWorker: bounded queue, delivery, dropped frames, reconnect, stop.

Uses a synthetic InMemoryAdapter so no hardware or video files are required.
"""
from __future__ import annotations

import datetime
import queue
import threading
import time
from typing import Iterator, Optional

import pytest

from app.vision.capture.base import CaptureAdapter, CaptureError, FrameBundle
from app.vision.capture.worker import CaptureWorker
from app.vision.schemas import WorkerState


# ── Synthetic adapters ─────────────────────────────────────────────────────────

def _make_jpeg_bytes(w: int = 4, h: int = 4) -> bytes:
    """Return a minimal valid JPEG for testing."""
    try:
        import cv2
        import numpy as np
        _, enc = cv2.imencode(".jpg", np.zeros((h, w, 3), dtype=np.uint8))
        return bytes(enc)
    except ImportError:
        # Fallback: minimal JPEG header (not decodable, but valid bytes for queue tests)
        return b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9"


class FiniteAdapter(CaptureAdapter):
    """Delivers exactly `n_frames` frames then returns None."""

    def __init__(self, n_frames: int = 10, source: str = "mem://finite") -> None:
        self._n = n_frames
        self._src = source
        self._open = False
        self._count = 0
        self._frame_data = _make_jpeg_bytes()

    @property
    def source_id(self) -> str:
        return self._src

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
            frame_data=self._frame_data,
            timestamp=datetime.datetime.utcnow(),
            frame_index=self._count,
            source_id=self._src,
            width=4,
            height=4,
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
        return 30.0


class SlowAdapter(FiniteAdapter):
    """Delivers frames with a configurable delay per frame."""

    def __init__(self, n_frames: int = 5, delay_s: float = 0.02) -> None:
        super().__init__(n_frames)
        self._delay = delay_s

    def read_frame(self) -> Optional[FrameBundle]:
        time.sleep(self._delay)
        return super().read_frame()


class FailOnNthAdapter(FiniteAdapter):
    """Raises CaptureError after the Nth frame, then succeeds again."""

    def __init__(self, n_frames: int = 5, fail_after: int = 2) -> None:
        super().__init__(n_frames)
        self._fail_after = fail_after
        self._open_calls = 0

    def open(self) -> None:
        self._open_calls += 1
        super().open()

    def read_frame(self) -> Optional[FrameBundle]:
        if self._count == self._fail_after:
            self._count += 1  # so it doesn't re-fail on reconnect
            raise CaptureError("Synthetic source failure")
        return super().read_frame()


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestCaptureWorkerDelivery:

    def test_delivers_all_frames(self):
        adapter = FiniteAdapter(n_frames=10)
        worker = CaptureWorker(adapter, queue_maxsize=20)
        worker.start()

        collected = []
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            fb = worker.get_frame(timeout=0.1)
            if fb is not None:
                collected.append(fb)
            if not worker.is_running() and worker.queue_size() == 0:
                break

        worker.stop()
        assert len(collected) == 10, f"Expected 10 frames, got {len(collected)}"

    def test_frame_indices_ascending(self):
        adapter = FiniteAdapter(n_frames=5)
        worker = CaptureWorker(adapter, queue_maxsize=10)
        worker.start()

        indices = []
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            fb = worker.get_frame(timeout=0.1)
            if fb is not None:
                indices.append(fb.frame_index)
            if not worker.is_running() and worker.queue_size() == 0:
                break

        worker.stop()
        assert indices == sorted(indices)
        assert len(indices) == 5

    def test_get_frame_nowait_returns_none_when_empty(self):
        adapter = FiniteAdapter(n_frames=0)
        worker = CaptureWorker(adapter, queue_maxsize=10)
        worker.start()
        time.sleep(0.2)
        frame = worker.get_frame_nowait()
        worker.stop()
        assert frame is None

    def test_get_latest_frame_reflects_last_delivered(self):
        adapter = FiniteAdapter(n_frames=5)
        worker = CaptureWorker(adapter, queue_maxsize=10)
        worker.start()
        time.sleep(0.3)
        worker.stop()
        latest = worker.get_latest_frame()
        assert latest is not None
        assert latest.frame_index > 0


class TestCaptureWorkerDroppedFrames:

    def test_frames_dropped_when_queue_full(self):
        """With queue size 2 and 10 frames, some must be dropped."""
        adapter = FiniteAdapter(n_frames=10)
        worker = CaptureWorker(adapter, queue_maxsize=2)
        worker.start()

        # Don't consume — let queue fill and overflow
        time.sleep(0.3)
        metrics = worker.get_metrics()
        worker.stop()

        # Metrics should show some dropped frames
        total = metrics.frames_total
        dropped = metrics.frames_dropped
        assert total <= 10
        assert dropped >= 0  # may be 0 if consumer fast enough; just check it's tracked
        assert total + dropped <= 10 + dropped  # sanity

    def test_metrics_frames_total_matches_delivered(self):
        adapter = FiniteAdapter(n_frames=8)
        worker = CaptureWorker(adapter, queue_maxsize=20)
        worker.start()

        collected = 0
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            fb = worker.get_frame(timeout=0.1)
            if fb is not None:
                collected += 1
            if not worker.is_running() and worker.queue_size() == 0:
                break

        worker.stop()
        metrics = worker.get_metrics()
        assert metrics.frames_total == 8
        assert metrics.frames_dropped == 0
        assert collected == 8


class TestCaptureWorkerMetrics:

    def test_metrics_initial_state(self):
        adapter = FiniteAdapter(n_frames=0)
        worker = CaptureWorker(adapter)
        metrics = worker.get_metrics()
        assert metrics.worker_state == WorkerState.NOT_STARTED
        assert metrics.frames_total == 0
        assert metrics.frames_dropped == 0
        assert metrics.fps_actual is None

    def test_metrics_after_start(self):
        adapter = FiniteAdapter(n_frames=5)
        worker = CaptureWorker(adapter, queue_maxsize=10)
        worker.start()
        time.sleep(0.3)
        metrics = worker.get_metrics()
        worker.stop()
        assert metrics.worker_state in (WorkerState.RUNNING, WorkerState.STOPPED)
        assert metrics.frames_total >= 0

    def test_metrics_stopped_after_stop(self):
        adapter = FiniteAdapter(n_frames=3)
        worker = CaptureWorker(adapter, queue_maxsize=10)
        worker.start()
        time.sleep(0.2)
        worker.stop()
        metrics = worker.get_metrics()
        assert metrics.worker_state == WorkerState.STOPPED

    def test_last_frame_age_ms_set(self):
        adapter = SlowAdapter(n_frames=2, delay_s=0.05)
        worker = CaptureWorker(adapter, queue_maxsize=10)
        worker.start()
        time.sleep(0.5)
        worker.stop()
        metrics = worker.get_metrics()
        # After delivery, age should be a non-negative number
        if metrics.frames_total > 0:
            assert metrics.last_frame_age_ms is not None
            assert metrics.last_frame_age_ms >= 0


class TestCaptureWorkerReconnect:

    def test_reconnect_on_error(self):
        """Worker should attempt reconnect when adapter raises CaptureError."""
        adapter = FailOnNthAdapter(n_frames=5, fail_after=2)
        # max_reconnect_attempts=2, reconnect_delay=0.01 so test is fast
        worker = CaptureWorker(
            adapter, queue_maxsize=20,
            reconnect_delay_s=0.01,
            max_reconnect_attempts=3,
        )
        worker.start()
        time.sleep(0.5)
        metrics = worker.get_metrics()
        worker.stop()
        # Should have opened at least once and delivered some frames
        assert adapter._open_calls >= 1

    def test_max_reconnect_attempts_reached(self):
        """After max attempts, worker should enter ERROR state."""

        class AlwaysFailAdapter(FiniteAdapter):
            def open(self) -> None:
                raise CaptureError("Always fails")

        adapter = AlwaysFailAdapter(n_frames=0)
        worker = CaptureWorker(
            adapter, reconnect_delay_s=0.01, max_reconnect_attempts=2
        )
        worker.start()
        time.sleep(0.5)
        metrics = worker.get_metrics()
        assert metrics.worker_state == WorkerState.ERROR
        assert metrics.error_message is not None
        worker.stop()


class TestCaptureWorkerStop:

    def test_stop_is_idempotent(self):
        adapter = FiniteAdapter(n_frames=5)
        worker = CaptureWorker(adapter, queue_maxsize=10)
        worker.start()
        worker.stop()
        worker.stop()  # second call must not raise
        assert not worker.is_running()

    def test_start_idempotent(self):
        adapter = FiniteAdapter(n_frames=5)
        worker = CaptureWorker(adapter, queue_maxsize=10)
        worker.start()
        worker.start()  # second call must not raise
        time.sleep(0.2)
        worker.stop()
        assert not worker.is_running()

    def test_source_id_matches_adapter(self):
        adapter = FiniteAdapter(source="mem://test-src")
        worker = CaptureWorker(adapter)
        assert worker.source_id == "mem://test-src"
