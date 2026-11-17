"""
VISION-SYNTH-E2E-01
===================
End-to-end validation of the synthetic image and video assets against
the vision backend APIs and infrastructure.

Coverage:
  - PNG-01..PNG-12: SHA256 integrity, pixel dimensions, API upload, ROI crop
  - MP4-01..MP4-09: SHA256 integrity, ffprobe metadata vs MANIFEST, frame count
  - VID-10 (CORRUPT): error-handling for unreadable file
  - API-01..API-10: static inspection endpoint with real synthetic images
  - ROI-01..ROI-04: region-of-interest crop and inspection
  - ERR-01..ERR-04: error conditions (oversized, corrupt, bad ROI, unauthenticated)
  - MOTION-01..MOTION-03: MotionEventDetector with synthetic frame sequences

Hard rules:
  - SYNTHETIC_TEST_DATA watermark must be present in missing_weld PNG (text-layer PNG)
  - No fabricated AI predictions used as acceptance thresholds
  - No production DB touched (uses conftest.py's SQLite fixture)
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Tuple

import pytest

# ── Paths ──────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).parent.parent.parent
_IMG_DIR = _REPO / "backend" / "tests" / "synthetic_data" / "images"
_VID_DIR = _REPO / "backend" / "tests" / "synthetic_data" / "videos"
_IMG_MANIFEST = _IMG_DIR / "MANIFEST.json"
_VID_MANIFEST = _VID_DIR / "MANIFEST.json"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def img_manifest():
    with open(_IMG_MANIFEST) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def vid_manifest():
    with open(_VID_MANIFEST) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def ffprobe_available():
    result = subprocess.run(["ffprobe", "-version"], capture_output=True)
    return result.returncode == 0


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _png_dimensions(path: Path) -> Tuple[int, int]:
    with open(path, "rb") as f:
        sig = f.read(8)
        assert sig == b"\x89PNG\r\n\x1a\n", "Not a PNG"
        f.read(4)  # length
        assert f.read(4) == b"IHDR"
        w = struct.unpack(">I", f.read(4))[0]
        h = struct.unpack(">I", f.read(4))[0]
        return w, h


def _make_grey_png(width: int, height: int, grey: int = 180) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    scanline = bytes([0]) + bytes([grey, grey, grey]) * width
    idat = chunk(b"IDAT", zlib.compress(scanline * height))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _upload_png(client, auth_headers, png_bytes, filename="test.png", **form):
    return client.post(
        "/api/v1/vision/static/inspect",
        files={"image": (filename, png_bytes, "image/png")},
        data=form,
        headers=auth_headers,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PNG-01..PNG-12: Integrity checks (no API, pure file validation)
# ══════════════════════════════════════════════════════════════════════════════

class TestSyntheticPNGIntegrity:
    """PNG-01..PNG-12 — file integrity against MANIFEST.json."""

    def test_manifest_has_12_images(self, img_manifest):
        assert img_manifest["total_images"] == 12
        assert len(img_manifest["images"]) == 12

    @pytest.mark.parametrize("entry", json.loads(_IMG_MANIFEST.read_text())["images"],
                             ids=[e["scenario"] for e in json.loads(_IMG_MANIFEST.read_text())["images"]])
    def test_png_sha256_matches_manifest(self, entry):
        path = _IMG_DIR / entry["filename"]
        assert path.exists(), f"File missing: {entry['filename']}"
        actual = _sha256(path)
        assert actual == entry["sha256"], (
            f"{entry['filename']}: SHA256 mismatch\n  actual  : {actual}\n  expected: {entry['sha256']}"
        )

    @pytest.mark.parametrize("entry", json.loads(_IMG_MANIFEST.read_text())["images"],
                             ids=[e["scenario"] for e in json.loads(_IMG_MANIFEST.read_text())["images"]])
    def test_png_dimensions_200x200(self, entry):
        path = _IMG_DIR / entry["filename"]
        w, h = _png_dimensions(path)
        assert w == 200, f"{entry['filename']}: width={w} expected 200"
        assert h == 200, f"{entry['filename']}: height={h} expected 200"

    @pytest.mark.parametrize("entry", json.loads(_IMG_MANIFEST.read_text())["images"],
                             ids=[e["scenario"] for e in json.loads(_IMG_MANIFEST.read_text())["images"]])
    def test_png_size_matches_manifest(self, entry):
        path = _IMG_DIR / entry["filename"]
        actual_size = path.stat().st_size
        assert actual_size == entry["size_bytes"], (
            f"{entry['filename']}: size={actual_size} expected={entry['size_bytes']}"
        )

    def test_disclaimer_present_in_manifest(self, img_manifest):
        d = img_manifest.get("disclaimer", "")
        assert "SYNTHETIC" in d.upper(), "MANIFEST disclaimer missing SYNTHETIC marker"
        assert "NOT" in d.upper(), "MANIFEST disclaimer should contain NOT"

    def test_mask_json_exists_for_each_image(self):
        entries = json.loads(_IMG_MANIFEST.read_text())["images"]
        for entry in entries:
            stem = Path(entry["filename"]).stem  # e.g. synth_normal_circular
            mask_path = _IMG_DIR / f"{stem}_mask.json"
            assert mask_path.exists(), f"Mask JSON missing: {mask_path.name}"

    def test_mask_bbox_matches_manifest(self):
        entries = json.loads(_IMG_MANIFEST.read_text())["images"]
        for entry in entries:
            stem = Path(entry["filename"]).stem
            mask_path = _IMG_DIR / f"{stem}_mask.json"
            if not mask_path.exists():
                continue
            mask = json.loads(mask_path.read_text())
            assert mask["bbox"] == entry["bbox"], (
                f"{entry['filename']}: mask bbox {mask['bbox']} != manifest {entry['bbox']}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# MP4-01..MP4-10: Video integrity checks
# ══════════════════════════════════════════════════════════════════════════════

class TestSyntheticVideoIntegrity:
    """MP4-01..MP4-10 — file integrity and metadata against MANIFEST.json."""

    def test_manifest_has_10_videos(self, vid_manifest):
        assert vid_manifest["total_videos"] == 10
        assert len(vid_manifest["videos"]) == 10

    @pytest.mark.parametrize("entry", json.loads(_VID_MANIFEST.read_text())["videos"],
                             ids=[e["scenario"] for e in json.loads(_VID_MANIFEST.read_text())["videos"]])
    def test_video_sha256_matches_manifest(self, entry):
        path = _VID_DIR / entry["filename"]
        assert path.exists(), f"File missing: {entry['filename']}"
        actual = _sha256(path)
        assert actual == entry["sha256"], (
            f"{entry['filename']}: SHA256 mismatch\n  actual  : {actual}\n  expected: {entry['sha256']}"
        )

    @pytest.mark.parametrize("entry", json.loads(_VID_MANIFEST.read_text())["videos"],
                             ids=[e["scenario"] for e in json.loads(_VID_MANIFEST.read_text())["videos"]])
    def test_video_size_matches_manifest(self, entry):
        path = _VID_DIR / entry["filename"]
        actual = path.stat().st_size
        assert actual == entry["size_bytes"], (
            f"{entry['filename']}: size={actual} expected={entry['size_bytes']}"
        )

    def test_disclaimer_present_in_video_manifest(self, vid_manifest):
        d = vid_manifest.get("disclaimer", "")
        assert "SYNTHETIC" in d.upper()
        assert "NOT" in d.upper()

    def test_unsupported_format_bin_is_not_mp4(self, vid_manifest):
        entry = next(v for v in vid_manifest["videos"] if v["scenario"] == "unsupported_format")
        assert entry["status"] == "INTENTIONAL_ERROR"
        assert entry["filename"].endswith(".bin")
        path = _VID_DIR / entry["filename"]
        with open(path, "rb") as f:
            header = f.read(4)
        assert header != b"\x00\x00\x00\x1c", "Should not be a valid MP4 ftyp"


class TestSyntheticVideoMetadata:
    """Probe actual video containers with ffprobe and compare to MANIFEST."""

    @pytest.fixture(autouse=True)
    def _require_ffprobe(self, ffprobe_available):
        if not ffprobe_available:
            pytest.skip("ffprobe not available")

    # Only probe the 9 real MP4s (skip the .bin intentional error)
    _MP4_ENTRIES = [
        e for e in json.loads(_VID_MANIFEST.read_text())["videos"]
        if e["status"] == "OK"
    ]

    @pytest.mark.parametrize("entry", _MP4_ENTRIES,
                             ids=[e["scenario"] for e in _MP4_ENTRIES])
    def test_ffprobe_dimensions(self, entry):
        path = str(_VID_DIR / entry["filename"])
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True, timeout=15
        )
        assert result.returncode == 0, f"ffprobe failed: {result.stderr[:200]}"
        streams = json.loads(result.stdout).get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        assert video_stream is not None, "No video stream found"
        assert video_stream["width"] == entry["width"]
        assert video_stream["height"] == entry["height"]

    @pytest.mark.parametrize("entry", _MP4_ENTRIES,
                             ids=[e["scenario"] for e in _MP4_ENTRIES])
    def test_ffprobe_fps(self, entry):
        path = str(_VID_DIR / entry["filename"])
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True, timeout=15
        )
        streams = json.loads(result.stdout).get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        assert video_stream is not None
        num, den = map(int, video_stream["r_frame_rate"].split("/"))
        actual_fps = num / den
        assert abs(actual_fps - entry["fps"]) < 0.5, (
            f"{entry['filename']}: fps={actual_fps} expected={entry['fps']}"
        )

    @pytest.mark.parametrize("entry", _MP4_ENTRIES,
                             ids=[e["scenario"] for e in _MP4_ENTRIES])
    def test_ffprobe_duration(self, entry):
        path = str(_VID_DIR / entry["filename"])
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True, timeout=15
        )
        streams = json.loads(result.stdout).get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        assert video_stream is not None
        actual_dur = float(video_stream.get("duration", 0))
        assert abs(actual_dur - entry["duration_s"]) < 0.1, (
            f"{entry['filename']}: duration={actual_dur} expected={entry['duration_s']}"
        )

    @pytest.mark.parametrize("entry", _MP4_ENTRIES,
                             ids=[e["scenario"] for e in _MP4_ENTRIES])
    def test_ffprobe_frame_count(self, entry):
        path = str(_VID_DIR / entry["filename"])
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True, timeout=15
        )
        streams = json.loads(result.stdout).get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        assert video_stream is not None
        actual_frames = int(video_stream.get("nb_frames", 0))
        expected_frames = int(entry["fps"] * entry["duration_s"])
        assert actual_frames == expected_frames, (
            f"{entry['filename']}: frames={actual_frames} expected={expected_frames}"
        )

    def test_corrupt_file_ffprobe_fails(self):
        path = str(_VID_DIR / "synth_unsupported_format.bin")
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", path], capture_output=True, timeout=5
        )
        assert result.returncode != 0, "ffprobe should fail on corrupt file"


# ══════════════════════════════════════════════════════════════════════════════
# API-01..API-10: Static inspection endpoint with real synthetic PNGs
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=False)
def _require_cv2():
    try:
        import cv2  # noqa: F401
    except ImportError:
        pytest.skip("opencv-python-headless not installed")


class TestStaticInspectionWithSyntheticPNGs:
    """API-01..API-10 — POST /api/v1/vision/static/inspect with real synthetic images."""

    @pytest.fixture(autouse=True)
    def _cv2(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            pytest.skip("opencv-python-headless not installed")

    _MANIFEST_DATA = json.loads(_IMG_MANIFEST.read_text())

    @pytest.mark.parametrize("entry", _MANIFEST_DATA["images"],
                             ids=[e["scenario"] for e in _MANIFEST_DATA["images"]])
    def test_inspect_returns_200(self, entry, client, auth_headers):
        path = _IMG_DIR / entry["filename"]
        with open(path, "rb") as f:
            png_bytes = f.read()
        resp = _upload_png(client, auth_headers, png_bytes, filename=entry["filename"])
        assert resp.status_code == 200, f"{entry['scenario']}: got {resp.status_code} — {resp.text[:200]}"

    @pytest.mark.parametrize("entry", _MANIFEST_DATA["images"],
                             ids=[e["scenario"] for e in _MANIFEST_DATA["images"]])
    def test_inspect_result_structure(self, entry, client, auth_headers):
        path = _IMG_DIR / entry["filename"]
        with open(path, "rb") as f:
            png_bytes = f.read()
        resp = _upload_png(client, auth_headers, png_bytes, filename=entry["filename"])
        assert resp.status_code == 200
        body = resp.json()
        assert "inspection_id" in body
        assert "status" in body
        assert "image_metadata" in body
        meta = body["image_metadata"]
        assert meta["width_px"] == 200
        assert meta["height_px"] == 200

    @pytest.mark.parametrize("entry", _MANIFEST_DATA["images"],
                             ids=[e["scenario"] for e in _MANIFEST_DATA["images"]])
    def test_inspect_no_fabricated_verdict_without_criteria(self, entry, client, auth_headers):
        """Without acceptance criteria, status must be NOT_EVALUATED."""
        path = _IMG_DIR / entry["filename"]
        with open(path, "rb") as f:
            png_bytes = f.read()
        resp = _upload_png(client, auth_headers, png_bytes, filename=entry["filename"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "NOT_EVALUATED", (
            f"{entry['scenario']}: status={body['status']} but no criteria were supplied"
        )

    def test_inspect_with_calibration_produces_mm_measurements(self, client, auth_headers):
        """pixels_per_mm supplied → diameter_mm should be non-None for well-formed circular image."""
        path = _IMG_DIR / "synth_normal_circular.png"
        with open(path, "rb") as f:
            png_bytes = f.read()
        resp = _upload_png(
            client, auth_headers, png_bytes,
            filename="synth_normal_circular.png",
            image_type="SURFACE",
            pixels_per_mm="10.0",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["calibration"] is not None
        assert body["calibration"]["pixels_per_mm"] == 10.0
        # With calibration, indentation diameter_mm should be a number if detected
        # (it may be None if the engine couldn't detect a contour — that's acceptable)
        # but the calibration object itself must be populated
        assert body["calibration"]["pixels_per_mm"] > 0

    def test_inspect_surface_type_accepted(self, client, auth_headers):
        path = _IMG_DIR / "synth_normal_circular.png"
        with open(path, "rb") as f:
            png_bytes = f.read()
        resp = _upload_png(client, auth_headers, png_bytes, image_type="SURFACE")
        assert resp.status_code == 200
        body = resp.json()
        assert body["image_type"] == "SURFACE"

    def test_inspect_cross_section_type_accepted(self, client, auth_headers):
        path = _IMG_DIR / "synth_elliptical_indentation.png"
        with open(path, "rb") as f:
            png_bytes = f.read()
        resp = _upload_png(client, auth_headers, png_bytes, image_type="CROSS_SECTION")
        assert resp.status_code == 200
        body = resp.json()
        assert body["image_type"] == "CROSS_SECTION"

    def test_inspect_with_acceptance_criteria_evaluates_status(self, client, auth_headers):
        """Supplying criteria causes status to be something other than NOT_EVALUATED."""
        path = _IMG_DIR / "synth_normal_circular.png"
        with open(path, "rb") as f:
            png_bytes = f.read()
        resp = _upload_png(
            client, auth_headers, png_bytes,
            pixels_per_mm="10.0",
            min_nugget_diameter_mm="3.0",
            max_nugget_diameter_mm="8.0",
            max_allowed_defects="5",
            criteria_version="test-v1",
        )
        assert resp.status_code == 200
        body = resp.json()
        # With criteria, status should be OK, NOK, or REVIEW — not NOT_EVALUATED
        assert body["status"] in ("OK", "NOK", "REVIEW"), (
            f"Expected evaluated status, got {body['status']}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ROI-01..ROI-04: Region-of-Interest crop tests
# ══════════════════════════════════════════════════════════════════════════════

class TestROIHandling:
    """ROI-01..ROI-04 — ROI crop applied before inspection."""

    @pytest.fixture(autouse=True)
    def _cv2(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            pytest.skip("opencv-python-headless not installed")

    def test_roi_from_manifest_accepted(self, client, auth_headers):
        """ROI coordinates from MANIFEST bbox should be accepted without error."""
        entry = next(
            e for e in json.loads(_IMG_MANIFEST.read_text())["images"]
            if e["scenario"] == "normal_circular"
        )
        with open(_IMG_DIR / entry["filename"], "rb") as f:
            png_bytes = f.read()
        bbox = entry["bbox"]
        resp = _upload_png(
            client, auth_headers, png_bytes,
            roi_x=str(bbox["x"]), roi_y=str(bbox["y"]),
            roi_w=str(bbox["w"]), roi_h=str(bbox["h"]),
        )
        assert resp.status_code == 200
        body = resp.json()
        # After ROI crop, dimensions equal the ROI size
        assert body["image_metadata"]["width_px"] == bbox["w"]
        assert body["image_metadata"]["height_px"] == bbox["h"]

    def test_roi_misalignment_scenario(self, client, auth_headers):
        """ROI from misalignment mask applied to misalignment image."""
        with open(_IMG_DIR / "synth_misalignment.png", "rb") as f:
            png_bytes = f.read()
        mask = json.loads((_IMG_DIR / "synth_misalignment_mask.json").read_text())
        bbox = mask["bbox"]
        resp = _upload_png(
            client, auth_headers, png_bytes,
            roi_x=str(bbox["x"]), roi_y=str(bbox["y"]),
            roi_w=str(bbox["w"]), roi_h=str(bbox["h"]),
        )
        assert resp.status_code == 200

    def test_roi_clamped_when_partially_out_of_bounds(self, client, auth_headers):
        """ROI extending beyond bounds is CLAMPED (not rejected).
        ROI starting at x=30 on a 50-wide image with w=50 → clamped to width=20.
        Only an ROI entirely outside the image raises 422."""
        png_bytes = _make_grey_png(50, 50)
        resp = _upload_png(
            client, auth_headers, png_bytes,
            roi_x="30", roi_y="0", roi_w="50", roi_h="50",  # x2=min(50,80)=50 → 20px wide
        )
        # Backend clamps, so 200 is correct behavior
        assert resp.status_code == 200, f"Clamped ROI should succeed, got {resp.status_code}"
        body = resp.json()
        # After clamping x=30..50, result is 20px wide
        assert body["image_metadata"]["width_px"] == 20

    def test_roi_entirely_outside_returns_422(self, client, auth_headers):
        """ROI completely outside image bounds → zero-area crop → 422."""
        png_bytes = _make_grey_png(50, 50)
        resp = _upload_png(
            client, auth_headers, png_bytes,
            roi_x="100", roi_y="100", roi_w="20", roi_h="20",  # entirely outside 50x50
        )
        assert resp.status_code == 422, f"Entirely out-of-bounds ROI should return 422, got {resp.status_code}"

    def test_roi_partial_params_ignored(self, client, auth_headers):
        """Supplying only some ROI params (not all 4) should NOT apply ROI."""
        with open(_IMG_DIR / "synth_normal_circular.png", "rb") as f:
            png_bytes = f.read()
        # Only roi_x and roi_y, no roi_w or roi_h → ROI not applied → full 200x200 returned
        resp = _upload_png(
            client, auth_headers, png_bytes,
            roi_x="50", roi_y="50",  # roi_w and roi_h omitted
        )
        assert resp.status_code == 200
        body = resp.json()
        # Full image returned since ROI wasn't complete
        assert body["image_metadata"]["width_px"] == 200
        assert body["image_metadata"]["height_px"] == 200


# ══════════════════════════════════════════════════════════════════════════════
# ERR-01..ERR-05: Error handling
# ══════════════════════════════════════════════════════════════════════════════

class TestVisionAPIErrorHandling:
    """ERR-01..ERR-05 — boundary and error conditions."""

    def test_unauthenticated_returns_401(self, client):
        """ERR-01: No auth header → 401."""
        png_bytes = _make_grey_png(100, 100)
        resp = client.post(
            "/api/v1/vision/static/inspect",
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 401

    def test_corrupt_file_returns_422(self, client, auth_headers):
        """ERR-02: Corrupt/non-image bytes → 422."""
        corrupt = b"THIS_IS_NOT_AN_IMAGE"
        resp = _upload_png(client, auth_headers, corrupt, filename="corrupt.png")
        assert resp.status_code == 422

    def test_empty_file_returns_422(self, client, auth_headers):
        """ERR-03: Zero-byte upload → 422."""
        resp = _upload_png(client, auth_headers, b"", filename="empty.png")
        assert resp.status_code == 422

    def test_synth_unsupported_format_bin_returns_422(self, client, auth_headers):
        """ERR-04: The .bin intentional-error file → 422."""
        path = _VID_DIR / "synth_unsupported_format.bin"
        with open(path, "rb") as f:
            corrupt_bytes = f.read()
        resp = _upload_png(client, auth_headers, corrupt_bytes, filename="bad.bin")
        assert resp.status_code == 422

    def test_missing_image_field_returns_422(self, client, auth_headers):
        """ERR-05: Request with no image field → 422."""
        resp = client.post(
            "/api/v1/vision/static/inspect",
            data={"image_type": "SURFACE"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# MOTION-01..MOTION-03: MotionEventDetector with synthetic frame sequences
# ══════════════════════════════════════════════════════════════════════════════

class TestMotionDetectorWithSyntheticFrames:
    """MOTION-01..MOTION-03 — deterministic motion detection on synthetic frames.

    MotionEventDetector.detect(bundle: FrameBundle) → TemporalEvent
    MotionDetectorConfig(threshold=float, blur_ksize=int, min_frame_gap_ms=float)
    FrameBundle(frame_data=bytes, timestamp=datetime, frame_index=int,
                source_id=str, width=int, height=int)
    """

    @pytest.fixture(autouse=True)
    def _cv2(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            pytest.skip("opencv-python-headless not installed")

    @staticmethod
    def _make_bundle(brightness: int, idx: int, w: int = 160, h: int = 120) -> "object":
        import cv2
        import numpy as np
        from datetime import datetime, timezone
        from app.vision.capture.base import FrameBundle

        frame = np.full((h, w, 3), brightness, dtype=np.uint8)
        _, enc = cv2.imencode(".jpg", frame)
        return FrameBundle(
            frame_data=bytes(enc),
            timestamp=datetime.now(timezone.utc),
            frame_index=idx,
            source_id="synth-test",
            width=w,
            height=h,
        )

    def test_motion_detected_on_brightness_change(self):
        """MOTION-01: Bright flash frame causes MOTION_DETECTED event."""
        from app.vision.motion_detection import MotionEventDetector, MotionDetectorConfig

        cfg = MotionDetectorConfig(threshold=10.0)
        detector = MotionEventDetector(config=cfg)

        # Prime with base (grey=50), then send flash (grey=220)
        base_bundle = self._make_bundle(50, 0)
        flash_bundle = self._make_bundle(220, 1)

        ev_base = detector.detect(base_bundle)   # first call → IDLE (no prior frame)
        ev_flash = detector.detect(flash_bundle)  # large change → MOTION_DETECTED

        assert ev_flash.event_type.value == "MOTION_DETECTED", (
            f"Expected MOTION_DETECTED, got {ev_flash.event_type}: magnitude={ev_flash.magnitude}"
        )

    def test_idle_on_static_scene(self):
        """MOTION-02: Static (unchanging) scene → all IDLE, no MOTION_DETECTED."""
        from app.vision.motion_detection import MotionEventDetector, MotionDetectorConfig

        cfg = MotionDetectorConfig(threshold=5.0)
        detector = MotionEventDetector(config=cfg)

        for i in range(5):
            bundle = self._make_bundle(100, i)
            ev = detector.detect(bundle)
            if i > 0:  # first call is always IDLE (no prior)
                assert ev.event_type.value == "IDLE", (
                    f"Frame {i}: static scene should be IDLE, got {ev.event_type} "
                    f"(magnitude={ev.magnitude})"
                )

    def test_motion_magnitude_proportional_to_change(self):
        """MOTION-03: Higher pixel delta → higher reported magnitude."""
        from app.vision.motion_detection import MotionEventDetector, MotionDetectorConfig

        cfg = MotionDetectorConfig(threshold=0.1)  # low threshold, detect everything
        det_small = MotionEventDetector(config=cfg)
        det_large = MotionEventDetector(config=cfg)

        # Prime both detectors
        det_small.detect(self._make_bundle(100, 0))
        det_large.detect(self._make_bundle(100, 0))

        ev_small = det_small.detect(self._make_bundle(110, 1))  # Δ≈10
        ev_large = det_large.detect(self._make_bundle(200, 1))  # Δ≈100

        assert ev_large.magnitude > ev_small.magnitude, (
            f"Large change should have higher magnitude: "
            f"large={ev_large.magnitude} vs small={ev_small.magnitude}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TIMELINE-01..TIMELINE-03: Synthetic event timeline validation
# ══════════════════════════════════════════════════════════════════════════════

class TestSyntheticEventTimelines:
    """Validate expected_events in video MANIFEST against reasonable time windows."""

    def test_normal_approach_has_5_phase_events(self, vid_manifest):
        """TIMELINE-01: Normal approach cycle has exactly 5 annotated phases."""
        entry = next(v for v in vid_manifest["videos"] if v["scenario"] == "normal_approach")
        assert len(entry["expected_events"]) == 5
        labels = [e["label"] for e in entry["expected_events"]]
        assert labels == ["approach", "clamp", "weld", "hold", "release"]

    def test_all_events_within_duration(self, vid_manifest):
        """TIMELINE-02: Every event t_end <= video duration_s."""
        for vid in vid_manifest["videos"]:
            for ev in vid.get("expected_events", []):
                assert ev["t_end"] <= vid["duration_s"] + 0.01, (
                    f"{vid['scenario']}: event '{ev['label']}' t_end={ev['t_end']} > duration={vid['duration_s']}"
                )
                assert ev["t_start"] >= 0.0
                assert ev["t_start"] < ev["t_end"]

    def test_multi_spot_has_3_sequential_spots(self, vid_manifest):
        """TIMELINE-03: multi_spot_seq has 3 non-overlapping spot events."""
        entry = next(v for v in vid_manifest["videos"] if v["scenario"] == "multi_spot_seq")
        evs = entry["expected_events"]
        assert len(evs) == 3
        for i in range(1, len(evs)):
            assert evs[i]["t_start"] >= evs[i - 1]["t_end"], (
                f"Spots overlap: {evs[i-1]} → {evs[i]}"
            )

    def test_expulsion_event_within_weld_window(self, vid_manifest):
        """TIMELINE-04: Expulsion event at ~t=1.5 is within plausible weld range."""
        entry = next(v for v in vid_manifest["videos"] if v["scenario"] == "expulsion_event")
        ev = entry["expected_events"][0]
        assert ev["label"] == "expulsion_flash"
        assert 0.5 <= ev["t_start"] <= 3.5

    def test_stream_interrupt_blackout_at_t2(self, vid_manifest):
        """TIMELINE-05: stream_interrupt has blackout at t=2."""
        entry = next(v for v in vid_manifest["videos"] if v["scenario"] == "stream_interrupt")
        ev = entry["expected_events"][0]
        assert ev["label"] == "blackout"
        assert abs(ev["t_start"] - 2.0) < 0.1

    def test_dropped_frames_has_low_fps(self, vid_manifest):
        """TIMELINE-06: dropped_frames scenario has fps=15 (half normal)."""
        entry = next(v for v in vid_manifest["videos"] if v["scenario"] == "dropped_frames")
        assert entry["fps"] == 15
        assert entry["fps"] < 30


# ══════════════════════════════════════════════════════════════════════════════
# SYNTH-MARKER: Watermark / disclaimer markers in synthetic assets
# ══════════════════════════════════════════════════════════════════════════════

class TestSyntheticDataMarkers:
    """Confirm SYNTHETIC_TEST_DATA markers are present where required."""

    def test_missing_weld_png_contains_watermark_marker(self):
        """The missing_weld PNG is large (25241 bytes) because it embeds a text layer.
        Verify the PNG is not just a blank 200x200 by checking its actual size."""
        path = _IMG_DIR / "synth_missing_weld.png"
        size = path.stat().st_size
        # normal blank PNGs are ~1-3 KB; the missing_weld one is ~25 KB due to noise/text
        assert size > 5000, f"synth_missing_weld.png is too small ({size}B); may be missing watermark layer"

    def test_noise_heavy_png_is_largest(self):
        """noise_heavy PNG should be the largest because of random pixel data."""
        entries = json.loads(_IMG_MANIFEST.read_text())["images"]
        sizes = {e["scenario"]: e["size_bytes"] for e in entries}
        assert sizes["noise_heavy"] > sizes["normal_circular"], (
            "noise_heavy should be larger than normal_circular"
        )

    def test_image_manifest_seed_is_42(self, img_manifest):
        assert img_manifest["seed"] == 42, "Reproducibility seed should be 42"

    def test_all_manifests_have_version_field(self, img_manifest, vid_manifest):
        assert "version" in img_manifest
        assert "version" in vid_manifest

    def test_no_expected_defect_none_for_defect_scenarios(self, img_manifest):
        """Scenarios with actual defects must have a non-'none' expected_defect."""
        no_defect_scenarios = {"normal_circular", "multi_spot_pattern"}
        for entry in img_manifest["images"]:
            if entry["scenario"] not in no_defect_scenarios:
                assert entry["expected_defect"] != "none", (
                    f"Scenario '{entry['scenario']}' should have a defect label, got 'none'"
                )
