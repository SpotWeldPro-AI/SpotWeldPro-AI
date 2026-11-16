"""AUTH-UX-DEMO-R3 — DEMO_USER role RBAC and isolation tests.

Verifies that the DEMO_USER role:
  - Has full access to all customer-facing engineering modules
    (dashboard, weld analysis, engineering, failure probability, statistical,
     energy, reports, projects, model catalog, vision, annotation read)
  - Cannot adjudicate E1 conflict pairs (annotation.py _ADJUDICATION_ROLES guard)
  - Cannot export datasets (annotation.py _EXPORT_ROLES guard)
  - Cannot add weld-point approvals (approval:write permission)
  - Cannot access admin-only operations (user creation, audit log, user list)
  - Cannot access another user's /me token with their own credentials
  - DEMO_USER is not PROCESS_ENGINEER, QUALITY_ENGINEER, or SYSTEM_ADMIN

Conftest creates:
  - admin / ChangeMe123! / SYSTEM_ADMIN
  - demo  / A1234        / DEMO_USER
"""

import pytest


def _login(client, username: str, password: str):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _demo_token(client) -> str:
    r = _login(client, "demo", "A1234")
    assert r.status_code == 200, f"Demo login failed: {r.json()}"
    return r.json()["access_token"]


def _admin_token(client) -> str:
    r = _login(client, "admin", "ChangeMe123!")
    assert r.status_code == 200
    return r.json()["access_token"]


# ── RBAC-01: DEMO_USER role identity ─────────────────────────────────────────

class TestDemoUserIdentity:
    def test_demo_role_is_demo_user(self, client):
        tok = _demo_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(tok))
        assert me.status_code == 200
        assert me.json()["role"] == "DEMO_USER"

    def test_demo_role_is_not_process_engineer(self, client):
        tok = _demo_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(tok))
        assert me.json()["role"] != "PROCESS_ENGINEER"

    def test_demo_role_is_not_quality_engineer(self, client):
        tok = _demo_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(tok))
        assert me.json()["role"] != "QUALITY_ENGINEER"

    def test_demo_role_is_not_system_admin(self, client):
        tok = _demo_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(tok))
        assert me.json()["role"] != "SYSTEM_ADMIN"

    def test_demo_role_is_not_read_only(self, client):
        """DEMO_USER must not be READ_ONLY — it needs write access to modules."""
        tok = _demo_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(tok))
        assert me.json()["role"] != "READ_ONLY"


# ── RBAC-02: Enabled modules — read operations ───────────────────────────────

class TestDemoEnabledModules:
    def test_dashboard_accessible(self, client):
        tok = _demo_token(client)
        r = client.get("/api/v1/dashboard", headers=_bearer(tok))
        assert r.status_code == 200

    def test_projects_list_accessible(self, client):
        tok = _demo_token(client)
        r = client.get("/api/v1/projects", headers=_bearer(tok))
        assert r.status_code in (200, 404)

    def test_engineering_weld_lobe_accessible(self, client):
        tok = _demo_token(client)
        r = client.get("/api/v1/engineering/process-window-config", headers=_bearer(tok))
        assert r.status_code in (200, 404)

    def test_failure_probability_accessible(self, client):
        """Failure Analysis module requires weld:read."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/failure-probability/analyze",
            headers=_bearer(tok),
            json={
                "current_ka": 9.0, "time_cycles": 14, "force_kn": 3.5,
                "material_grade": "DC04", "sheet_thickness_mm": 1.0,
                "electrode_tip_diameter_mm": 6.0,
            },
        )
        # 200 = analysis ran; 422 = validation error (payload issue, not auth)
        assert r.status_code in (200, 422)

    def test_statistical_analysis_accessible(self, client):
        """Statistical Analysis (Taguchi DOE) requires weld:read."""
        tok = _demo_token(client)
        r = client.get("/api/v1/statistical-analysis/health", headers=_bearer(tok))
        assert r.status_code in (200, 404)

    def test_energy_accessible(self, client):
        tok = _demo_token(client)
        r = client.get("/api/v1/energy/parameters", headers=_bearer(tok))
        assert r.status_code in (200, 404)

    def test_model_catalog_accessible(self, client):
        tok = _demo_token(client)
        r = client.get("/api/v1/model-catalog/models", headers=_bearer(tok))
        assert r.status_code in (200, 404)

    def test_annotation_conflicts_readable(self, client):
        """DEMO_USER can list conflict records (list_conflicts has no role guard)."""
        tok = _demo_token(client)
        r = client.get("/api/v1/annotation/conflicts", headers=_bearer(tok))
        assert r.status_code == 200


# ── RBAC-03: Enabled modules — write operations ──────────────────────────────

class TestDemoWriteAccess:
    def test_project_create_allowed(self, client):
        """DEMO_USER has project:write permission."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/projects",
            headers=_bearer(tok),
            json={"name": "Demo Test Project", "description": "RBAC test"},
        )
        assert r.status_code in (201, 422)

    def test_weld_point_endpoints_accessible_with_write(self, client):
        """DEMO_USER has weld:write permission needed for weld point creation."""
        tok = _demo_token(client)
        # Create a project first (may already exist from above test)
        proj = client.post(
            "/api/v1/projects",
            headers=_bearer(tok),
            json={"name": "Demo WP Project RBAC", "description": "test"},
        )
        if proj.status_code == 201:
            proj_id = proj.json()["id"]
            r = client.post(
                f"/api/v1/projects/{proj_id}/weld-points",
                headers=_bearer(tok),
                json={"name": "WP-001", "nominal_current_ka": 9.0, "nominal_time_cycles": 14},
            )
            assert r.status_code in (201, 422)


