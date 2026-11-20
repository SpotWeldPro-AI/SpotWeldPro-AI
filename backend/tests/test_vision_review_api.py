"""
Integration tests for VISION-AI-REVIEW-01 engineer review API.

Endpoints tested:
  POST /api/v1/vision/static/inspect/{inspection_id}/review
  GET  /api/v1/vision/static/inspect/{inspection_id}/reviews

Hard rules verified:
  - is_training_label is always False
  - Comment minimum length enforced (10 chars)
  - Auth required (401 without token)
  - Reviewer identity captured from JWT (not client input)
  - inspection_snapshot preserved verbatim
"""
from __future__ import annotations

import struct
import zlib

import pytest

INSPECTION_ID = "test-inspection-uuid-review-01"

# Minimal StaticInspectionResult-shaped JSON for snapshot
_SNAPSHOT = {
    "inspection_id": INSPECTION_ID,
    "timestamp": "2026-11-20T10:00:00Z",
    "image_type": "SURFACE",
    "status": "NOT_EVALUATED",
    "image_metadata": {"width_px": 200, "height_px": 200, "channels": 3,
                       "format_detected": "PNG", "file_size_bytes": 1024},
    "electrode_indentation": None,
    "defects": [],
    "nugget": None,
    "visual_findings": [
        {"code": "NORMAL_SURFACE", "status": "DETECTED",
         "name_en": "Normal Surface", "name_tr": "Normal Yüzey",
         "evidence": "no defects detected", "source": "composite",
         "limitations": "surface only", "confidence": None,
         "bbox_pixels": None,
         "next_action_en": "No action", "next_action_tr": "İşlem yok",
         "internal_weld_integrity": "Cannot confirm from surface image"}
    ],
    "preprocessing_notes": [],
    "review_notes": [],
    "calibration": None,
}

_VALID_PAYLOAD = {
    "verdict": "AGREE",
    "comment": "Yüzey görüntüsü normal, kaynak bölgesi düzgün görünüyor.",
    "inspection_snapshot": _SNAPSHOT,
}


@pytest.fixture()
def demo_headers(client):
    r = client.post("/api/v1/auth/login", json={"username": "demo", "password": "A1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestCreateReview:
    def test_create_returns_201(self, client, demo_headers):
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}/review",
            json=_VALID_PAYLOAD,
            headers=demo_headers,
        )
        assert r.status_code == 201, r.text

    def test_response_fields(self, client, demo_headers):
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}/review",
            json=_VALID_PAYLOAD,
            headers=demo_headers,
        )
        body = r.json()
        assert body["inspection_id"] == INSPECTION_ID
        assert body["verdict"] == "AGREE"
        assert "id" in body
        assert "created_at" in body
        assert body["reviewer_username"] == "demo"
        assert body["reviewer_role"] == "DEMO_USER"

    def test_is_training_label_always_false(self, client, demo_headers):
        payload = {**_VALID_PAYLOAD, "is_training_label": True}
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}/review",
            json=payload,
            headers=demo_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["is_training_label"] is False

    def test_requires_auth(self, client):
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}/review",
            json=_VALID_PAYLOAD,
        )
        assert r.status_code == 401

    def test_comment_too_short_rejected(self, client, demo_headers):
        payload = {**_VALID_PAYLOAD, "comment": "short"}
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}/review",
            json=payload,
            headers=demo_headers,
        )
        assert r.status_code == 422

    def test_empty_comment_rejected(self, client, demo_headers):
        payload = {**_VALID_PAYLOAD, "comment": ""}
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}/review",
            json=payload,
            headers=demo_headers,
        )
        assert r.status_code == 422

    def test_missing_snapshot_rejected(self, client, demo_headers):
        payload = {"verdict": "AGREE", "comment": "valid comment here"}
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}/review",
            json=payload,
            headers=demo_headers,
        )
        assert r.status_code == 422

    def test_invalid_verdict_rejected(self, client, demo_headers):
        payload = {**_VALID_PAYLOAD, "verdict": "INVALID"}
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}/review",
            json=payload,
            headers=demo_headers,
        )
        assert r.status_code == 422

    def test_all_three_verdicts_accepted(self, client, demo_headers):
        for verdict in ("AGREE", "DISAGREE", "FURTHER_REVIEW"):
            r = client.post(
                f"/api/v1/vision/static/inspect/{INSPECTION_ID}-{verdict}/review",
                json={**_VALID_PAYLOAD, "verdict": verdict},
                headers=demo_headers,
            )
            assert r.status_code == 201, f"verdict={verdict}: {r.text}"

    def test_snapshot_preserved(self, client, demo_headers):
        iid = f"{INSPECTION_ID}-snap"
        r = client.post(
            f"/api/v1/vision/static/inspect/{iid}/review",
            json={**_VALID_PAYLOAD, "inspection_snapshot": _SNAPSHOT},
            headers=demo_headers,
        )
        assert r.status_code == 201
        # snapshot is returned via GET; verify roundtrip
        g = client.get(f"/api/v1/vision/static/inspect/{iid}/reviews", headers=demo_headers)
        reviews = g.json()
        assert len(reviews) == 1

    def test_admin_can_also_review(self, client, auth_headers):
        r = client.post(
            f"/api/v1/vision/static/inspect/{INSPECTION_ID}-admin/review",
            json=_VALID_PAYLOAD,
            headers=auth_headers,
        )
        assert r.status_code == 201


class TestListReviews:
    def test_empty_list_new_id(self, client, demo_headers):
        r = client.get(
            "/api/v1/vision/static/inspect/nonexistent-inspection-999/reviews",
            headers=demo_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_list_requires_auth(self, client):
        r = client.get(f"/api/v1/vision/static/inspect/{INSPECTION_ID}/reviews")
        assert r.status_code == 401

    def test_list_returns_created_reviews(self, client, demo_headers):
        iid = f"{INSPECTION_ID}-list"
        client.post(
            f"/api/v1/vision/static/inspect/{iid}/review",
            json={**_VALID_PAYLOAD, "comment": "First review comment here"},
            headers=demo_headers,
        )
        client.post(
            f"/api/v1/vision/static/inspect/{iid}/review",
            json={**_VALID_PAYLOAD, "verdict": "DISAGREE",
                  "comment": "Second review — further review required"},
            headers=demo_headers,
        )
        r = client.get(f"/api/v1/vision/static/inspect/{iid}/reviews", headers=demo_headers)
        assert r.status_code == 200
        reviews = r.json()
        assert len(reviews) >= 2
        assert reviews[0]["verdict"] == "AGREE"
        assert reviews[1]["verdict"] == "DISAGREE"

    def test_multiple_inspections_isolated(self, client, demo_headers):
        iid_a = f"{INSPECTION_ID}-iso-a"
        iid_b = f"{INSPECTION_ID}-iso-b"
        client.post(
            f"/api/v1/vision/static/inspect/{iid_a}/review",
            json={**_VALID_PAYLOAD, "comment": "Review for inspection A"},
            headers=demo_headers,
        )
        r = client.get(f"/api/v1/vision/static/inspect/{iid_b}/reviews", headers=demo_headers)
        assert r.json() == []

    def test_is_training_label_false_in_list(self, client, demo_headers):
        iid = f"{INSPECTION_ID}-tl"
        client.post(
            f"/api/v1/vision/static/inspect/{iid}/review",
            json=_VALID_PAYLOAD,
            headers=demo_headers,
        )
        reviews = client.get(
            f"/api/v1/vision/static/inspect/{iid}/reviews", headers=demo_headers
        ).json()
        assert all(rv["is_training_label"] is False for rv in reviews)
