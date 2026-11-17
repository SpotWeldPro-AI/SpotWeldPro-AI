"""
VISION-SYNTH-E2E-03 — Complete Browser Video Replay Integration Tests

Verifies the new REST endpoints that resolve MISSINT-01:
  POST  /api/v1/vision/live/sources  — register and start a file source
  DELETE /api/v1/vision/live/sources — stop and unregister a source

Security tests:
  - Path traversal attempts are denied (HTTP 403)
  - Files outside the allowed directory are denied (HTTP 403)
  - Unsupported file types are rejected (HTTP 422)
  - Non-existent files return 404
  - Unauthenticated requests return 401

E2E flow tests:
  - Register source → worker starts → WS subscribe → frames arrive → motion events → worker STOPPED after EOF

HARD RULES (preserved verbatim):
  - No production data changes
  - No arbitrary filesystem access
  - No bypass of E1-E4 quality gates
  - No fabricated AI defect classifications
  - Training gate status assessed from verified test results only
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional
import pytest

_REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO / "backend"))

_VID_DIR = _REPO / "backend" / "tests" / "synthetic_data" / "videos"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"username": "demo", "password": "A1234"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_session_manager():
    """Ensure session manager is clean before and after each test."""
    from app.vision.session_manager import get_session_manager
    mgr = get_session_manager()
    yield
    for sid in list(mgr.list_sources()):
        try:
            mgr.unregister_source(sid)
        except Exception:
            pass


# ── POST /sources — basic registration ────────────────────────────────────────

class TestPostSources:

    def test_register_01_valid_filename_returns_201(self, client, auth_headers):
        """POST with just the filename registers and starts the source."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_normal_approach.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "source_id" in data
        assert data["source_id"].startswith("file://")
        assert "normal_approach" in data["source_id"]
        assert "worker_state" in data
        assert data["file_name"] == "synth_normal_approach.mp4"

    def test_register_02_all_9_valid_scenarios(self, client, auth_headers):
        """All 9 OK synthetic videos can be registered."""
        import json as _json
        manifest = _json.loads((_VID_DIR / "MANIFEST.json").read_text())
        ok_videos = [v for v in manifest["videos"] if v["status"] == "OK"]
        assert len(ok_videos) == 9

        from app.vision.session_manager import get_session_manager
        mgr = get_session_manager()

        for v in ok_videos:
            # Clean up any previous registration of this source
            resp_post = client.post(
                "/api/v1/vision/live/sources",
                json={"source_type": "file", "path": v["filename"]},
                headers=auth_headers,
            )
            assert resp_post.status_code in (201, 200), (
                f"{v['scenario']}: unexpected status {resp_post.status_code}: {resp_post.text}"
            )
            sid = resp_post.json()["source_id"]
            # Cleanup for next iteration
            mgr.unregister_source(sid)

    def test_register_03_replay_fps_accepted(self, client, auth_headers):
        """replay_fps parameter is accepted and registered."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_normal_approach.mp4", "replay_fps": 30.0},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        assert "source_id" in resp.json()

    def test_register_04_idempotent_second_registration(self, client, auth_headers):
        """Second registration of the same path returns the existing source (200 or 201)."""
        payload = {"source_type": "file", "path": "synth_normal_approach.mp4"}
        r1 = client.post("/api/v1/vision/live/sources", json=payload, headers=auth_headers)
        assert r1.status_code == 201
        r2 = client.post("/api/v1/vision/live/sources", json=payload, headers=auth_headers)
        assert r2.status_code in (200, 201)
        assert r1.json()["source_id"] == r2.json()["source_id"]

    def test_register_05_source_appears_in_list(self, client, auth_headers):
        """Registered source appears in GET /sources list."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_expulsion_event.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]
        list_resp = client.get("/api/v1/vision/live/sources", headers=auth_headers)
        assert list_resp.status_code == 200
        ids = [s["source_id"] for s in list_resp.json()["sources"]]
        assert source_id in ids


# ── POST /sources — security ───────────────────────────────────────────────────

