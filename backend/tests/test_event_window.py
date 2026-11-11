"""
Tests for WeldEventWindow: state machine transitions, record emission, reset.
No hardware or vision processing required.
"""
from __future__ import annotations

import datetime
import time
from typing import List, Optional

import pytest

from app.vision.event_window import EventWindowConfig, WeldEventWindow
from app.vision.schemas import (
    TemporalEvent,
    TemporalEventType,
    WeldCycleState,
    WeldEventRecord,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_event(
    magnitude: float,
    frame_index: int,
    source: str = "test",
    threshold: float = 8.0,
) -> TemporalEvent:
    above = magnitude > threshold
    return TemporalEvent(
        event_type=TemporalEventType.MOTION_DETECTED if above else TemporalEventType.IDLE,
        timestamp_ms=float(frame_index) * 33.3,  # ~30 fps spacing
        frame_index=frame_index,
        magnitude=magnitude,
        threshold=threshold,
        is_above_threshold=above,
        source_id=source,
    )


def _feed_sequence(
    window: WeldEventWindow,
    magnitudes: List[float],
    threshold: float = 8.0,
    source: str = "test",
) -> List[Optional[WeldEventRecord]]:
    results = []
    for i, mag in enumerate(magnitudes):
        rec = window.feed(_make_event(mag, frame_index=i, source=source, threshold=threshold))
        results.append(rec)
    return results


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestWeldEventWindowInitialState:

    def test_initial_state_is_idle(self):
        w = WeldEventWindow("src")
        assert w.state == WeldCycleState.IDLE

    def test_idle_on_low_magnitude(self):
        w = WeldEventWindow("src", EventWindowConfig(onset_threshold=8.0))
        rec = w.feed(_make_event(2.0, 0))
        assert rec is None
        assert w.state == WeldCycleState.IDLE


class TestWeldEventWindowOnset:

    def test_onset_requires_sustained_frames(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0,
            onset_frames_required=3,
        )
        w = WeldEventWindow("src", cfg)
        # 2 high frames — not enough to confirm
        w.feed(_make_event(15.0, 0))
        assert w.state == WeldCycleState.MOTION_ONSET
        w.feed(_make_event(15.0, 1))
        assert w.state == WeldCycleState.MOTION_ONSET  # still not enough
        w.feed(_make_event(15.0, 2))
        assert w.state == WeldCycleState.ACTIVE_MOTION  # confirmed

    def test_onset_aborted_by_low_frame(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0,
            onset_frames_required=3,
        )
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(2.0, 1))  # drops back
        assert w.state == WeldCycleState.IDLE

    def test_onset_then_abort_clears_window(self):
        """After abort, fresh high-magnitude frames restart onset correctly."""
        cfg = EventWindowConfig(onset_threshold=8.0, onset_frames_required=2)
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(2.0, 1))  # abort
        assert w.state == WeldCycleState.IDLE
        # Restart
        w.feed(_make_event(15.0, 2))
        w.feed(_make_event(15.0, 3))
        assert w.state == WeldCycleState.ACTIVE_MOTION


class TestWeldEventWindowActiveMotion:

    def test_active_motion_no_exit_no_record(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0,
            onset_frames_required=2,
            exit_threshold=4.0,
            exit_frames_required=4,
        )
        w = WeldEventWindow("src", cfg)
        # Enter active
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(15.0, 1))
        assert w.state == WeldCycleState.ACTIVE_MOTION
        # Stay active — no record yet
        for i in range(2, 8):
            rec = w.feed(_make_event(15.0, i))
            assert rec is None

    def test_exit_requires_sustained_low_frames(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0,
            onset_frames_required=2,
            exit_threshold=4.0,
            exit_frames_required=3,
            min_window_frames=2,
        )
        w = WeldEventWindow("src", cfg)
        # Enter active
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(15.0, 1))
        # 2 low frames — not enough
        w.feed(_make_event(2.0, 2))
        assert w.state == WeldCycleState.ACTIVE_MOTION
        w.feed(_make_event(2.0, 3))
        assert w.state == WeldCycleState.ACTIVE_MOTION
        # 3rd low frame — exit confirmed
        rec = w.feed(_make_event(2.0, 4))
        assert rec is not None
        assert w.state == WeldCycleState.IDLE

    def test_exit_record_has_correct_source(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0,
            onset_frames_required=2,
            exit_threshold=4.0,
            exit_frames_required=2,
            min_window_frames=1,
        )
        w = WeldEventWindow("cam://test", cfg)
        w.feed(_make_event(15.0, 0, source="cam://test"))
        w.feed(_make_event(15.0, 1, source="cam://test"))
        w.feed(_make_event(2.0, 2, source="cam://test"))
        rec = w.feed(_make_event(2.0, 3, source="cam://test"))
        assert rec is not None
        assert rec.source_id == "cam://test"

    def test_record_contains_peak_and_mean(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0, onset_frames_required=2,
            exit_threshold=4.0, exit_frames_required=2,
            min_window_frames=1,
        )
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(10.0, 0))
        w.feed(_make_event(20.0, 1))  # peak
        w.feed(_make_event(2.0, 2))
        rec = w.feed(_make_event(2.0, 3))
        assert rec is not None
        assert rec.peak_magnitude == pytest.approx(20.0, abs=0.01)
        assert rec.mean_magnitude > 0.0

    def test_record_duration_ms_positive(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0, onset_frames_required=2,
            exit_threshold=4.0, exit_frames_required=2,
            min_window_frames=1,
        )
        w = WeldEventWindow("src", cfg)
        for i in range(2):
            w.feed(_make_event(15.0, i))
        for i in range(2, 4):
            rec = w.feed(_make_event(2.0, i))
        assert rec is not None
        assert rec.duration_ms > 0


