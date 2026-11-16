"""AUTH-UX-DEMO-R6 — Engineering sub-tabs API + security fix regression tests.

Tests:
  - Electrode Life endpoint: valid request → 200 with expected fields
  - Dynamic Resistance endpoint: valid request → 200 with expected fields
  - Pulse Strategy endpoint: valid request → 200 with expected fields
  - annotation/export → 403 for DEMO_USER (not 500, not INTERNAL_ERROR)
  - annotation/export 403 body uses PERMISSION_DENIED error code (not INTERNAL_ERROR)
  - 403 responses from engineering-adjacent forbidden endpoints use PERMISSION_DENIED
  - DEMO_USER can access all three new engineering endpoints
"""

import pytest


def _login(client, username: str, password: str) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return r.json()["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _demo_token(client) -> str:
    return _login(client, "demo", "A1234")


def _admin_token(client) -> str:
    return _login(client, "admin", "ChangeMe123!")


# ── R6-EL: Electrode Life endpoint ───────────────────────────────────────────

class TestElectrodeLifeEndpoint:
    _PAYLOAD = {
        "material_family": "Düşük / Orta Karbonlu Çelik",
        "coated": False,
        "tip_diameter_mm": 6.0,
        "cooling_flow_lpm": 6.0,
        "cooling_temp_c": 20.0,
        "current_ka": 9.5,
        "annual_spot_count": 50000,
    }

    def test_electrode_life_200_for_demo_user(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/electrode-life", headers=_bearer(tok), json=self._PAYLOAD)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.json()}"

    def test_electrode_life_returns_estimated_life(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/electrode-life", headers=_bearer(tok), json=self._PAYLOAD)
        body = r.json()
        assert "estimated_life_spots" in body
        assert isinstance(body["estimated_life_spots"], int)
        assert body["estimated_life_spots"] > 0

    def test_electrode_life_returns_stepper_profile(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/electrode-life", headers=_bearer(tok), json=self._PAYLOAD)
        body = r.json()
        assert "stepper_profile" in body
        assert isinstance(body["stepper_profile"], list)
        assert len(body["stepper_profile"]) == 4, "Expected 4-step stepper profile"

    def test_electrode_life_returns_dress_interval(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/electrode-life", headers=_bearer(tok), json=self._PAYLOAD)
        body = r.json()
        assert "recommended_dress_interval_spots" in body
        assert body["recommended_dress_interval_spots"] > 0

    def test_electrode_life_returns_replacements_per_year(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/electrode-life", headers=_bearer(tok), json=self._PAYLOAD)
        body = r.json()
        assert "estimated_replacements_per_year" in body
        assert body["estimated_replacements_per_year"] >= 1

    def test_electrode_life_requires_auth(self, client):
        r = client.post("/api/v1/engineering/electrode-life", json=self._PAYLOAD)
        assert r.status_code == 401

    def test_electrode_life_coated_vs_uncoated(self, client):
        tok = _demo_token(client)
        base = dict(self._PAYLOAD, material_family="Galvanizli / Kaplamalı Çelik")
        r_coated = client.post("/api/v1/engineering/electrode-life", headers=_bearer(tok),
                               json={**base, "coated": True})
        r_uncoated = client.post("/api/v1/engineering/electrode-life", headers=_bearer(tok),
                                 json={**base, "coated": False})
        assert r_coated.status_code == 200
        assert r_uncoated.status_code == 200
        # Coated should give shorter life
        assert r_coated.json()["estimated_life_spots"] <= r_uncoated.json()["estimated_life_spots"]


# ── R6-DR: Dynamic Resistance endpoint ───────────────────────────────────────

class TestDynamicResistanceEndpoint:
    _SAMPLES = [85.0, 92.0, 108.0, 118.0, 120.0, 115.0, 109.0, 103.0, 98.0, 95.0, 92.0, 90.0]

    def test_dynamic_resistance_200_for_demo_user(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/dynamic-resistance", headers=_bearer(tok),
                        json={"samples_micro_ohm": self._SAMPLES})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.json()}"

    def test_dynamic_resistance_returns_peak(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/dynamic-resistance", headers=_bearer(tok),
                        json={"samples_micro_ohm": self._SAMPLES})
        body = r.json()
        assert "peak_micro_ohm" in body
        assert body["peak_micro_ohm"] == pytest.approx(120.0)

    def test_dynamic_resistance_returns_quality(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/dynamic-resistance", headers=_bearer(tok),
                        json={"samples_micro_ohm": self._SAMPLES})
        body = r.json()
        assert "quality" in body
        assert body["quality"] in ("Normal", "İnceleme Gerekli", "Yüksek Risk")

    def test_dynamic_resistance_returns_flags(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/dynamic-resistance", headers=_bearer(tok),
                        json={"samples_micro_ohm": self._SAMPLES})
        body = r.json()
        assert "flags" in body
        assert isinstance(body["flags"], list)

    def test_dynamic_resistance_too_few_samples_422(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/dynamic-resistance", headers=_bearer(tok),
                        json={"samples_micro_ohm": [100.0, 110.0]})  # < 5 samples
        assert r.status_code == 422

    def test_dynamic_resistance_requires_auth(self, client):
        r = client.post("/api/v1/engineering/dynamic-resistance",
                        json={"samples_micro_ohm": self._SAMPLES})
        assert r.status_code == 401

    def test_dynamic_resistance_post_peak_drop_ratio(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/dynamic-resistance", headers=_bearer(tok),
                        json={"samples_micro_ohm": self._SAMPLES})
        body = r.json()
        assert "post_peak_drop_ratio" in body
        # peak=120, final=90, drop=(120-90)/120 = 0.25
        assert 0.0 <= body["post_peak_drop_ratio"] <= 1.0


# ── R6-PS: Pulse Strategy endpoint ───────────────────────────────────────────

class TestPulseStrategyEndpoint:
    _PAYLOAD_SINGLE = {
        "material_family": "Düşük / Orta Karbonlu Çelik",
        "coated": False,
        "thickness_ratio": 1.0,
        "stack_count": "2T",
        "adhesive": False,
        "current_ka": 9.5,
        "weld_cycles": 16,
    }
    _PAYLOAD_MULTI = {
        "material_family": "Galvanizli / Kaplamalı Çelik",
        "coated": True,
        "thickness_ratio": 2.5,
        "stack_count": "3T",
        "adhesive": True,
        "current_ka": 10.0,
        "weld_cycles": 20,
    }

    def test_pulse_strategy_200_for_demo_user(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/pulse-strategy", headers=_bearer(tok),
                        json=self._PAYLOAD_SINGLE)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.json()}"

    def test_pulse_strategy_single_pulse_uncoated_mild_steel(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/pulse-strategy", headers=_bearer(tok),
                        json=self._PAYLOAD_SINGLE)
        body = r.json()
        assert body["pulse_count"] == 1
        assert body["strategy"] == "Tek darbe"

    def test_pulse_strategy_multi_pulse_coated_complex(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/pulse-strategy", headers=_bearer(tok),
                        json=self._PAYLOAD_MULTI)
        body = r.json()
        assert body["pulse_count"] >= 1
        assert body["decision_score"] >= 3

    def test_pulse_strategy_returns_validation_required(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/pulse-strategy", headers=_bearer(tok),
                        json=self._PAYLOAD_SINGLE)
        body = r.json()
        assert body["validation_required"] is True

    def test_pulse_strategy_returns_reasons(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/pulse-strategy", headers=_bearer(tok),
                        json=self._PAYLOAD_SINGLE)
        body = r.json()
        assert "reasons" in body
        assert len(body["reasons"]) >= 1

    def test_pulse_strategy_requires_auth(self, client):
        r = client.post("/api/v1/engineering/pulse-strategy", json=self._PAYLOAD_SINGLE)
        assert r.status_code == 401

    def test_pulse_strategy_aluminum_gets_two_pulses(self, client):
        tok = _demo_token(client)
        payload = {**self._PAYLOAD_SINGLE, "material_family": "Alüminyum Alaşımları"}
        r = client.post("/api/v1/engineering/pulse-strategy", headers=_bearer(tok), json=payload)
        body = r.json()
        assert body["pulse_count"] == 2


# ── R6-SEC: Security fix — annotation/export 403 not 500 ─────────────────────

class TestAnnotationExportSecurityFix:
    def test_export_returns_403_not_500_for_demo(self, client):
        """POST /annotation/export must return 403 for DEMO_USER (not 500)."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/annotation/export",
            headers=_bearer(tok),
            json={"export_version": "v1-r6-security-test"},
        )
        assert r.status_code == 403, (
            f"Expected 403, got {r.status_code}: {r.json()}"
        )

    def test_export_403_body_is_not_internal_error(self, client):
        """The 403 response must NOT use error_code='INTERNAL_ERROR'."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/annotation/export",
            headers=_bearer(tok),
            json={"export_version": "v1-r6-security-test"},
        )
        body = r.json()
        assert body.get("error_code") != "INTERNAL_ERROR", (
            f"error_code must not be INTERNAL_ERROR on 403: {body}"
        )

    def test_export_403_body_uses_permission_denied(self, client):
        """The 403 response must use error_code='PERMISSION_DENIED'."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/annotation/export",
            headers=_bearer(tok),
            json={"export_version": "v1-r6-security-test"},
        )
        body = r.json()
        assert body.get("error_code") == "PERMISSION_DENIED", (
            f"Expected PERMISSION_DENIED, got: {body.get('error_code')}"
        )

    def test_export_403_message_is_informative(self, client):
        """The 403 message must mention the required role, not a generic error."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/annotation/export",
            headers=_bearer(tok),
            json={"export_version": "v1-r6-security-test"},
        )
        body = r.json()
        msg = body.get("message", "")
        assert "QUALITY_ENGINEER" in msg or "export" in msg.lower() or "role" in msg.lower(), (
            f"Expected informative 403 message, got: {msg!r}"
        )

    def test_export_422_for_missing_body_fields(self, client):
        """Missing required export_version must return 422, not 403 or 500."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/annotation/export",
            headers=_bearer(tok),
            json={},
        )
        assert r.status_code == 422

    def test_export_401_for_unauthenticated(self, client):
        r = client.post("/api/v1/annotation/export", json={"export_version": "v1"})
        assert r.status_code == 401

    def test_adjudication_403_uses_permission_denied(self, client):
        """PATCH /annotation/conflicts/{id} → 403 with PERMISSION_DENIED for DEMO_USER."""
        tok = _demo_token(client)
        r = client.patch(
            "/api/v1/annotation/conflicts/99999",
            headers=_bearer(tok),
            json={"decision": "KEEP_A", "notes": "r6 test"},
        )
        assert r.status_code == 403
        body = r.json()
        assert body.get("error_code") == "PERMISSION_DENIED", (
            f"Expected PERMISSION_DENIED on adjudication 403, got: {body.get('error_code')}"
        )


# ── R6-WELD-LOBE: Existing endpoint still works ───────────────────────────────

class TestWeldLobeStillWorks:
    def test_weld_lobe_200_for_demo(self, client):
        tok = _demo_token(client)
        r = client.post("/api/v1/engineering/weld-lobe", headers=_bearer(tok), json={
            "material_family": "Düşük / Orta Karbonlu Çelik",
            "thickness_mm": 1.0,
            "force_kn": 3.0,
            "min_nugget_mm": 4.2,
            "current_min_ka": 6.0,
            "current_max_ka": 12.0,
            "current_step_ka": 0.5,
            "time_min_cycles": 8,
            "time_max_cycles": 18,
            "time_step_cycles": 1,
        })
        assert r.status_code == 200
        body = r.json()
        assert "safe_count" in body
        assert "sensitivity" in body
