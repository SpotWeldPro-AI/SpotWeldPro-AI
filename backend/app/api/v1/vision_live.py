"""
/api/v1/vision/live — Live monitoring WebSocket interface.

STATUS: FRAMEWORK ONLY — not production-ready.

This module defines the WebSocket protocol and adapter registry scaffolding.
No capture adapter, trained inference model, or ring buffer is wired up yet.

Requirements for production activation (all must be verified):
  1. A validated CaptureAdapter for the target hardware
  2. A trained, benchmarked weld-cycle segmentation model
     (precision/recall measured on a held-out test set, not training data)
  3. End-to-end latency measured on target hardware under sustained load
  4. Sustained FPS test: target rate held for the full weld cycle duration
  5. Frame-drop characterisation under CPU/network stress
  6. Disconnect/reconnect stress test (e.g. 100 consecutive reconnects)
  7. Memory and resource leak test for a multi-hour run

No automatic PLC actuation is performed by this endpoint. Manual review is
required before any production-line integration.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/vision/live", tags=["Vision - Live Monitoring"])

# In-process adapter registry (Phase 2 will move this to a managed service)
_REGISTERED_SOURCES: Dict[str, Any] = {}


@router.websocket("/ws")
async def live_monitoring_ws(
    websocket: WebSocket,
    source_id: Optional[str] = Query(None, description="Capture source ID to subscribe to"),
) -> None:
    """
    WebSocket endpoint for live monitoring status and event delivery.

    Protocol (all messages are JSON):

    Client → Server:
      {"action": "subscribe", "source_id": "..."}
      {"action": "ping"}

    Server → Client:
      {"type": "status",  "payload": {...}}
      {"type": "event",   "payload": {"event": "weld_cycle_start"|"weld_cycle_end"|"alert", ...}}
      {"type": "alert",   "payload": {"severity": "INFO"|"WARNING"|"CRITICAL", "message": "..."}}
      {"type": "error",   "payload": {"message": "..."}}
      {"type": "pong"}

    Current state: returns a framework-only status frame and echoes messages.
    """
    await websocket.accept()
    try:
        await websocket.send_json({
            "type": "status",
            "payload": {
                "state": "FRAMEWORK_ONLY",
                "message": (
                    "Live monitoring framework is present but no trained model or "
                    "validated capture adapter is active. "
                    "Hardware and software validation is required before production use."
                ),
                "capture_adapter": None,
                "inference_model": None,
                "fps_actual": None,
                "fps_nominal": None,
                "frames_dropped": None,
                "registered_sources": list(_REGISTERED_SOURCES.keys()),
            },
        })
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                await websocket.send_json(
                    {"type": "error", "payload": {"message": "Message must be valid JSON."}}
                )
                continue

            action = msg.get("action", "")
            if action == "ping":
                await websocket.send_json({"type": "pong"})
            elif action == "subscribe":
                sid = msg.get("source_id")
                await websocket.send_json({
                    "type": "status",
                    "payload": {
                        "state": "NOT_IMPLEMENTED",
                        "source_id": sid,
                        "message": (
                            f"Source '{sid}' is not registered. "
                            "Register a validated CaptureAdapter before subscribing."
                        ),
                    },
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "payload": {"message": f"Unknown action: '{action}'."},
                })
    except WebSocketDisconnect:
        pass


@router.get("/sources")
def list_capture_sources() -> Dict[str, Any]:
    """
    List registered capture sources.

    Returns an empty list until concrete CaptureAdapter instances are registered.
    This endpoint is a placeholder for the adapter registry (Phase 2).
    """
    return {
        "sources": [
            {"source_id": sid, "type": type(adapter).__name__}
            for sid, adapter in _REGISTERED_SOURCES.items()
        ],
        "note": (
            "No adapters are registered. "
            "Adapters must be validated on target hardware before registration."
            if not _REGISTERED_SOURCES
            else None
        ),
    }