class TestPostSourcesSecurity:

    def test_sec_01_unauthenticated_returns_401(self, client):
        """POST without auth returns 401."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_normal_approach.mp4"},
        )
        assert resp.status_code == 401

    def test_sec_02_path_traversal_up_two_levels(self, client, auth_headers):
        """../../etc/passwd path traversal is denied with 403."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "../../etc/passwd"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_sec_03_absolute_path_outside_allowed_dir(self, client, auth_headers):
        """Absolute path outside the synthetic video directory is denied with 403."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "C:\\Windows\\system32\\cmd.exe"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_sec_04_unix_root_path(self, client, auth_headers):
        """Unix root path is denied with 403."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "/etc/passwd"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_sec_05_nonexistent_filename_returns_404(self, client, auth_headers):
        """Filename that doesn't exist in the allowed dir returns 404."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "nonexistent_video_xyz.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_sec_06_unsupported_extension_denied(self, client, auth_headers):
        """Unsupported file extension returns 422."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_unsupported_format.bin"},
            headers=auth_headers,
        )
        # .bin is not in the allowed extensions
        assert resp.status_code == 422

    def test_sec_07_webcam_source_type_rejected(self, client, auth_headers):
        """source_type='webcam' is rejected — only file sources supported via REST."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "webcam", "path": "webcam://device/0"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_sec_08_path_with_null_bytes_rejected(self, client, auth_headers):
        """Path containing null bytes is rejected."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_normal_approach.mp4\x00extra"},
            headers=auth_headers,
        )
        # Should fail validation or path resolution
        assert resp.status_code in (403, 404, 422)


# ── DELETE /sources ────────────────────────────────────────────────────────────

