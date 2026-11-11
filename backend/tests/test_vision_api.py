"""
Integration tests for the vision static inspection API endpoint.

Uses the existing TestClient + SQLite fixture from conftest.py.
Image uploads use synthetic PNG bytes — no external files required.
cv2-dependent tests are auto-skipped when OpenCV is not installed.
"""
from __future__ import annotations

import struct
import zlib
from typing import Tuple

import pytest


def _make_png(width: int, height: int, rgb: Tuple[int, int, int] = (128, 128, 128)) -> bytes:
    r, g, b = rgb
    sig = b'\x89PNG\r\n\x1a\n'

    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        return struct.pack('>I', len(data)) + payload + struct.pack('>I', zlib.crc32(payload) & 0xFFFFFFFF)

    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    scanline = bytes([0]) + bytes([r, g, b]) * width
    idat = chunk(b'IDAT', zlib.compress(scanline * height))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


def _make_png_with_circle(size: int = 200, radius: int = 40) -> bytes:
    try:
        import cv2
        import numpy as np
        img = np.full((size, size, 3), 220, dtype=np.uint8)
        cv2.circle(img, (size // 2, size // 2), radius, (50, 50, 50), -1)
        _, enc = cv2.imencode('.png', img)
        return bytes(enc)
    except ImportError:
        return _make_png(size, size)


def _upload(client, auth_headers, png_bytes, **form_fields):
    """POST to /api/v1/vision/static/inspect with a PNG upload."""
    return client.post(
        "/api/v1/vision/static/inspect",
        files={"image": ("test.png", png_bytes, "image/png")},
        data=form_fields,
        headers=auth_headers,
    )


class TestVisionStaticAPI:
    @pytest.fixture(autouse=True)
    def _require_cv2(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            pytest.skip("opencv-python-headless not installed")

    def test_unauthenticated_request_rejected(self, client):
        raw = _make_png(100, 100)
        r = client.post(
            "/api/v1/vision/static/inspect",
            files={"image": ("t.png", raw, "image/png")},
        )
        assert r.status_code in (401, 403)

    def test_valid_surface_image_returns_200(self, client, auth_headers):
        raw = _make_png_with_circle()
        r = _upload(client, auth_headers, raw, image_type="SURFACE")
        assert r.status_code == 200

    def test_response_has_required_fields(self, client, auth_headers):
        raw = _make_png_with_circle()
        r = _upload(client, auth_headers, raw, image_type="SURFACE")
        assert r.status_code == 200
        body = r.json()
        for field in ("inspection_id", "timestamp", "status", "image_type", "defects"):
            assert field in body, f"Missing field: {field}"

    def test_status_not_evaluated_without_criteria(self, client, auth_headers):
        raw = _make_png_with_circle()
        r = _upload(client, auth_headers, raw, image_type="SURFACE")
        assert r.status_code == 200
        assert r.json()["status"] == "NOT_EVALUATED"

    def test_status_evaluated_with_criteria(self, client, auth_headers):
        raw = _make_png_with_circle()
        r = _upload(
            client, auth_headers, raw,
            image_type="SURFACE",
            max_allowed_defects="100",
            criteria_version="test-v1",
        )
        assert r.status_code == 200
        assert r.json()["status"] != "NOT_EVALUATED"

    def test_cross_section_image_type(self, client, auth_headers):
        raw = _make_png(200, 200, (160, 160, 160))
        r = _upload(client, auth_headers, raw, image_type="CROSS_SECTION")
        assert r.status_code == 200
        assert r.json()["image_type"] == "CROSS_SECTION"

    def test_empty_file_returns_422(self, client, auth_headers):
        r = client.post(
            "/api/v1/vision/static/inspect",
            files={"image": ("empty.png", b"", "image/png")},
            data={"image_type": "SURFACE"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_non_image_file_returns_422(self, client, auth_headers):
        r = client.post(
            "/api/v1/vision/static/inspect",
            files={"image": ("bad.png", b"not-image-data-xyz", "image/png")},
            data={"image_type": "SURFACE"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_calibration_accepted(self, client, auth_headers):
        raw = _make_png_with_circle(200, 40)
        r = _upload(
            client, auth_headers, raw,
            image_type="SURFACE",
            pixels_per_mm="12.5",
        )
        assert r.status_code == 200
        body = r.json()
        assert body["calibration"]["pixels_per_mm"] == pytest.approx(12.5)

    def test_roi_parameters_accepted(self, client, auth_headers):
        raw = _make_png_with_circle(200, 40)
        r = _upload(
            client, auth_headers, raw,
            image_type="SURFACE",
            roi_x="10", roi_y="10", roi_w="100", roi_h="100",
        )
        assert r.status_code == 200

    def test_roi_outside_image_returns_422(self, client, auth_headers):
        raw = _make_png(100, 100)
        r = _upload(
            client, auth_headers, raw,
            image_type="SURFACE",
            roi_x="500", roi_y="500", roi_w="50", roi_h="50",
        )
        assert r.status_code == 422

    def test_defects_is_a_list(self, client, auth_headers):
        raw = _make_png_with_circle()
        r = _upload(client, auth_headers, raw, image_type="SURFACE")
        assert r.status_code == 200
        assert isinstance(r.json()["defects"], list)

    def test_image_metadata_in_response(self, client, auth_headers):
        raw = _make_png(150, 120)
        r = _upload(client, auth_headers, raw, image_type="SURFACE")
        assert r.status_code == 200
        meta = r.json()["image_metadata"]
        assert meta["width_px"] == 150
        assert meta["height_px"] == 120


class TestVisionLiveAPI:
    def test_sources_endpoint_returns_200(self, client, auth_headers):
        r = client.get("/api/v1/vision/live/sources", headers=auth_headers)
        # This endpoint is public (no auth required) but should still return 200
        assert r.status_code == 200
        body = r.json()
        assert "sources" in body
        assert isinstance(body["sources"], list)
