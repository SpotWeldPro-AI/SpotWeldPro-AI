"""
Tests for the image preprocessing pipeline.

Synthetic images are built from numpy arrays — no external images required.
All tests in cv2-dependent classes are auto-skipped if OpenCV is not installed.
"""
from __future__ import annotations

import struct
import zlib
from typing import Tuple

import pytest


# ── Synthetic image builders ──────────────────────────────────────────────────

def _make_png(width: int, height: int, rgb: Tuple[int, int, int] = (128, 128, 128)) -> bytes:
    """Minimal valid RGB PNG."""
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
    """PNG with a dark circle on a light background (simulates electrode mark)."""
    try:
        import cv2
        import numpy as np
        img = np.full((size, size, 3), 220, dtype=np.uint8)
        cv2.circle(img, (size // 2, size // 2), radius, (50, 50, 50), -1)
        _, enc = cv2.imencode('.png', img)
        return bytes(enc)
    except ImportError:
        return _make_png(size, size, (180, 180, 180))


# ── Test classes ──────────────────────────────────────────────────────────────

class TestImagePreprocessor:
    @pytest.fixture(autouse=True)
    def _require_cv2(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            pytest.skip("opencv-python-headless not installed")

    def test_valid_png_loads(self):
        from app.vision.preprocessing import ImagePreprocessor
        p = ImagePreprocessor()
        raw = _make_png(100, 100, (200, 150, 100))
        img = p.load_and_validate(raw, "test.png")
        assert img.width == 100
        assert img.height == 100
        assert img.metadata.format_detected == "PNG"
        assert img.metadata.file_size_bytes == len(raw)
        assert img.array is not None

    def test_empty_bytes_raises(self):
        from app.vision.preprocessing import ImagePreprocessor, PreprocessingError
        p = ImagePreprocessor()
        with pytest.raises(PreprocessingError, match="empty"):
            p.load_and_validate(b"", "empty.png")

    def test_non_image_bytes_raises(self):
        from app.vision.preprocessing import ImagePreprocessor, PreprocessingError
        p = ImagePreprocessor()
        with pytest.raises(PreprocessingError, match="decode"):
            p.load_and_validate(b"not-an-image-at-all-xyz", "bad.bin")

    def test_oversized_raises(self):
        from app.vision.preprocessing import ImagePreprocessor, PreprocessingError
        p = ImagePreprocessor(max_bytes=50)  # absurdly small cap
        raw = _make_png(10, 10)
        with pytest.raises(PreprocessingError, match="maximum"):
            p.load_and_validate(raw, "big.png")

    def test_roi_extraction_basic(self):
        from app.vision.preprocessing import ImagePreprocessor
        from app.vision.schemas import ROIConfig
        p = ImagePreprocessor()
        raw = _make_png(200, 200)
        img = p.load_and_validate(raw, "test.png")
        roi = ROIConfig(x=10, y=20, width=50, height=60)
        cropped = p.apply_roi(img, roi)
        assert cropped.width == 50
        assert cropped.height == 60
        assert cropped.roi_applied is True
        assert any("ROI applied" in n for n in cropped.notes)

    def test_roi_clamped_to_bounds(self):
        from app.vision.preprocessing import ImagePreprocessor
        from app.vision.schemas import ROIConfig
        p = ImagePreprocessor()
        raw = _make_png(100, 100)
        img = p.load_and_validate(raw, "test.png")
        roi = ROIConfig(x=80, y=80, width=50, height=50)
        cropped = p.apply_roi(img, roi)
        assert cropped.width == 20
        assert cropped.height == 20

    def test_roi_entirely_outside_raises(self):
        from app.vision.preprocessing import ImagePreprocessor, PreprocessingError
        from app.vision.schemas import ROIConfig
        p = ImagePreprocessor()
        raw = _make_png(100, 100)
        img = p.load_and_validate(raw, "test.png")
        roi = ROIConfig(x=200, y=200, width=50, height=50)
        with pytest.raises(PreprocessingError, match="outside image bounds"):
            p.apply_roi(img, roi)

    def test_clahe_produces_valid_shape(self):
        from app.vision.preprocessing import ImagePreprocessor
        p = ImagePreprocessor()
        raw = _make_png(100, 100, (40, 40, 40))
        img = p.load_and_validate(raw, "dark.png")
        enhanced = p.apply_clahe(img)
        assert enhanced.clahe_applied is True
        assert enhanced.array.shape == img.array.shape
        assert any("CLAHE" in n for n in enhanced.notes)

    def test_grayscale_note_added(self):
        from app.vision.preprocessing import ImagePreprocessor
        p = ImagePreprocessor()
        raw = _make_png(100, 100, (128, 128, 128))
        img = p.load_and_validate(raw)
        assert any("grayscale" in n.lower() for n in img.notes)

    def test_non_grayscale_no_note(self):
        from app.vision.preprocessing import ImagePreprocessor
        p = ImagePreprocessor()
        raw = _make_png(100, 100, (200, 50, 10))  # strong red — clearly not grayscale
        img = p.load_and_validate(raw)
        assert not any("grayscale" in n.lower() for n in img.notes)

    def test_metadata_channels(self):
        from app.vision.preprocessing import ImagePreprocessor
        p = ImagePreprocessor()
        raw = _make_png(80, 60)
        img = p.load_and_validate(raw, "test.png")
        assert img.metadata.channels == 3

    def test_metadata_dimensions_match_array(self):
        from app.vision.preprocessing import ImagePreprocessor
        p = ImagePreprocessor()
        raw = _make_png(120, 90)
        img = p.load_and_validate(raw, "test.png")
        h, w = img.array.shape[:2]
        assert w == img.width == img.metadata.width_px == 120
        assert h == img.height == img.metadata.height_px == 90


class TestFormatDetection:
    def test_png_magic(self):
        from app.vision.preprocessing import _detect_format
        raw = _make_png(10, 10)
        assert _detect_format(raw, "image.png") == "PNG"

    def test_jpeg_magic(self):
        from app.vision.preprocessing import _detect_format
        fake_jpeg = b'\xff\xd8\xff\xe0' + b'\x00' * 20
        assert _detect_format(fake_jpeg, "photo.jpg") == "JPEG"

    def test_tiff_magic_le(self):
        from app.vision.preprocessing import _detect_format
        fake_tiff = b'II*\x00' + b'\x00' * 20
        assert _detect_format(fake_tiff, "scan.tif") == "TIFF"

    def test_bmp_magic(self):
        from app.vision.preprocessing import _detect_format
        fake_bmp = b'BM' + b'\x00' * 20
        assert _detect_format(fake_bmp, "img.bmp") == "BMP"

    def test_webp_magic(self):
        from app.vision.preprocessing import _detect_format
        fake_webp = b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 20
        assert _detect_format(fake_webp, "img.webp") == "WebP"

    def test_fallback_to_extension(self):
        from app.vision.preprocessing import _detect_format
        assert _detect_format(b'\x00\x00\x00', "scan.TIF") == "TIF"

    def test_unknown_no_extension(self):
        from app.vision.preprocessing import _detect_format
        assert _detect_format(b'\x00\x01\x02', "") == "UNKNOWN"


class TestGrayscaleDetection:
    def test_pure_grey_is_grayscale(self):
        from app.vision.preprocessing import _is_effectively_grayscale
        import numpy as np
        img = np.full((50, 50, 3), 128, dtype=np.uint8)
        assert _is_effectively_grayscale(img)

    def test_colored_image_is_not_grayscale(self):
        from app.vision.preprocessing import _is_effectively_grayscale
        import numpy as np
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        img[:, :, 2] = 200  # strong red channel
        assert not _is_effectively_grayscale(img)
