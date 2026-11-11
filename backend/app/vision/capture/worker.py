"""
CaptureWorker — background thread that drives a CaptureAdapter.

Responsibilities:
- Read frames from any CaptureAdapter in a daemon thread.
- Put FrameBundle items into a bounded queue; drop frames when full (tracks count).
- Track metrics: fps_actual, frames_total, frames_dropped, last_frame_age_ms.
- Reconnect with exponential backoff on source failure (up to max_reconnect_attempts).
- Expose thread-safe stop() / is_running() / get_metrics() / get_latest_frame().

Thread safety: all mutable state is protected by a threading.Lock.
Queue: caller pops from q (get_nowait / get with timeout). Dropped frames are
recorded in metrics but never fabricated — the queue simply does not grow beyond maxsize.

Limitations (stated explicitly):
- Uses Python threads; GIL limits CPU-bound parallelism.
- OpenCV VideoCapture is not guaranteed thread-safe; this worker is the sole reader.
- Reconnect resets frame_index to 0 in the adapter; callers must handle gaps.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from app.vision.capture.base import CaptureAdapter, CaptureError, FrameBundle
from app.vision.schemas import LiveStreamMetrics, WorkerState

_log = logging.getLogger(__name__)

_DEFAULT_QUEUE_MAXSIZE = 60   # ~2 s at 30 fps; adjust per use case
_DEFAULT_RECONNECT_DELAY_S = 1.0
_DEFAULT_RECONNECT_BACKOFF = 2.0
_DEFAULT_MAX_RECONNECT_ATTEMPTS = 5


@dataclass
class _WorkerMetrics:
    frames_total: int = 0
    frames_dropped: int = 0
    fps_actual: Optional[float] = None
    last_frame_time: Optional[float] = None  # monotonic seconds
    fps_window_start: float = field(default_factory=time.monotonic)
    fps_window_count: int = 0
    worker_state: WorkerState = WorkerState.NOT_STARTED
    error_message: Optional[str] = None


class CaptureWorker:
    """
    Background-thread wrapper around a CaptureAdapter.

    Usage::

        adapter = FileVideoAdapter("clip.mp4", replay_fps=25.0)
        worker = CaptureWorker(adapter, queue_maxsize=60)
        worker.start()

        fb: FrameBundle = worker.get_frame(timeout=0.1)   # may return None
        metrics = worker.get_metrics()
        worker.stop()
    """

    def __init__(
        self,
        adapter: CaptureAdapter,
        queue_maxsize: int = _DEFAULT_QUEUE_MAXSIZE,
        reconnect_delay_s: float = _DEFAULT_RECONNECT_DELAY_S,
        reconnect_backoff: float = _DEFAULT_RECONNECT_BACKOFF,
        max_reconnect_attempts: int = _DEFAULT_MAX_RECONNECT_ATTEMPTS,
    ) -> None:
        self._adapter = adapter
        self._q: queue.Queue[FrameBundle] = queue.Queue(maxsize=queue_maxsize)
        self._reconnect_delay_s = reconnect_delay_s
        self._reconnect_backoff = reconnect_backoff
        self._max_reconnect_attempts = max_reconnect_attempts

        self._lock = threading.Lock()
        self._metrics = _WorkerMetrics()
        self._latest_frame: Optional[FrameBundle] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def source_id(self) -> str:
        return self._adapter.source_id

    def start(self) -> None:
        """Start the capture thread. Idempotent if already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._metrics = _WorkerMetrics()
            self._thread = threading.Thread(
                target=self._run,
                name=f"capture-worker-{self._adapter.source_id}",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        """Signal the worker to stop and wait for the thread to finish."""
        self._stop_event.set()
        with self._lock:
            t = self._thread
        if t is not None:
            t.join(timeout=timeout_s)
        self._adapter.close()
        with self._lock:
            self._metrics.worker_state = WorkerState.STOPPED

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def get_frame(self, timeout: float = 0.05) -> Optional[FrameBundle]:
        """
        Pop the oldest frame from the queue.
        Returns None if no frame is available within timeout seconds.
        """
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_frame_nowait(self) -> Optional[FrameBundle]:
        """Non-blocking frame pop. Returns None if queue is empty."""
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def get_latest_frame(self) -> Optional[FrameBundle]:
        """Return the most recently captured frame without consuming the queue."""
        with self._lock:
            return self._latest_frame

    def get_metrics(self) -> LiveStreamMetrics:
        """Thread-safe snapshot of current worker metrics."""
        with self._lock:
            m = self._metrics
            now = time.monotonic()
            last_age: Optional[float] = None
            if m.last_frame_time is not None:
                last_age = round((now - m.last_frame_time) * 1000.0, 1)
            return LiveStreamMetrics(
                source_id=self._adapter.source_id,
                fps_actual=m.fps_actual,
                fps_nominal=self._adapter.nominal_fps() if self._adapter.is_open() else None,
                frames_total=m.frames_total,
                frames_dropped=m.frames_dropped,
                last_frame_age_ms=last_age,
                queue_depth=self._q.qsize(),
                worker_state=m.worker_state,
                error_message=m.error_message,
            )

    def queue_size(self) -> int:
        return self._q.qsize()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _run(self) -> None:
        with self._lock:
            self._metrics.worker_state = WorkerState.RUNNING

        attempt = 0
        delay = self._reconnect_delay_s

        while not self._stop_event.is_set():
            try:
                if not self._adapter.is_open():
                    self._adapter.open()
                    with self._lock:
                        self._metrics.worker_state = WorkerState.RUNNING
                        self._metrics.error_message = None
                    attempt = 0
                    delay = self._reconnect_delay_s

                while not self._stop_event.is_set():
                    fb = self._adapter.read_frame()
                    if fb is None:
                        # End of file or temporary gap
                        break
                    self._deliver(fb)

                # Normal EOF (file adapter exhausted) → stop cleanly
                if not self._stop_event.is_set():
                    break

            except CaptureError as exc:
                attempt += 1
                with self._lock:
                    self._metrics.worker_state = WorkerState.RECONNECTING
                    self._metrics.error_message = str(exc)

                _log.warning(
                    "CaptureWorker %s: error on attempt %d/%d: %s",
                    self._adapter.source_id, attempt, self._max_reconnect_attempts, exc,
                )
                self._adapter.close()

                if attempt >= self._max_reconnect_attempts:
                    with self._lock:
                        self._metrics.worker_state = WorkerState.ERROR
                    _log.error(
                        "CaptureWorker %s: max reconnect attempts reached. Stopping.",
                        self._adapter.source_id,
                    )
                    break

                # Wait with backoff, but check stop_event frequently
                waited = 0.0
                while waited < delay and not self._stop_event.is_set():
                    time.sleep(0.1)
                    waited += 0.1
                delay = min(delay * self._reconnect_backoff, 30.0)

        self._adapter.close()
        with self._lock:
            if self._metrics.worker_state not in (WorkerState.ERROR,):
                self._metrics.worker_state = WorkerState.STOPPED

    def _deliver(self, fb: FrameBundle) -> None:
        """Put a frame into the queue; drop if full and increment counter."""
        with self._lock:
            self._metrics.frames_total += 1
            self._metrics.last_frame_time = time.monotonic()
            self._latest_frame = fb
            self._update_fps()

        try:
            self._q.put_nowait(fb)
        except queue.Full:
            with self._lock:
                self._metrics.frames_dropped += 1

    def _update_fps(self) -> None:
        """Compute rolling FPS over a 2-second window (called under lock)."""
        m = self._metrics
        m.fps_window_count += 1
        now = time.monotonic()
        elapsed = now - m.fps_window_start
        if elapsed >= 2.0:
            m.fps_actual = round(m.fps_window_count / elapsed, 2)
            m.fps_window_start = now
            m.fps_window_count = 0
