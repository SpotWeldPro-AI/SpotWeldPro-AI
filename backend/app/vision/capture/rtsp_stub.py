"""
RTSP capture adapter stub.

STATUS: INTERFACE ONLY — not production-validated.

This adapter wraps OpenCV's VideoCapture(rtsp_url) for IP cameras and
industrial vision systems that expose an RTSP stream.

Prerequisites before production deployment:
  - Confirm the camera's RTSP URL format and authentication scheme
  - Measure end-to-end latency for the target network topology
  - Test automatic reconnect under network interruptions
  - Confirm OpenCV's RTSP transport (TCP vs UDP) for the target environment
  - Measure actual sustained FPS; RTSP streams can silently drop frames
  - Industrial cameras may require proprietary SDKs for full control;
    this adapter is for ONVIF/generic RTSP only

Ring buffer and dropped-frame tracking are the caller's responsibility.
This adapter reports dropped_since_last=0; a wrapper should compute this
from frame_index gaps.
"""
from __future__ import annotations

import datetime
from typing import Iterator, Optional

from app.vision.capture.base import CaptureAdapter, CaptureError, FrameBundle

_RTSP_DEFAULT_TIMEOUT_MS = 5000


class RTSPAdapter(CaptureAdapter):
    """
    Generic RTSP stream capture via OpenCV VideoCapture.

    Not validated for production. Industrial cameras may need proprietary SDK adapters.
    """

    def __init__(
        self,
        rtsp_url: str,
        prefer_tcp: bool = True,
        open_timeout_ms: int = _RTSP_DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._url = rtsp_url
        self._prefer_tcp = prefer_tcp
        self._open_timeout_ms = open_timeout_ms
        self._cap = None
        self._frame_index: int = 0

    @property
    def source_id(self) -> str:
        # Redact credentials from the URL for logging safety
        return _redact_url(self._url)

    def open(self) -> None:
        try:
            import cv2
        except ImportError:
            raise CaptureError(
                "opencv-python-headless is required. "
                "Install with: pip install 'opencv-python-headless>=4.8'"
            )
        url = self._url
        if self._prefer_tcp and 'rtsp://' in url and '?' not in url:
            url = url + '?tcp'
        cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, float(self._open_timeout_ms))
        if not cap.isOpened():
            raise CaptureError(
                f"Could not open RTSP stream: {self.source_id}. "
                "Check the URL, credentials, network path, and camera state."
            )
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
            return None
        import cv2
        fps = self._cap.get(cv2.CAP_PROP_FPS)  # type: ignore[union-attr]
        return float(fps) if fps and fps > 0 else None


def _redact_url(url: str) -> str:
    """Remove password from rtsp://user:pass@host/path for safe logging."""
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        if p.password:
            netloc = f"{p.hostname}" if not p.port else f"{p.hostname}:{p.port}"
            if p.username:
                netloc = f"{p.username}:***@{netloc}"
            p = p._replace(netloc=netloc)
        return urlunparse(p)
    except Exception:
        return "rtsp://[redacted]"
