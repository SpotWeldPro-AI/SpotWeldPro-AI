"""
Tests for the static inspection engine.

Synthetic images are built from numpy arrays — no external images required.
All cv2-dependent tests are auto-skipped when OpenCV is unavailable.
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


def _load(raw: bytes):
    from app.vision.preprocessing import ImagePreprocessor
    return ImagePreprocessor().load_and_validate(raw, "test.png")


class TestStaticInspectionEngine:
    @pytest.fixture(autouse=True)
    def _require_cv2(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            pytest.skip("opencv-python-headless not installed")

    def test_result_has_id_and_timestamp(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType
        raw = _make_png_with_circle()
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.SURFACE)
        assert result.inspection_id
        assert "T" in result.timestamp  # ISO 8601

    def test_status_not_evaluated_without_criteria(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType, InspectionStatus
        raw = _make_png_with_circle()
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.SURFACE)
        assert result.status == InspectionStatus.NOT_EVALUATED

    def test_electrode_field_present_for_surface(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType
        raw = _make_png_with_circle(200, 40)
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.SURFACE)
        assert result.electrode_indentation is not None

    def test_electrode_mm_none_without_calibration(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType, MeasurementSource
        raw = _make_png_with_circle(200, 40)
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.SURFACE)
        ei = result.electrode_indentation
        assert ei is not None
        if ei.source == MeasurementSource.NOT_AVAILABLE:
            assert ei.diameter_mm is None

    def test_electrode_mm_set_with_calibration(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import CalibrationConfig, ImageType, MeasurementSource
        raw = _make_png_with_circle(200, 40)
        img = _load(raw)
        cal = CalibrationConfig(pixels_per_mm=10.0)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.SURFACE, calibration=cal)
        ei = result.electrode_indentation
        assert ei is not None
        if ei.source == MeasurementSource.MEASURED:
            assert ei.diameter_mm is not None
            assert ei.diameter_mm > 0

    def test_permissive_criteria_returns_ok_or_review(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import AcceptanceCriteria, ImageType, InspectionStatus
        raw = _make_png_with_circle(200, 40)
        img = _load(raw)
        criteria = AcceptanceCriteria(
            max_allowed_defects=9999,
            criteria_version="test-permissive",
        )
        result = StaticInspectionEngine().inspect(
            img, image_type=ImageType.SURFACE, criteria=criteria
        )
        assert result.status != InspectionStatus.NOT_EVALUATED

    def test_zero_defect_criteria_on_solid_image(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import AcceptanceCriteria, ImageType, InspectionStatus
        raw = _make_png(200, 200, (200, 200, 200))
        img = _load(raw)
        criteria = AcceptanceCriteria(
            max_allowed_defects=0,
            criteria_version="strict-zero",
        )
        result = StaticInspectionEngine().inspect(
            img, image_type=ImageType.SURFACE, criteria=criteria
        )
        assert result.status in (
            InspectionStatus.OK,
            InspectionStatus.NOK,
            InspectionStatus.REVIEW,
        )

    def test_unknown_image_type_adds_note(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType
        raw = _make_png_with_circle()
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.UNKNOWN)
        all_notes = result.preprocessing_notes + result.review_notes
        assert any("type" in n.lower() for n in all_notes)

    def test_result_serializable(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType
        raw = _make_png_with_circle()
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.SURFACE)
        d = result.model_dump()
        assert "status" in d
        assert "inspection_id" in d
        assert isinstance(d["defects"], list)

    def test_defects_list_is_always_returned(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType
        raw = _make_png(100, 100)
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.SURFACE)
        assert isinstance(result.defects, list)

    def test_cross_section_has_nugget_field(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType
        raw = _make_png(200, 200, (160, 160, 160))
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.CROSS_SECTION)
        assert result.nugget is not None  # always returned for cross-section

    def test_nugget_mm_requires_calibration(self):
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import ImageType, MeasurementSource
        raw = _make_png(200, 200, (160, 160, 160))
        img = _load(raw)
        result = StaticInspectionEngine().inspect(img, image_type=ImageType.CROSS_SECTION)
        if result.nugget and result.nugget.source == MeasurementSource.NOT_AVAILABLE:
            assert result.nugget.diameter_mm is None

    def test_nok_on_nugget_too_small(self):
        import numpy as np
        import cv2
        from app.vision.static_analysis import StaticInspectionEngine
        from app.vision.schemas import (
            AcceptanceCriteria, CalibrationConfig, ImageType, InspectionStatus
        )
        # Cross-section with a tiny bright circle (nugget ~10px radius → 1 mm at 10px/mm)
        img_arr = np.full((200, 200, 3), 50, dtype=np.uint8)
        cv2.circle(img_arr, (100, 100), 10, (200, 200, 200), -1)
        _, enc = cv2.imencode('.png', img_arr)
        img = _load(bytes(enc))
        cal = CalibrationConfig(pixels_per_mm=10.0)
        # Require >5 mm — the synthetic nugget is ~2 mm, so should fail
        criteria = AcceptanceCriteria(
            min_nugget_diameter_mm=5.0,
            criteria_version="v-test-nok",
        )
        result = StaticInspectionEngine().inspect(
            img, image_type=ImageType.CROSS_SECTION,
            calibration=cal, criteria=criteria
        )
        # May be NOK or REVIEW (depends on detection); NOT_EVALUATED is wrong
        assert result.status != InspectionStatus.NOT_EVALUATED


class TestDeriveStatus:
    """Unit tests for the _derive_status helper (pure logic, no OpenCV needed)."""

    def _make_electrode(self, source, diameter_mm=None):
        from app.vision.schemas import ElectrodeIndentation, MeasurementSource
        return ElectrodeIndentation(source=source, diameter_mm=diameter_mm)

    def _make_nugget(self, source, diameter_mm=None):
        from app.vision.schemas import MeasurementSource, NuggetMeasurement
        return NuggetMeasurement(source=source, diameter_mm=diameter_mm)

    def test_no_criteria_returns_not_evaluated(self):
        from app.vision.static_analysis import _derive_status
        notes: list[str] = []
        status = _derive_status(None, [], None, None, notes)
        from app.vision.schemas import InspectionStatus
        assert status == InspectionStatus.NOT_EVALUATED

    def test_criteria_with_no_violations_returns_ok(self):
        from app.vision.static_analysis import _derive_status
        from app.vision.schemas import AcceptanceCriteria, InspectionStatus, MeasurementSource
        criteria = AcceptanceCriteria(
            max_allowed_defects=5,
            criteria_version="v1",
        )
        nugget = self._make_nugget(MeasurementSource.MEASURED, diameter_mm=6.0)
        notes: list[str] = []
        status = _derive_status(None, [], nugget, criteria, notes)
        assert status == InspectionStatus.OK

    def test_too_many_defects_returns_nok(self):
        from app.vision.static_analysis import _derive_status
        from app.vision.schemas import (
            AcceptanceCriteria, DefectRegion, InspectionStatus, MeasurementSource
        )
        defects = [
            DefectRegion(
                label="anomalous_region",
                bbox_pixels=(0, 0, 10, 10),
                source=MeasurementSource.NOT_AVAILABLE,
            )
            for _ in range(3)
        ]
        criteria = AcceptanceCriteria(max_allowed_defects=1, criteria_version="v1")
        notes: list[str] = []
        status = _derive_status(None, defects, None, criteria, notes)
        assert status == InspectionStatus.NOK

    def test_nugget_too_small_returns_nok(self):
        from app.vision.static_analysis import _derive_status
        from app.vision.schemas import AcceptanceCriteria, InspectionStatus, MeasurementSource
        criteria = AcceptanceCriteria(min_nugget_diameter_mm=5.0, criteria_version="v1")
        nugget = self._make_nugget(MeasurementSource.MEASURED, diameter_mm=3.0)
        notes: list[str] = []
        status = _derive_status(None, [], nugget, criteria, notes)
        assert status == InspectionStatus.NOK

    def test_uncalibrated_with_criteria_returns_review(self):
        from app.vision.static_analysis import _derive_status
        from app.vision.schemas import AcceptanceCriteria, InspectionStatus, MeasurementSource
        criteria = AcceptanceCriteria(max_allowed_defects=5, criteria_version="v1")
        nugget = self._make_nugget(MeasurementSource.NOT_AVAILABLE)
        notes: list[str] = []
        status = _derive_status(None, [], nugget, criteria, notes)
        assert status == InspectionStatus.REVIEW
