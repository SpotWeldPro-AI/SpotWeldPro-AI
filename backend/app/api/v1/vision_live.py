"""
/api/v1/vision/live — Authenticated live monitoring WebSocket and REST endpoints.

Authentication for WebSocket:
  Since browser WebSocket API does not support custom headers, the client
  must send a JSON auth message as the FIRST message after connecting:
    {"action": "auth", "token": "<JWT access token>"}
  The server validates the token and closes with code 4001 on failure.
  Auth must complete within 10 seconds or the connection is closed.

WebSocket protocol (all messages are JSON):

  Client → Server:
    {"action": "auth",        "token": "..."}        (must be first message)
    {"action": "subscribe",   "source_id": "..."}
    {"action": "unsubscribe", "source_id": "..."}
    {"action": "ping"}

  Server → Client:
    {"type": "auth_ok",   "payload": {"user": "..."}}
    {"type": "status",    "payload": LiveStreamStatus}
    {"type": "frame",     "payload": {"source_id": "...", "frame_b64": "...",
                                      "frame_index": int, "timestamp_ms": float,
                                      "width": int, "height": int}}
    {"type": "event",     "payload": TemporalEvent}
    {"type": "weld_window", "payload": WeldEventRecord}
    {"type": "metrics",   "payload": LiveStreamMetrics}
    {"type": "error",     "payload": {"message": "..."}}
    {"type": "pong"}

IMPORTANT:
  - No automatic PLC actuation is performed by this endpoint.
  - Frame base64 payloads are raw JPEG bytes from the capture adapter.
  - TemporalEvent is frame-differencing only; it does not confirm weld quality.
  - WeldEventRecord is a heuristic motion window; it is not a weld quality result.
  - Inference model is None until a validated model is registered.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.websockets import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.security import decode_token
from app.db.session import get_db as _get_db_ctx
from app.models.entities import User
from app.vision.motion_detection import MotionEventDetector, MotionDetectorConfig
from app.vision.event_window import EventWindowConfig, WeldEventWindow
from app.vision.schemas import (
    LiveStreamMetrics,
    LiveStreamStatus,
    WorkerState,
)
from app.vision.session_manager import (
    LiveSessionManager,
    SessionManagerError,
    get_session_manager,
)

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/vision/live", tags=["Vision - Live Monitoring"])

_WS_AUTH_TIMEOUT_S = 10.0
_METRICS_INTERVAL_S = 1.0   # how often to push metrics updates
_FRAME_POLL_S = 0.033        # ~30 fps poll cadence


# ── REST endpoints ─────────────────────────────────────────────────────────────

@router.get("/sources")
def list_capture_sources(
    _: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List registered capture sources and their current metrics."""
    mgr = get_session_manager()
    source_ids = mgr.list_sources()
    sources = []
    for sid in source_ids:
        try:
            m = mgr.get_metrics(sid)
            sources.append({
                "source_id": sid,
                "worker_state": m.worker_state,
                "fps_actual": m.fps_actual,
                "fps_nominal": m.fps_nominal,
                "frames_total": m.frames_total,
                "frames_dropped": m.frames_dropped,
                "queue_depth": m.queue_depth,
            })
        except SessionManagerError:
            pass

    return {
        "sources": sources,
        "active_ws_sessions": mgr.active_ws_count,
        "note": (
            "No sources are registered. Register a validated CaptureAdapter via "
            "the session manager before connecting."
            if not sources else None
        ),
    }


@router.get("/sources/{source_id}/metrics")
def get_source_metrics(
    source_id: str,
    _: User = Depends(get_current_user),
) -> LiveStreamMetrics:
    mgr = get_session_manager()
    try:
        return mgr.get_metrics(source_id)
    except SessionManagerError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@router.websocket("/ws")
