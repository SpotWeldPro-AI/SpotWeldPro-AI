"""
File-based capture adapter: reads video frames from a local file.

Requires opencv-python-headless>=4.8.
Suitable for offline testing and evidence clip review.
Not intended for real-time production streaming.

NOTE: 30-FPS cameras cannot capture high-speed expulsion events (>1000 fps).
If expulsion detection is required, use a high-speed camera adapter instead.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Iterator, Optional

from app.vision.capture.base import CaptureAdapter, CaptureError, FrameBundle


class FileVideoAdapter(CaptureAdapter):
    """
    Read frames from a video file (MP4, AVI, MKV, etc.).

    replay_fps: if set, delivery is throttled to simulate a camera at that FPS.
    This enables deterministic replay for testing and benchmarking without
    actual hardware. When replay_fps is None the adapter reads as fast as
    possible (CPU-bound; use only in tests).
    """

    def __init__(self, file_path: str, replay_fps: Optional[float] = None) -> None:
        self._path = str(file_path)
        self._replay_fps = replay_fps  # None = max speed
        self._cap = None
        self._frame_index: int = 0
        self._last_frame_time: Optional[float] = None

    @property
    def source_id(self) -> str:
        return f"file://{self._path}"

    def open(self) -> None:
        try:
            import cv2
        except ImportError:
            raise CaptureError(
                "opencv-python-headless is required for video file capture. "
                "Install with: pip install 'opencv-python-headless>=4.8'"
            )
        if not Path(self._path).exists():
            raise CaptureError(f"Video file not found: {self._path}")

        cap = cv2.VideoCapture(self._path)
        if not cap.isOpened():
            raise CaptureError(f"OpenCV could not open video file: {self._path}")
        self._cap = cap
        self._frame_index = 0

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read_frame(self) -> Optional[FrameBundle]:
        if not self.is_open():
            return None
        import time
        import cv2

        # Throttle delivery to replay_fps if configured
        if self._replay_fps is not None and self._replay_fps > 0:
            now = time.monotonic()
            if self._last_frame_time is not None:
                elapsed = now - self._last_frame_time
                frame_period = 1.0 / self._replay_fps
                if elapsed < frame_period:
                    time.sleep(frame_period - elapsed)
            self._last_frame_time = time.monotonic()

        ok, frame = self._cap.read()  # type: ignore[union-attr]
        if not ok or frame is None:
            return None
        _, encoded = cv2.imencode(
            '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60]
        )
        self._frame_index += 1
        return FrameBundle(
            frame_data=bytes(encoded),
            timestamp=datetime.datetime.utcnow(),
            frame_index=self._frame_index,
            source_id=self.source_id,
            width=frame.shape[1],
            height=frame.shape[0],
        )

    def frames(self, max_frames: Optional[int] = None) -> Iterator[FrameBundle]:
        self.open()
        try:
            count = 0
            while max_frames is None or count < max_frames:
                fb = self.read_frame()
                if fb is None:
                    break
                yield fb
                count += 1
        finally:
            self.close()

    def nominal_fps(self) -> Optional[float]:
        if not self.is_open():
            return None
        import cv2
        fps = self._cap.get(cv2.CAP_PROP_FPS)  # type: ignore[union-attr]
        return float(fps) if fps and fps > 0 else None
