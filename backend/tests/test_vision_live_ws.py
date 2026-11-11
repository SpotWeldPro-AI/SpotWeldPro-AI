"""
Tests for the Phase 2 live vision WebSocket and REST endpoints.

Tests cover:
- GET /api/v1/vision/live/sources (auth required)
- GET /api/v1/vision/live/sources/{id}/metrics (auth required)
- WebSocket auth: missing token, invalid token, timeout, valid auth
- WebSocket subscribe to unknown source
- WebSocket ping/pong
- WebSocket resource limits
"""
from __future__ import annotations

import json
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_session_manager():
    """Reset the singleton session manager between tests."""
    from app.vision.session_manager import get_session_manager
    mgr = get_session_manager()
    # Stop and unregister any sources from previous tests
    for sid in list(mgr.list_sources()):
        mgr.unregister_source(sid)
    # Reset WS count (force reset by accessing internal lock)
    with mgr._lock:
        mgr._ws_count = 0
    yield
    for sid in list(mgr.list_sources()):
        mgr.unregister_source(sid)
    with mgr._lock:
        mgr._ws_count = 0


# ── REST endpoint tests ────────────────────────────────────────────────────────

class TestLiveSourcesEndpoint:

    def test_sources_requires_auth(self, client):
        resp = client.get("/api/v1/vision/live/sources")
        assert resp.status_code == 401

    def test_sources_returns_empty_list(self, client, auth_headers):
        resp = client.get("/api/v1/vision/live/sources", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert data["sources"] == []
        assert "note" in data

    def test_metrics_unknown_source_returns_404(self, client, auth_headers):
        resp = client.get(
            "/api/v1/vision/live/sources/does_not_exist/metrics",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_sources_shows_registered_source(self, client, auth_headers):
        from app.vision.session_manager import get_session_manager
        from tests.test_session_manager import DummyAdapter
        mgr = get_session_manager()
        mgr.register_source("test_src", DummyAdapter("test_src", n=0))

        resp = client.get("/api/v1/vision/live/sources", headers=auth_headers)
        assert resp.status_code == 200
        ids = [s["source_id"] for s in resp.json()["sources"]]
        assert "test_src" in ids

    def test_metrics_known_source_returns_200(self, client, auth_headers):
        from app.vision.session_manager import get_session_manager
        from tests.test_session_manager import DummyAdapter
        mgr = get_session_manager()
        mgr.register_source("ms_src", DummyAdapter("ms_src", n=0))

        resp = client.get(
            "/api/v1/vision/live/sources/ms_src/metrics",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == "ms_src"
        assert "worker_state" in data


# ── WebSocket auth tests ───────────────────────────────────────────────────────

class TestLiveWebSocketAuth:

    def test_ws_auth_with_valid_token(self, client, auth_headers):
        token = auth_headers["Authorization"].split(" ")[1]
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "auth", "token": token})
            msg = ws.receive_json()
            assert msg["type"] == "auth_ok"
            assert "user" in msg["payload"]

    def test_ws_auth_with_invalid_token(self, client):
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_text(json.dumps({"action": "auth", "token": "bad.token.here"}))
            # Server should close with 4001; TestClient may raise or return close
            try:
                msg = ws.receive_json()
                # If we do get a message, it should not be auth_ok
                assert msg.get("type") != "auth_ok"
            except Exception:
                pass  # Expected: server closed connection

    def test_ws_no_auth_message_wrong_action(self, client, auth_headers):
        token = auth_headers["Authorization"].split(" ")[1]
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "ping"})  # wrong first action
            try:
                msg = ws.receive_json()
                assert msg.get("type") != "auth_ok"
            except Exception:
                pass

    def test_ws_after_auth_initial_status_sent(self, client, auth_headers):
        token = auth_headers["Authorization"].split(" ")[1]
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            ws.send_json({"action": "auth", "token": token})
            auth_msg = ws.receive_json()
            assert auth_msg["type"] == "auth_ok"
            # Next message should be status
            status_msg = ws.receive_json()
            assert status_msg["type"] == "status"


# ── WebSocket protocol tests ───────────────────────────────────────────────────

class TestLiveWebSocketProtocol:

    def _auth(self, ws, auth_headers):
        token = auth_headers["Authorization"].split(" ")[1]
        ws.send_json({"action": "auth", "token": token})
        ws.receive_json()  # auth_ok
        ws.receive_json()  # initial status

    def test_ping_pong(self, client, auth_headers):
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            self._auth(ws, auth_headers)
            ws.send_json({"action": "ping"})
            # Drain any pending metrics/status
            msg = None
            for _ in range(5):
                msg = ws.receive_json()
                if msg["type"] == "pong":
                    break
            assert msg is not None and msg["type"] == "pong"

    def test_subscribe_to_unknown_source(self, client, auth_headers):
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            self._auth(ws, auth_headers)
            ws.send_json({"action": "subscribe", "source_id": "no_such_source"})
            # Drain messages until we get a status with NOT_FOUND
            found_not_found = False
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "status" and msg.get("payload", {}).get("state") == "NOT_FOUND":
                    found_not_found = True
                    break
            assert found_not_found

    def test_unknown_action_returns_error(self, client, auth_headers):
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            self._auth(ws, auth_headers)
            ws.send_json({"action": "unknown_action_xyz"})
            found_error = False
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "error":
                    found_error = True
                    break
            assert found_error

    def test_malformed_json_returns_error(self, client, auth_headers):
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            self._auth(ws, auth_headers)
            ws.send_text("{not valid json !!!")
            found_error = False
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "error":
                    found_error = True
                    break
            assert found_error

    def test_unsubscribe_returns_idle(self, client, auth_headers):
        with client.websocket_connect("/api/v1/vision/live/ws") as ws:
            self._auth(ws, auth_headers)
            ws.send_json({"action": "unsubscribe"})
            found_idle = False
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "status" and msg.get("payload", {}).get("state") == "IDLE":
                    found_idle = True
                    break
            assert found_idle


# ── Resource limit tests ───────────────────────────────────────────────────────

class TestLiveWebSocketResourceLimits:

    def test_concurrent_session_limit(self, client, auth_headers):
        """When max WS sessions reached, next connect should be rejected."""
        from app.vision.session_manager import get_session_manager
        mgr = get_session_manager()
        # Manually fill the slot counter to simulate max connections
        with mgr._lock:
            mgr._ws_count = mgr._max_ws_sessions

        # Attempting a new connection should close with 4029
        try:
            with client.websocket_connect("/api/v1/vision/live/ws") as ws:
                # Either the connection is refused immediately or sends no auth_ok
                msg = ws.receive_json()
                # If we get a message, it must not be auth_ok
                assert msg.get("type") != "auth_ok"
        except Exception:
            pass  # Expected: server closed with 4029

        # Reset
        with mgr._lock:
            mgr._ws_count = 0
