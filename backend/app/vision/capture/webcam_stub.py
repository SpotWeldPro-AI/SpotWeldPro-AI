"""
Webcam capture adapter stub.

STATUS: INTERFACE ONLY — not production-validated.

This adapter wraps OpenCV's VideoCapture(device_index) for USB webcams.
It must be validated with the specific camera model, driver, and frame rate
before use in production. Standard 30-FPS USB webcams cannot detect
high-speed events (expulsion, spatter) which require dedicated hardware.

Prerequisites before production deployment:
  - Confirm device_index stability across reboots (udev rules or device alias)
  - Measure actual sustained FPS under load (not nominal FPS)
  - Measure end-to-end latency from physical event to delivered FrameBundle
  - Test disconnect/reconnect under repeated cable events
"""
from __future__ import annotations

import datetime
from typing import Iterator, Optional

from app.vision.capture.base import CaptureAdapter, CaptureError, FrameBundle


class WebcamAdapter(CaptureAdapter):
    """
    USB webcam capture via OpenCV VideoCapture(device_index).

    Not validated for production. Use only after hardware characterisation.
    """

    def __init__(self, device_index: int = 0, target_fps: Optional[float] = None) -> None:
        self._device_index = device_index
        self._target_fps = target_fps
        self._cap = None
        self._frame_index: int = 0

    @property
    def source_id(self) -> str:
        return f"webcam://device/{self._device_index}"

    def open(self) -> None:
        try:
            import cv2
        except ImportError:
            raise CaptureError(
                "opencv-python-headless is required. "
                "Install with: pip install 'opencv-python-headless>=4.8'"
            )
        cap = cv2.VideoCapture(self._device_index)
        if not cap.isOpened():
            raise CaptureError(
                f"Could not open webcam at device index {self._device_index}. "
                "Check that the camera is connected and not used by another process."
            )
        if self._target_fps is not None:
            cap.set(cv2.CAP_PROP_FPS, self._target_fps)
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
        import cv2
        ok, frame = self._cap.read()  # type: ignore[union-attr]
        if not ok or frame is None:
            return None
        _, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
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
            return self._target_fps
        import cv2
        fps = self._cap.get(cv2.CAP_PROP_FPS)  # type: ignore[union-attr]
        return float(fps) if fps and fps > 0 else self._target_fps
