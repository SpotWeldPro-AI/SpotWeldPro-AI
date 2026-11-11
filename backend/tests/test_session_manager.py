"""
Tests for LiveSessionManager: register/unregister, start/stop, WS slots, limits.
Uses the synthetic FiniteAdapter from test_capture_worker.
"""
from __future__ import annotations

import datetime
import time
from typing import Iterator, Optional

import pytest

from app.vision.capture.base import CaptureAdapter, CaptureError, FrameBundle
from app.vision.schemas import WorkerState
from app.vision.session_manager import LiveSessionManager, SessionManagerError


# ── Synthetic adapter ──────────────────────────────────────────────────────────

class DummyAdapter(CaptureAdapter):
    def __init__(self, source: str = "dummy://0", n: int = 3) -> None:
        self._src = source
        self._n = n
        self._open = False
        self._count = 0

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
            frame_data=b"\xff\xd8\xff\xd9",
            timestamp=datetime.datetime.utcnow(),
            frame_index=self._count,
            source_id=self._src,
            width=4, height=4,
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


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestSessionManagerRegistration:

    def test_register_and_list(self):
        mgr = LiveSessionManager(max_sources=4)
        mgr.register_source("s1", DummyAdapter("s1"))
        assert "s1" in mgr.list_sources()

    def test_register_duplicate_raises(self):
        mgr = LiveSessionManager()
        mgr.register_source("s1", DummyAdapter("s1"))
        with pytest.raises(SessionManagerError, match="already registered"):
            mgr.register_source("s1", DummyAdapter("s1"))

    def test_register_beyond_max_raises(self):
        mgr = LiveSessionManager(max_sources=2)
        mgr.register_source("s1", DummyAdapter("s1"))
        mgr.register_source("s2", DummyAdapter("s2"))
        with pytest.raises(SessionManagerError, match="Maximum"):
            mgr.register_source("s3", DummyAdapter("s3"))

    def test_unregister_removes_source(self):
        mgr = LiveSessionManager()
        mgr.register_source("s1", DummyAdapter("s1"))
        mgr.unregister_source("s1")
        assert "s1" not in mgr.list_sources()

    def test_unregister_nonexistent_is_safe(self):
        mgr = LiveSessionManager()
        mgr.unregister_source("does_not_exist")  # must not raise

    def test_source_exists(self):
        mgr = LiveSessionManager()
        mgr.register_source("s1", DummyAdapter("s1"))
        assert mgr.source_exists("s1")
        assert not mgr.source_exists("s_missing")


class TestSessionManagerStartStop:

    def test_start_and_stop_source(self):
        mgr = LiveSessionManager()
        mgr.register_source("s1", DummyAdapter("s1", n=10))
        mgr.start_source("s1")
        time.sleep(0.2)
        metrics = mgr.get_metrics("s1")
        mgr.stop_source("s1")
        assert metrics.worker_state in (WorkerState.RUNNING, WorkerState.STOPPED)

    def test_get_metrics_unknown_raises(self):
        mgr = LiveSessionManager()
        with pytest.raises(SessionManagerError):
            mgr.get_metrics("no_such_source")

    def test_get_latest_frame_before_start_returns_none(self):
        mgr = LiveSessionManager()
        mgr.register_source("s1", DummyAdapter("s1", n=5))
        frame = mgr.get_latest_frame("s1")
        assert frame is None

    def test_get_latest_frame_after_running(self):
        mgr = LiveSessionManager()
        mgr.register_source("s1", DummyAdapter("s1", n=5))
        mgr.start_source("s1")
        time.sleep(0.3)
        frame = mgr.get_latest_frame("s1")
        mgr.stop_source("s1")
        # DummyAdapter frames have minimal JPEG bytes; just check frame arrived
        assert frame is not None

    def test_stop_all(self):
        mgr = LiveSessionManager()
        mgr.register_source("s1", DummyAdapter("s1", n=100))
        mgr.register_source("s2", DummyAdapter("s2", n=100))
        mgr.start_source("s1")
        mgr.start_source("s2")
        mgr.stop_all()
        # Both workers should be stopped
        for sid in ["s1", "s2"]:
            m = mgr.get_metrics(sid)
            assert m.worker_state in (WorkerState.STOPPED, WorkerState.ERROR)


class TestSessionManagerWsSlots:

    def test_acquire_and_release(self):
        mgr = LiveSessionManager(max_ws_sessions=2)
        mgr.acquire_ws_slot()
        assert mgr.active_ws_count == 1
        mgr.acquire_ws_slot()
        assert mgr.active_ws_count == 2
        mgr.release_ws_slot()
        assert mgr.active_ws_count == 1
        mgr.release_ws_slot()
        assert mgr.active_ws_count == 0

    def test_acquire_beyond_limit_raises(self):
        mgr = LiveSessionManager(max_ws_sessions=1)
        mgr.acquire_ws_slot()
        with pytest.raises(SessionManagerError, match="Maximum concurrent"):
            mgr.acquire_ws_slot()
        mgr.release_ws_slot()

    def test_release_below_zero_clamped(self):
        mgr = LiveSessionManager()
        mgr.release_ws_slot()  # should not go negative
        assert mgr.active_ws_count == 0

    def test_ws_count_thread_safe(self):
        """Concurrent acquires and releases should not corrupt the counter."""
        import threading
        mgr = LiveSessionManager(max_ws_sessions=100)
        errors = []

        def acquire_release():
            try:
                mgr.acquire_ws_slot()
                time.sleep(0.01)
                mgr.release_ws_slot()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=acquire_release) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert mgr.active_ws_count == 0