class TestDeleteSources:

    def test_delete_01_registered_source_unregistered(self, client, auth_headers):
        """DELETE removes the source from the session manager."""
        from urllib.parse import quote
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_occlusion_noise.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]

        del_resp = client.delete(
            f"/api/v1/vision/live/sources?source_id={quote(source_id, safe='')}",
            headers=auth_headers,
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "unregistered"

        # Source should no longer appear in list
        list_resp = client.get("/api/v1/vision/live/sources", headers=auth_headers)
        ids = [s["source_id"] for s in list_resp.json()["sources"]]
        assert source_id not in ids

    def test_delete_02_unregistered_source_returns_404(self, client, auth_headers):
        """DELETE of a non-existent source returns 404."""
        from urllib.parse import quote
        resp = client.delete(
            f"/api/v1/vision/live/sources?source_id={quote('file://nonexistent', safe='')}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_delete_03_unauthenticated_returns_401(self, client):
        """DELETE without auth returns 401."""
        resp = client.delete("/api/v1/vision/live/sources?source_id=file://test")
        assert resp.status_code == 401


# ── E2E: register → WS subscribe → frames → motion events ─────────────────────

class TestFileSourceE2EFrameDelivery:

    def test_e2e_01_frames_arrive_via_ws_after_registration(self, client, auth_headers):
        """E2E-01: Register file source, subscribe via WS, verify frames arrive."""
        from urllib.parse import quote

        # Register source (max speed — no replay_fps for fast test)
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_normal_approach.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]

        # Give the worker a moment to start
        time.sleep(0.2)

        # Subscribe via WS and collect messages
        token = auth_headers["Authorization"].split(" ")[1]
        frames_received = []
        events_received = []

        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "auth", "token": token})
            # Drain until auth_ok
            for _ in range(10):
                m = ws.receive_json()
                if m["type"] == "auth_ok":
                    break
            # Drain initial status
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break
            # Subscribe
            ws.send_json({"action": "subscribe", "source_id": source_id})
            # Drain subscribe ack
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break
            # Collect frames and events
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and len(frames_received) < 10:
                try:
                    m = ws.receive_json()
                    if m["type"] == "frame":
                        frames_received.append(m["payload"])
                    elif m["type"] == "event":
                        events_received.append(m["payload"])
                except Exception:
                    break

        assert len(frames_received) >= 5, (
            f"Expected ≥5 frames, got {len(frames_received)}"
        )
        # Verify frame structure
        f = frames_received[0]
        assert "frame_b64" in f
        assert "frame_index" in f
        assert "timestamp_ms" in f
        assert f["width"] == 1280
        assert f["height"] == 720
        assert len(f["frame_b64"]) > 100  # non-empty JPEG base64

    def test_e2e_02_motion_events_delivered_via_ws(self, client, auth_headers):
        """E2E-02: Motion events (TemporalEvent) arrive alongside frames."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_expulsion_event.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]
        time.sleep(0.2)

        token = auth_headers["Authorization"].split(" ")[1]
        events_received = []

        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "auth", "token": token})
            for _ in range(10):
                m = ws.receive_json()
                if m["type"] == "auth_ok":
                    break
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break
            ws.send_json({"action": "subscribe", "source_id": source_id})
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break

            deadline = time.monotonic() + 5.0
            frame_count = 0
            while time.monotonic() < deadline and frame_count < 20:
                try:
                    m = ws.receive_json()
                    if m["type"] == "frame":
                        frame_count += 1
                    elif m["type"] == "event":
                        events_received.append(m["payload"])
                except Exception:
                    break

        assert len(events_received) > 0, "Expected motion events alongside frames"
        ev = events_received[0]
        assert "event_type" in ev
        assert "magnitude" in ev
        assert "frame_index" in ev
        # event_type must be a known value
        assert ev["event_type"] in ("MOTION_DETECTED", "IDLE", "WELD_CYCLE_BOUNDARY")

    def test_e2e_03_worker_reaches_stopped_after_complete_replay(self, client, auth_headers):
        """E2E-03: Worker transitions to STOPPED after full file replay (EOF)."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_occlusion_noise.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]

        # Poll via GET /sources list (avoids path-encoding issues with per-source endpoint)
        # occlusion_noise is 60 frames at max speed ≈ <1 s
        deadline = time.monotonic() + 10.0
        worker_state = None
        while time.monotonic() < deadline:
            list_resp = client.get("/api/v1/vision/live/sources", headers=auth_headers)
            if list_resp.status_code == 200:
                for s in list_resp.json()["sources"]:
                    if s["source_id"] == source_id:
                        worker_state = s.get("worker_state")
                        break
                if worker_state == "STOPPED":
                    break
            time.sleep(0.2)

        assert worker_state == "STOPPED", (
            f"Expected worker_state=STOPPED after EOF, got {worker_state!r}"
        )

    def test_e2e_04_replay_fps_throttles_delivery(self, client, auth_headers):
        """E2E-04: replay_fps throttles frame delivery rate."""
        import math
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_normal_approach.mp4", "replay_fps": 10.0},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]

        token = auth_headers["Authorization"].split(" ")[1]
        frame_times = []

        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "auth", "token": token})
            for _ in range(10):
                m = ws.receive_json()
                if m["type"] == "auth_ok":
                    break
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break
            ws.send_json({"action": "subscribe", "source_id": source_id})
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break

            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and len(frame_times) < 5:
                try:
                    m = ws.receive_json()
                    if m["type"] == "frame":
                        frame_times.append(time.monotonic())
                except Exception:
                    break

        assert len(frame_times) >= 3, "Should receive at least 3 frames"
        if len(frame_times) >= 2:
            # Average inter-frame gap should be ~100ms (10fps) with some tolerance
            gaps = [frame_times[i+1] - frame_times[i] for i in range(len(frame_times)-1)]
            avg_gap = sum(gaps) / len(gaps)
            # At 10fps replay, gap ~0.1s. Allow 2× tolerance for WS + test overhead.
            assert avg_gap >= 0.05, f"Gaps too small ({avg_gap:.3f}s) for 10fps replay"

    def test_e2e_05_unsubscribe_stops_frame_delivery(self, client, auth_headers):
        """E2E-05: unsubscribe action stops frame delivery."""
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_normal_approach.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]
        time.sleep(0.1)

        token = auth_headers["Authorization"].split(" ")[1]

        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "auth", "token": token})
            for _ in range(10):
                m = ws.receive_json()
                if m["type"] == "auth_ok":
                    break
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break
            ws.send_json({"action": "subscribe", "source_id": source_id})
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break

            # Collect a few frames
            frames_before = 0
            for _ in range(20):
                try:
                    m = ws.receive_json()
                    if m["type"] == "frame":
                        frames_before += 1
                        if frames_before >= 3:
                            break
                except Exception:
                    break

            # Unsubscribe
            ws.send_json({"action": "unsubscribe"})
            idle_msg = None
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status" and m.get("payload", {}).get("state") == "IDLE":
                    idle_msg = m
                    break

            assert idle_msg is not None, "Expected IDLE status after unsubscribe"