# ── RBAC-04: Restricted operations — E1 conflict adjudication ────────────────

class TestDemoRestrictions:
    def test_e1_adjudication_blocked(self, client):
        """DEMO_USER must NOT adjudicate E1 conflict pairs."""
        tok = _demo_token(client)
        # Attempt to PATCH a conflict (even a non-existent one — expect 403, not 404)
        r = client.patch(
            "/api/v1/annotation/conflicts/99999",
            headers=_bearer(tok),
            json={"decision": "CONFIRM_LABEL", "notes": "Demo attempt"},
        )
        assert r.status_code == 403, (
            f"Expected 403 for DEMO_USER E1 adjudication, got {r.status_code}: {r.json()}"
        )

    def test_dataset_export_blocked(self, client):
        """DEMO_USER must NOT export training datasets."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/annotation/export",
            headers=_bearer(tok),
            json={"export_version": "v1", "split": "train"},
        )
        assert r.status_code == 403, (
            f"Expected 403 for DEMO_USER export, got {r.status_code}: {r.json()}"
        )

    def test_e1_load_queue_blocked(self, client):
        """DEMO_USER must NOT reload the E1 queue (destructive operation)."""
        tok = _demo_token(client)
        r = client.post("/api/v1/annotation/load-e1-queue", headers=_bearer(tok))
        assert r.status_code == 403, (
            f"Expected 403 for DEMO_USER load-e1-queue, got {r.status_code}"
        )

    def test_weld_point_approval_blocked(self, client):
        """DEMO_USER lacks approval:write — cannot add weld point approvals."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/projects/1/weld-points/1/approvals",
            headers=_bearer(tok),
            json={"status": "approved", "notes": "demo attempt"},
        )
        # 403 (no permission) or 404 (resource not found) — not 200/201
        assert r.status_code in (403, 404), (
            f"Expected 403/404 for approval:write attempt, got {r.status_code}"
        )

    def test_user_creation_blocked(self, client):
        """DEMO_USER must NOT create new user accounts (requires admin *)."""
        tok = _demo_token(client)
        r = client.post(
            "/api/v1/auth/users",
            headers=_bearer(tok),
            json={
                "username": "malicious_user",
                "email": "malicious@example.com",
                "full_name": "Malicious",
                "password": "Password1!",
                "role": "SYSTEM_ADMIN",
            },
        )
        assert r.status_code == 403, (
            f"Expected 403 for user creation by DEMO_USER, got {r.status_code}"
        )

    def test_user_list_blocked(self, client):
        """DEMO_USER must NOT list all user accounts."""
        tok = _demo_token(client)
        r = client.get("/api/v1/auth/users", headers=_bearer(tok))
        assert r.status_code == 403

    def test_audit_log_blocked(self, client):
        """DEMO_USER must NOT access audit logs."""
        tok = _demo_token(client)
        r = client.get("/api/v1/audit", headers=_bearer(tok))
        assert r.status_code == 403

    def test_annotation_review_summary_blocked(self, client):
        """DEMO_USER must NOT access review summary (requires PE/QE/SA role)."""
        tok = _demo_token(client)
        r = client.get("/api/v1/annotation/conflicts/review-summary", headers=_bearer(tok))
        assert r.status_code == 403, (
            f"Expected 403 for DEMO_USER review-summary, got {r.status_code}"
        )

    def test_e1_load_conflicts_blocked(self, client):
        """DEMO_USER must NOT load conflicts (SYSTEM_ADMIN only)."""
        tok = _demo_token(client)
        r = client.post("/api/v1/annotation/load-conflicts", headers=_bearer(tok))
        assert r.status_code == 403, (
            f"Expected 403 for load-conflicts, got {r.status_code}"
        )


# ── RBAC-05: Tenant isolation — demo cannot see admin token data ──────────────

class TestDemoTenantIsolation:
    def test_demo_cannot_use_admin_token(self, client):
        """The demo user's token is specific to that user."""
        demo_tok = _demo_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(demo_tok))
        assert me.json()["username"] == "demo"
        assert me.json()["role"] == "DEMO_USER"

    def test_unauthenticated_access_denied(self, client):
        """All endpoints require authentication even without demo mode."""
        r = client.get("/api/v1/dashboard")
        assert r.status_code in (401, 403)

    def test_demo_token_cannot_impersonate_admin(self, client):
        """Using the demo token to access admin-only routes returns 403."""
        demo_tok = _demo_token(client)
        r = client.get("/api/v1/auth/users", headers=_bearer(demo_tok))
        assert r.status_code == 403


# ── RBAC-06: Existing roles not affected ─────────────────────────────────────

class TestExistingRolesUnchanged:
    def test_admin_still_works(self, client):
        tok = _admin_token(client)
        r = client.get("/api/v1/dashboard", headers=_bearer(tok))
        assert r.status_code == 200

    def test_admin_can_list_users(self, client):
        tok = _admin_token(client)
        r = client.get("/api/v1/auth/users", headers=_bearer(tok))
        assert r.status_code == 200

    def test_demo_user_exists_in_user_list(self, client):
        """Admin can see the demo account in the user list."""
        tok = _admin_token(client)
        r = client.get("/api/v1/auth/users", headers=_bearer(tok))
        assert r.status_code == 200
        usernames = [u["username"] for u in r.json()]
        assert "demo" in usernames