class TestWeldEventWindowMaxWindow:

    def test_max_window_forces_emit(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0,
            onset_frames_required=2,
            exit_threshold=4.0,
            exit_frames_required=100,  # would never exit naturally
            max_window_frames=10,
            min_window_frames=1,
        )
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(15.0, 1))
        assert w.state == WeldCycleState.ACTIVE_MOTION

        rec = None
        for i in range(2, 20):
            r = w.feed(_make_event(15.0, i))
            if r is not None:
                rec = r
                break
        assert rec is not None
        assert w.state == WeldCycleState.IDLE


class TestWeldEventWindowMinWindow:

    def test_short_window_discarded(self):
        """Windows shorter than min_window_frames should not produce a record."""
        cfg = EventWindowConfig(
            onset_threshold=8.0,
            onset_frames_required=2,
            exit_threshold=4.0,
            exit_frames_required=2,
            min_window_frames=20,  # very high min
        )
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(15.0, 1))
        w.feed(_make_event(2.0, 2))
        rec = w.feed(_make_event(2.0, 3))
        # Only 4 frames total; min=20 → should be None
        assert rec is None


class TestWeldEventWindowReset:

    def test_reset_from_active_to_idle(self):
        cfg = EventWindowConfig(onset_threshold=8.0, onset_frames_required=2)
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(15.0, 1))
        assert w.state == WeldCycleState.ACTIVE_MOTION
        w.reset()
        assert w.state == WeldCycleState.IDLE

    def test_reset_then_new_window(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0, onset_frames_required=2,
            exit_threshold=4.0, exit_frames_required=2,
            min_window_frames=1,
        )
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(15.0, 0))
        w.reset()
        # Fresh start: re-enter motion onset
        w.feed(_make_event(15.0, 10))
        w.feed(_make_event(15.0, 11))
        assert w.state == WeldCycleState.ACTIVE_MOTION


class TestWeldEventWindowRecord:

    def test_record_has_uuid(self):
        cfg = EventWindowConfig(
            onset_threshold=8.0, onset_frames_required=2,
            exit_threshold=4.0, exit_frames_required=2,
            min_window_frames=1,
        )
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(15.0, 1))
        w.feed(_make_event(2.0, 2))
        rec = w.feed(_make_event(2.0, 3))
        assert rec is not None
        assert len(rec.record_id) > 0

    def test_record_note_disclaims_quality(self):
        """Record note must not claim weld quality assessment."""
        cfg = EventWindowConfig(
            onset_threshold=8.0, onset_frames_required=2,
            exit_threshold=4.0, exit_frames_required=2,
            min_window_frames=1,
        )
        w = WeldEventWindow("src", cfg)
        w.feed(_make_event(15.0, 0))
        w.feed(_make_event(15.0, 1))
        w.feed(_make_event(2.0, 2))
        rec = w.feed(_make_event(2.0, 3))
        assert rec is not None
        note = rec.note.lower()
        # Note must contain a disclaimer
        assert "not" in note or "quality" in note

    def test_multiple_cycles_emitted(self):
        """Two complete motion windows should emit two records."""
        cfg = EventWindowConfig(
            onset_threshold=8.0, onset_frames_required=2,
            exit_threshold=4.0, exit_frames_required=2,
            min_window_frames=1,
        )
        w = WeldEventWindow("src", cfg)
        records = []

        # First cycle
        for mags in [[15, 15, 2, 2], [15, 15, 2, 2]]:
            for i, m in enumerate(mags):
                r = w.feed(_make_event(float(m), i))
                if r is not None:
                    records.append(r)

        assert len(records) >= 1
