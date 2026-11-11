"""
Abstract capture adapter interface.

All capture sources — video files, webcams, RTSP streams, and industrial
camera SDKs — implement CaptureAdapter. The interface guarantees:
- Explicit open/close lifecycle with reconnect support
- Timestamped FrameBundle with dropped-frame tracking
- Non-blocking read_frame; callers control the loop
- No frame fabrication: if the source is unavailable, read_frame returns None

This interface does NOT claim any source is production-ready. Concrete adapters
must be validated with the actual target hardware before production deployment.
"""
from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass
class FrameBundle:
    """One timestamped frame from a capture source."""
    frame_data: bytes           # JPEG-encoded bytes
    timestamp: datetime.datetime
    frame_index: int
    source_id: str
    width: int
    height: int
    dropped_since_last: int = 0  # frames skipped since previous delivery


class CaptureError(Exception):
    """Raised when a capture source cannot be opened, read, or reconnected."""


class CaptureAdapter(ABC):
    """Abstract base for all capture sources."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this source (URI, device path, etc.)."""

    @abstractmethod
    def open(self) -> None:
        """
        Open or reconnect to the capture source.
        Raises CaptureError if the source cannot be reached.
        """

    @abstractmethod
    def close(self) -> None:
        """Release all resources. Safe to call even if not open."""

    @abstractmethod
    def is_open(self) -> bool:
        """True if the source is open and frames can be read."""

    @abstractmethod
    def read_frame(self) -> Optional[FrameBundle]:
        """
        Read one frame without blocking indefinitely.
        Returns None if no frame is available (end-of-file or temporary gap).
        Never fabricates frames.
        """

    @abstractmethod
    def frames(self, max_frames: Optional[int] = None) -> Iterator[FrameBundle]:
        """
        Iterate over frames. Opens the source, yields FrameBundles, closes on exit.
        Callers break the loop; the generator closes on break or exhaustion.
        """

    @abstractmethod
    def nominal_fps(self) -> Optional[float]:
        """Declared FPS of the source, or None if unknown or not applicable."""

    def reconnect(self, max_attempts: int = 3, delay_s: float = 1.0) -> None:
        """
        Close and reopen the source up to max_attempts times.
        Raises CaptureError if all attempts fail.
        """
        import time
        self.close()
        last_exc: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                self.open()
                return
            except CaptureError as exc:
                last_exc = exc
                if attempt < max_attempts:
                    time.sleep(delay_s)
        raise CaptureError(
            f"Reconnect failed after {max_attempts} attempts: {last_exc}"
        ) from last_exc
