"""
Benchmark utilities for the vision pipeline.

Measures sustained FPS, per-frame inference latency, and resource usage.
Reports ACTUAL measured values only — no synthetic or assumed numbers.

Usage::

    report = run_capture_benchmark(adapter, n_frames=100)
    print(report.summary())

IMPORTANT: Results are hardware- and load-specific. Report the CPU model,
clock speed, OS, Python version, and OpenCV version alongside any numbers.
Do not publish results as general performance claims.
"""
from __future__ import annotations

import platform
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import cv2 as _cv2
    _CV2_VERSION = _cv2.__version__
except ImportError:
    _cv2 = None  # type: ignore[assignment]
    _CV2_VERSION = "not installed"

try:
    import numpy as _np
    _NP_VERSION = _np.__version__
except ImportError:
    _np = None  # type: ignore[assignment]
    _NP_VERSION = "not installed"

try:
    import psutil as _psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_AVAILABLE = False


@dataclass
class FrameLatencySample:
    frame_index: int
    decode_ms: float        # time to decode JPEG from bytes to numpy array
    analysis_ms: float      # time for static analysis (0 if not benchmarked)
    total_ms: float


@dataclass
class BenchmarkReport:
    test_description: str
    n_frames_requested: int
    n_frames_delivered: int
    n_frames_dropped: int
    elapsed_wall_s: float
    fps_sustained: float
    latency_ms_min: float
    latency_ms_max: float
    latency_ms_mean: float
    latency_ms_p95: float
    cpu_percent_mean: Optional[float]   # None if psutil unavailable
    rss_mb_start: Optional[float]
    rss_mb_end: Optional[float]
    hardware_info: dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"=== Benchmark: {self.test_description} ===",
            f"  Frames requested : {self.n_frames_requested}",
            f"  Frames delivered : {self.n_frames_delivered}",
            f"  Frames dropped   : {self.n_frames_dropped}",
            f"  Wall time        : {self.elapsed_wall_s:.3f} s",
            f"  FPS (sustained)  : {self.fps_sustained:.2f}",
            f"  Latency min/mean/p95/max (ms): "
            f"{self.latency_ms_min:.2f} / {self.latency_ms_mean:.2f} / "
            f"{self.latency_ms_p95:.2f} / {self.latency_ms_max:.2f}",
        ]
        if self.cpu_percent_mean is not None:
            lines.append(f"  CPU mean         : {self.cpu_percent_mean:.1f}%")
        if self.rss_mb_start is not None:
            lines.append(
                f"  RSS start/end (MB): {self.rss_mb_start:.1f} / {self.rss_mb_end:.1f}"
            )
        for hw_key, hw_val in self.hardware_info.items():
            lines.append(f"  {hw_key}: {hw_val}")
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "test_description": self.test_description,
            "n_frames_requested": self.n_frames_requested,
            "n_frames_delivered": self.n_frames_delivered,
            "n_frames_dropped": self.n_frames_dropped,
            "elapsed_wall_s": self.elapsed_wall_s,
            "fps_sustained": self.fps_sustained,
            "latency_ms_min": self.latency_ms_min,
            "latency_ms_max": self.latency_ms_max,
            "latency_ms_mean": self.latency_ms_mean,
            "latency_ms_p95": self.latency_ms_p95,
            "cpu_percent_mean": self.cpu_percent_mean,
            "rss_mb_start": self.rss_mb_start,
            "rss_mb_end": self.rss_mb_end,
            "hardware_info": self.hardware_info,
            "warnings": self.warnings,
        }


def _hardware_info() -> dict:
    info = {
        "platform": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "python_version": sys.version,
        "opencv_version": _CV2_VERSION,
        "numpy_version": _NP_VERSION,
        "psutil_available": _PSUTIL_AVAILABLE,
    }
    if _PSUTIL_AVAILABLE:
        info["cpu_physical_cores"] = _psutil.cpu_count(logical=False)
        info["cpu_logical_cores"] = _psutil.cpu_count(logical=True)
        vm = _psutil.virtual_memory()
        info["ram_total_mb"] = round(vm.total / 1024 / 1024, 1)
    return info


