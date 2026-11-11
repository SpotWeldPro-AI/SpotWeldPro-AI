"""
Sliding weld-event window: heuristic weld-cycle boundary detection.

IMPORTANT:
- This module uses motion-magnitude thresholds to detect onset and end of motion
  windows. It does NOT assess weld quality, detect defects, or confirm weld presence.
- WeldEventRecord.state == MOTION_END indicates the end of a motion window only.
  It must not be interpreted as "weld complete" or "weld OK/NOK".
- Validation against destructive testing is required before this output is used
  for any production or quality decision.

State machine (per source):
  IDLE → (magnitude > onset_threshold) → MOTION_ONSET
  MOTION_ONSET → (sustained N frames) → ACTIVE_MOTION
  ACTIVE_MOTION → (magnitude < exit_threshold for M consecutive frames) → MOTION_END
  MOTION_END → emits WeldEventRecord → IDLE
"""
from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

from app.vision.schemas import (
    TemporalEvent,
    TemporalEventType,
    WeldCycleState,
    WeldEventRecord,
)


@dataclass
class EventWindowConfig:
    onset_threshold: float = 8.0        # magnitude to enter MOTION_ONSET
    exit_threshold: float = 4.0         # magnitude to start exit countdown
    onset_frames_required: int = 3      # consecutive above-threshold frames to confirm motion
    exit_frames_required: int = 5       # consecutive below-threshold frames to close window
    min_window_frames: int = 5          # discard windows shorter than this
    max_window_frames: int = 300        # hard limit: close and emit if exceeded


class WeldEventWindow:
    """
    Accumulates TemporalEvents and emits WeldEventRecord when a motion window closes.

    Thread safety: not thread-safe. Use one instance per source, called from
    the same thread or under an external lock.
    """

    def __init__(self, source_id: str, config: Optional[EventWindowConfig] = None) -> None:
        self._source_id = source_id
        self._cfg = config or EventWindowConfig()
        self._state = WeldCycleState.IDLE
        self._window: Deque[TemporalEvent] = deque()
        self._onset_count: int = 0
        self._exit_count: int = 0

    @property
    def state(self) -> WeldCycleState:
        return self._state

    def feed(self, event: TemporalEvent) -> Optional[WeldEventRecord]:
        """
        Process one TemporalEvent through the state machine.
        Returns a WeldEventRecord when a window closes, otherwise None.
        """
        if self._state == WeldCycleState.IDLE:
            return self._handle_idle(event)
        elif self._state == WeldCycleState.MOTION_ONSET:
            return self._handle_onset(event)
        elif self._state == WeldCycleState.ACTIVE_MOTION:
            return self._handle_active(event)
        return None

    def reset(self) -> None:
        """Reset state machine (e.g. after source reconnect)."""
        self._state = WeldCycleState.IDLE
        self._window.clear()
        self._onset_count = 0
        self._exit_count = 0

    # ── State handlers ────────────────────────────────────────────────────────

    def _handle_idle(self, event: TemporalEvent) -> Optional[WeldEventRecord]:
        if event.magnitude > self._cfg.onset_threshold:
            self._state = WeldCycleState.MOTION_ONSET
            self._window.clear()
            self._window.append(event)
            self._onset_count = 1
            self._exit_count = 0
        return None

    def _handle_onset(self, event: TemporalEvent) -> Optional[WeldEventRecord]:
        self._window.append(event)
        if event.magnitude > self._cfg.onset_threshold:
            self._onset_count += 1
            if self._onset_count >= self._cfg.onset_frames_required:
                self._state = WeldCycleState.ACTIVE_MOTION
                self._exit_count = 0
        else:
            # Motion didn't sustain — go back to IDLE, discard window
            self._state = WeldCycleState.IDLE
            self._window.clear()
            self._onset_count = 0
        return None

    def _handle_active(self, event: TemporalEvent) -> Optional[WeldEventRecord]:
        self._window.append(event)

        if event.magnitude < self._cfg.exit_threshold:
            self._exit_count += 1
        else:
            self._exit_count = 0

        over_max = len(self._window) >= self._cfg.max_window_frames
        exit_confirmed = self._exit_count >= self._cfg.exit_frames_required

        if exit_confirmed or over_max:
            rec = self._emit_record(WeldCycleState.MOTION_END)
            self._state = WeldCycleState.IDLE
            self._window.clear()
            self._onset_count = 0
            self._exit_count = 0
            return rec
        return None

    def _emit_record(self, closing_state: WeldCycleState) -> Optional[WeldEventRecord]:
        events = list(self._window)
        if len(events) < self._cfg.min_window_frames:
            return None  # too short to be meaningful

        mags = [e.magnitude for e in events]
        return WeldEventRecord(
            record_id=str(uuid.uuid4()),
            source_id=self._source_id,
            start_timestamp_ms=events[0].timestamp_ms,
            end_timestamp_ms=events[-1].timestamp_ms,
            duration_ms=events[-1].timestamp_ms - events[0].timestamp_ms,
            frame_count=len(events),
            peak_magnitude=round(max(mags), 4),
            mean_magnitude=round(sum(mags) / len(mags), 4),
            state=closing_state,
        )
