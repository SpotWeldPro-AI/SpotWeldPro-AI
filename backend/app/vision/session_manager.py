"""
LiveSessionManager — process-level registry of CaptureWorker instances.

One singleton (get_session_manager()) serves the whole FastAPI process.
Resource limits are enforced at registration and WS connection time.

Limits (all configurable via constructor):
  max_sources:     maximum number of registered capture sources
  max_ws_sessions: maximum concurrent WebSocket client connections

Thread safety: all mutations are protected by a threading.Lock.

IMPORTANT: No automatic PLC actuation is performed by this module.
No weld quality inferences are stored here; only frame delivery metrics.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, Optional

from app.vision.capture.base import CaptureAdapter, FrameBundle
from app.vision.capture.worker import CaptureWorker
from app.vision.schemas import LiveStreamMetrics, WorkerState

_log = logging.getLogger(__name__)

_MAX_SOURCES = 8
_MAX_WS_SESSIONS = 8
_QUEUE_MAXSIZE = 60


class SessionManagerError(RuntimeError):
    """Raised when a resource limit or state invariant is violated."""


class LiveSessionManager:
    """
    Registry and lifecycle manager for CaptureWorker instances.

    Usage::

        mgr = get_session_manager()
        mgr.register_source("cam0", FileVideoAdapter("clip.mp4"))
        mgr.start_source("cam0")
        metrics = mgr.get_metrics("cam0")
        frame = mgr.get_latest_frame("cam0")
        mgr.stop_source("cam0")
    """

    def __init__(
        self,
        max_sources: int = _MAX_SOURCES,
        max_ws_sessions: int = _MAX_WS_SESSIONS,
        queue_maxsize: int = _QUEUE_MAXSIZE,
    ) -> None:
        self._max_sources = max_sources
        self._max_ws_sessions = max_ws_sessions
        self._queue_maxsize = queue_maxsize
        self._lock = threading.Lock()
        self._workers: Dict[str, CaptureWorker] = {}
        self._ws_count: int = 0

    # ── Source lifecycle ───────────────────────────────────────────────────────

    def register_source(self, source_id: str, adapter: CaptureAdapter) -> None:
        with self._lock:
            if source_id in self._workers:
                raise SessionManagerError(
                    f"Source '{source_id}' is already registered. "
                    "Call unregister_source() first."
                )
            if len(self._workers) >= self._max_sources:
                raise SessionManagerError(
                    f"Maximum number of sources ({self._max_sources}) already registered."
                )
            self._workers[source_id] = CaptureWorker(
                adapter, queue_maxsize=self._queue_maxsize
            )
            _log.info("LiveSessionManager: registered source %r", source_id)

    def unregister_source(self, source_id: str) -> None:
        with self._lock:
            worker = self._workers.pop(source_id, None)
        if worker is not None:
            worker.stop()
            _log.info("LiveSessionManager: unregistered source %r", source_id)

    def start_source(self, source_id: str) -> None:
        worker = self._get_worker(source_id)
        worker.start()

    def stop_source(self, source_id: str) -> None:
        worker = self._get_worker(source_id)
        worker.stop()

    def list_sources(self) -> list[str]:
        with self._lock:
            return list(self._workers.keys())

    def get_metrics(self, source_id: str) -> LiveStreamMetrics:
        return self._get_worker(source_id).get_metrics()

    def get_latest_frame(self, source_id: str) -> Optional[FrameBundle]:
        return self._get_worker(source_id).get_latest_frame()

    def get_frame(self, source_id: str, timeout: float = 0.05) -> Optional[FrameBundle]:
        return self._get_worker(source_id).get_frame(timeout=timeout)

    def source_exists(self, source_id: str) -> bool:
        with self._lock:
            return source_id in self._workers

    # ── WS connection accounting ───────────────────────────────────────────────

    def acquire_ws_slot(self) -> None:
        with self._lock:
            if self._ws_count >= self._max_ws_sessions:
                raise SessionManagerError(
                    f"Maximum concurrent WebSocket sessions ({self._max_ws_sessions}) reached. "
                    "Try again when another client disconnects."
                )
            self._ws_count += 1
            _log.debug("LiveSessionManager: WS slot acquired (%d/%d)", self._ws_count, self._max_ws_sessions)

    def release_ws_slot(self) -> None:
        with self._lock:
            self._ws_count = max(0, self._ws_count - 1)
            _log.debug("LiveSessionManager: WS slot released (%d/%d)", self._ws_count, self._max_ws_sessions)

    @property
    def active_ws_count(self) -> int:
        with self._lock:
            return self._ws_count

    # ── Teardown ───────────────────────────────────────────────────────────────

    def stop_all(self) -> None:
        with self._lock:
            keys = list(self._workers.keys())
        for key in keys:
            try:
                self._workers[key].stop()
            except Exception as exc:
                _log.warning("Error stopping worker %r: %s", key, exc)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _get_worker(self, source_id: str) -> CaptureWorker:
        with self._lock:
            worker = self._workers.get(source_id)
        if worker is None:
            raise SessionManagerError(f"Source '{source_id}' is not registered.")
        return worker


# ── Process-level singleton ────────────────────────────────────────────────────

_singleton: Optional[LiveSessionManager] = None
_singleton_lock = threading.Lock()


def get_session_manager() -> LiveSessionManager:
    """Return the process-level LiveSessionManager singleton."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = LiveSessionManager()
    return _singleton