def _get_rss_mb() -> Optional[float]:
    if not _PSUTIL_AVAILABLE:
        return None
    try:
        proc = _psutil.Process()
        return round(proc.memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return None


def run_capture_benchmark(
    adapter,  # CaptureAdapter — avoids circular import
    n_frames: int = 200,
    description: str = "capture_benchmark",
) -> BenchmarkReport:
    """
    Read n_frames from adapter, measure per-frame decode latency and FPS.

    The adapter is opened, frames are read as fast as possible (no replay throttle),
    and the adapter is closed. JPEG decoding latency is measured per frame.

    Returns a BenchmarkReport with actual measured values only.
    """
    if _cv2 is None or _np is None:
        raise RuntimeError(
            "opencv-python-headless and numpy are required for benchmarking."
        )

    warnings: List[str] = []
    samples: List[FrameLatencySample] = []
    cpu_samples: List[float] = []
    rss_start = _get_rss_mb()

    if _PSUTIL_AVAILABLE:
        proc = _psutil.Process()

    adapter.open()
    wall_start = time.perf_counter()

    try:
        for i in range(n_frames):
            fb = adapter.read_frame()
            if fb is None:
                break  # EOF

            t0 = time.perf_counter()
            buf = _np.frombuffer(fb.frame_data, dtype=_np.uint8)
            _cv2.imdecode(buf, _cv2.IMREAD_COLOR)
            decode_ms = (time.perf_counter() - t0) * 1000.0

            samples.append(FrameLatencySample(
                frame_index=fb.frame_index,
                decode_ms=decode_ms,
                analysis_ms=0.0,
                total_ms=decode_ms,
            ))

            if _PSUTIL_AVAILABLE and i % 10 == 0:
                try:
                    cpu_samples.append(proc.cpu_percent(interval=None))
                except Exception:
                    pass
    finally:
        adapter.close()

    wall_end = time.perf_counter()
    rss_end = _get_rss_mb()
    elapsed = wall_end - wall_start

    delivered = len(samples)
    dropped = n_frames - delivered

    if delivered == 0:
        return BenchmarkReport(
            test_description=description,
            n_frames_requested=n_frames,
            n_frames_delivered=0,
            n_frames_dropped=n_frames,
            elapsed_wall_s=elapsed,
            fps_sustained=0.0,
            latency_ms_min=0.0,
            latency_ms_max=0.0,
            latency_ms_mean=0.0,
            latency_ms_p95=0.0,
            cpu_percent_mean=None,
            rss_mb_start=rss_start,
            rss_mb_end=rss_end,
            hardware_info=_hardware_info(),
            warnings=["No frames delivered — check adapter and source file."],
        )

    latencies = [s.total_ms for s in samples]
    latencies_sorted = sorted(latencies)
    p95_idx = int(len(latencies_sorted) * 0.95)
    fps = delivered / elapsed if elapsed > 0 else 0.0

    if fps < 10:
        warnings.append(
            f"Sustained FPS ({fps:.1f}) is below 10. "
            "This adapter or hardware may not support real-time monitoring."
        )

    return BenchmarkReport(
        test_description=description,
        n_frames_requested=n_frames,
        n_frames_delivered=delivered,
        n_frames_dropped=dropped,
        elapsed_wall_s=round(elapsed, 4),
        fps_sustained=round(fps, 2),
        latency_ms_min=round(min(latencies), 3),
        latency_ms_max=round(max(latencies), 3),
        latency_ms_mean=round(sum(latencies) / len(latencies), 3),
        latency_ms_p95=round(latencies_sorted[p95_idx], 3),
        cpu_percent_mean=(
            round(sum(cpu_samples) / len(cpu_samples), 1)
            if cpu_samples else None
        ),
        rss_mb_start=rss_start,
        rss_mb_end=rss_end,
        hardware_info=_hardware_info(),
        warnings=warnings,
    )