async def live_monitoring_ws(websocket: WebSocket) -> None:
    """
    Authenticated WebSocket for live monitoring.

    Requires auth as first message: {"action": "auth", "token": "<JWT>"}.
    Closes with 4001 on auth failure or timeout.
    Closes with 4029 when the concurrent-session limit is reached.
    """
    mgr = get_session_manager()

    # ── Step 1: Resource limit check (before accepting, to avoid wasted slot)
    try:
        mgr.acquire_ws_slot()
    except SessionManagerError as exc:
        await websocket.accept()
        await websocket.close(code=4029, reason=str(exc))
        return

    await websocket.accept()
    user: Optional[User] = None

    try:
        # ── Step 2: Authenticate via first message
        user = await _authenticate_ws(websocket)
        if user is None:
            return  # close already sent inside _authenticate_ws

        await websocket.send_json({
            "type": "auth_ok",
            "payload": {"user": user.email},
        })

        # ── Step 3: Send initial status
        await _send_status(websocket, mgr, source_id=None)

        # ── Step 4: Main message loop
        subscribed_source: Optional[str] = None
        metrics_countdown = _METRICS_INTERVAL_S
        motion_detector = MotionEventDetector()
        event_window: Optional[WeldEventWindow] = None

        loop_start = asyncio.get_event_loop().time()

        while True:
            # Poll for client messages (non-blocking)
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=_FRAME_POLL_S)
                msg = json.loads(raw)
                subscribed_source, motion_detector, event_window = await _handle_message(
                    websocket, msg, mgr, subscribed_source, motion_detector, event_window
                )
            except asyncio.TimeoutError:
                pass  # Normal — no client message this poll cycle
            except (json.JSONDecodeError, ValueError):
                await websocket.send_json(
                    {"type": "error", "payload": {"message": "Message must be valid JSON."}}
                )
                continue
            except WebSocketDisconnect:
                return

            # Push frame and events if subscribed to an active source
            if subscribed_source is not None and mgr.source_exists(subscribed_source):
                try:
                    worker_metrics = mgr.get_metrics(subscribed_source)
                    if worker_metrics.worker_state == WorkerState.RUNNING:
                        frame = mgr.get_frame(subscribed_source, timeout=0.0)
                        if frame is not None:
                            # Send JPEG as base64
                            await websocket.send_json({
                                "type": "frame",
                                "payload": {
                                    "source_id": subscribed_source,
                                    "frame_b64": base64.b64encode(frame.frame_data).decode(),
                                    "frame_index": frame.frame_index,
                                    "timestamp_ms": frame.timestamp.timestamp() * 1000.0,
                                    "width": frame.width,
                                    "height": frame.height,
                                },
                            })
                            # Run motion detection
                            try:
                                event = motion_detector.detect(frame)
                                await websocket.send_json({
                                    "type": "event",
                                    "payload": event.model_dump(),
                                })
                                # Feed event window
                                if event_window is not None:
                                    record = event_window.feed(event)
                                    if record is not None:
                                        await websocket.send_json({
                                            "type": "weld_window",
                                            "payload": record.model_dump(),
                                        })
                            except Exception as exc:
                                _log.debug("Motion detection error: %s", exc)
                except SessionManagerError:
                    pass

            # Push metrics at interval
            now = asyncio.get_event_loop().time()
            elapsed_since_start = now - loop_start
            if elapsed_since_start >= metrics_countdown:
                metrics_countdown = elapsed_since_start + _METRICS_INTERVAL_S
                await _send_metrics(websocket, mgr, subscribed_source)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        _log.exception("Unexpected error in live WS for user %s: %s", user, exc)
        try:
            await websocket.send_json(
                {"type": "error", "payload": {"message": f"Internal error: {exc}"}}
            )
        except Exception:
            pass
    finally:
        mgr.release_ws_slot()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _authenticate_ws(websocket: WebSocket) -> Optional[User]:
    """
    Wait for the first auth message and validate the JWT token.
    Returns the User on success, None (after closing) on failure.
    """
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=_WS_AUTH_TIMEOUT_S)
    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="Authentication timeout — send auth message first.")
        return None
    except WebSocketDisconnect:
        return None

    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        await websocket.close(code=4001, reason="First message must be valid JSON.")
        return None

    if msg.get("action") != "auth":
        await websocket.close(
            code=4001,
            reason=f"First message must be {{action: auth, token: ...}}, got action={msg.get('action')!r}."
        )
        return None

    token = msg.get("token", "")
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.entities import User

    try:
        email = decode_token(token, "access")
    except (ValueError, Exception):
        await websocket.close(code=4001, reason="Invalid or expired token.")
        return None

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="User not found or inactive.")
            return None
        # Detach from session before returning
        db.expunge(user)

    return user


async def _handle_message(
    websocket: WebSocket,
    msg: dict,
    mgr: LiveSessionManager,
    subscribed_source: Optional[str],
    motion_detector: MotionEventDetector,
    event_window: Optional[WeldEventWindow],
):
    """Process a client action message. Returns updated (subscribed_source, detector, window)."""
    action = msg.get("action", "")

    if action == "ping":
        await websocket.send_json({"type": "pong"})

    elif action == "subscribe":
        sid = msg.get("source_id")
        if sid and mgr.source_exists(sid):
            subscribed_source = sid
            motion_detector.reset()
            event_window = WeldEventWindow(sid)
            await websocket.send_json({
                "type": "status",
                "payload": {
                    "state": "ACTIVE",
                    "source_id": sid,
                    "note": "Subscribed. Receiving frames and motion events.",
                },
            })
        else:
            await websocket.send_json({
                "type": "status",
                "payload": {
                    "state": "NOT_FOUND",
                    "source_id": sid,
                    "note": (
                        f"Source '{sid}' is not registered. "
                        "Call GET /api/v1/vision/live/sources to list available sources."
                    ),
                },
            })

    elif action == "unsubscribe":
        subscribed_source = None
        motion_detector.reset()
        event_window = None
        await websocket.send_json({
            "type": "status",
            "payload": {"state": "IDLE", "source_id": None, "note": "Unsubscribed."},
        })

    else:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": f"Unknown action: {action!r}."},
        })

    return subscribed_source, motion_detector, event_window


async def _send_status(
    websocket: WebSocket,
    mgr: LiveSessionManager,
    source_id: Optional[str],
) -> None:
    sources = mgr.list_sources()
    state = "ACTIVE" if sources else "IDLE"
    metrics = None
    if source_id and mgr.source_exists(source_id):
        metrics = mgr.get_metrics(source_id)

    await websocket.send_json({
        "type": "status",
        "payload": {
            "state": state,
            "source_id": source_id,
            "registered_sources": sources,
            "active_ws_sessions": mgr.active_ws_count,
            "inference_model": None,
            "note": (
                "No sources registered — connect a validated CaptureAdapter via the session manager."
                if not sources
                else f"{len(sources)} source(s) registered. Subscribe to begin receiving frames."
            ),
            "metrics": metrics.model_dump() if metrics else None,
        },
    })


async def _send_metrics(
    websocket: WebSocket,
    mgr: LiveSessionManager,
    source_id: Optional[str],
) -> None:
    if source_id and mgr.source_exists(source_id):
        try:
            m = mgr.get_metrics(source_id)
            await websocket.send_json({
                "type": "metrics",
                "payload": m.model_dump(),
            })
        except SessionManagerError:
            pass