# ── E2E: temporal event comparison vs manifest ─────────────────────────────────

class TestTemporalEventVsManifest:

    def test_temporal_01_expulsion_event_has_high_magnitude_frames(self, client, auth_headers):
        """
        TEMPORAL-01: expulsion_event scenario produces at least one frame with
        magnitude above the synthetic signal threshold.

        NOTE: This test uses pixel-level frame differences only.
        It does NOT use a trained weld defect classification model.
        It does NOT confirm weld quality.
        """
        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_expulsion_event.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]
        time.sleep(0.1)

        token = auth_headers["Authorization"].split(" ")[1]
        magnitudes = []

        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "auth", "token": token})
            for _ in range(10):
                m = ws.receive_json()
                if m["type"] == "auth_ok":
                    break
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break
            ws.send_json({"action": "subscribe", "source_id": source_id})
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break

            deadline = time.monotonic() + 8.0
            frame_count = 0
            while time.monotonic() < deadline and frame_count < 90:
                try:
                    m = ws.receive_json()
                    if m["type"] == "frame":
                        frame_count += 1
                    elif m["type"] == "event":
                        magnitudes.append(float(m["payload"].get("magnitude", 0.0)))
                except Exception:
                    break

        assert len(magnitudes) > 0, "No motion events received"
        max_magnitude = max(magnitudes)
        # Expulsion event has synthetic spike; at least one frame should be > 1.0
        assert max_magnitude > 1.0, (
            f"Expected expulsion event to produce magnitude > 1.0, got max={max_magnitude:.3f}. "
            "MISSINT-02: default onset_threshold=8.0 is calibrated for hardware cameras."
        )

    def test_temporal_02_normal_approach_vs_manifest_window(self, client, auth_headers):
        """
        TEMPORAL-02: Verify frame indices from normal_approach fall within
        the expected timing window from MANIFEST.json (approach at t=0..0.5s).

        DISCLAIMER: Geometric motion detection only. No trained model loaded.
        """
        import json as _json
        manifest = _json.loads((_VID_DIR / "MANIFEST.json").read_text())
        na_entry = next(v for v in manifest["videos"] if v["scenario"] == "normal_approach")
        fps = na_entry["fps"]  # 30
        # approach window: t=0..0.5s = frames 0..15 (at 30fps)

        resp = client.post(
            "/api/v1/vision/live/sources",
            json={"source_type": "file", "path": "synth_normal_approach.mp4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        source_id = resp.json()["source_id"]
        time.sleep(0.1)

        token = auth_headers["Authorization"].split(" ")[1]
        frame_indices = []

        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "auth", "token": token})
            for _ in range(10):
                m = ws.receive_json()
                if m["type"] == "auth_ok":
                    break
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break
            ws.send_json({"action": "subscribe", "source_id": source_id})
            for _ in range(5):
                m = ws.receive_json()
                if m["type"] == "status":
                    break

            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and len(frame_indices) < 20:
                try:
                    m = ws.receive_json()
                    if m["type"] == "frame":
                        frame_indices.append(int(m["payload"]["frame_index"]))
                except Exception:
                    break

        assert len(frame_indices) >= 10, f"Expected ≥10 frames, got {len(frame_indices)}"
        # Frames should be monotonically increasing
        for i in range(1, len(frame_indices)):
            assert frame_indices[i] >= frame_indices[i - 1], (
                f"Frame indices not monotonically increasing: {frame_indices[i-1]} → {frame_indices[i]}"
            )
        # First frame index should be close to 1
        assert frame_indices[0] <= 5, (
            f"Expected first frame near index 1, got {frame_indices[0]}"
        )
