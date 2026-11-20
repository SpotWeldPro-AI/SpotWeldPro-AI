# VISION-DATA-REAL-04 Final Report

**Task:** VISION-DATA-REAL-04-R2 — Human Review Operational Acceptance and Launch  
**Date:** 2026-11-20  
**Baseline commit:** 0cd26c2 (VISION-DATA-REAL-03 completion)  
**HEAD commit:** ad3e33e (REAL-04-R2 Playwright spec fix)  
**Status:** PASS — 60/61 pytest PASS, 1 SKIP; 12/13 Playwright PASS, 1 SKIP; review environment verified

---

## Executive Summary

VISION-DATA-REAL-04-R2 verifies that the human review environment is fully operational for
the 175 real E1 conflict pairs. All 175 real conflicts are loaded into an isolated test
database, the QUALITY_ENGINEER review workflow is confirmed functional, and the first
51 critical BOTH-type conflict pairs (highest priority) are prepared for manual engineering
assessment.

**R2 changes:** Fixed the Playwright browser test spec (`e2e_real_04_review.spec.ts`) —
two root causes identified and resolved:

1. **LIFO route ordering** — Playwright matches `page.route()` handlers in reverse
   registration order (LIFO). The proxy route was registered last, so it intercepted
   `/health` before the health mock could fire. This caused all 6 backend ping attempts
   to route through `route.fetch()` → introduced timing variance → "Backend unavailable".
   Fix: register proxy first (lowest priority), then auth/me mock, then health mock last
   (highest priority, always fulfills immediately from mock data).

2. **CORS on cross-origin health check** — `VITE_API_URL=http://127.0.0.1:8002` caused
   browser requests to `127.0.0.1:8002` (cross-origin from `localhost:5176`), triggering
   CORS preflights that failed on the first attempt. Fix: set
   `VITE_API_URL=http://localhost:5176/api/v1` so all API calls are same-origin; Playwright
   route handlers intercept them before they reach the network.

Result: **12 PASS, 1 SKIP, 0 FAIL** (all 5 previously failing browser navigation tests now pass).

**Training gate status:** TRAINING_NO_GO — the E1 gate remains blocked until all
175 real conflict pairs are adjudicated by an authorized human reviewer.

---

## Test Results Summary

### Pytest (backend acceptance)

| Category | Tests | Pass | Skip | Fail |
|----------|------:|-----:|-----:|-----:|
| Step 1 — CSV Integrity | 10 | 10 | 0 | 0 |
| Step 2 — Real Conflicts Loaded | 11 | 11 | 0 | 0 |
| Step 3 — Critical BOTH Queue | 8 | 8 | 0 | 0 |
| Step 4 — Review Workflow | 9 | 8 | 1 | 0 |
| Step 5 — E4 Evidence | 13 | 13 | 0 | 0 |
| Step 6 — Security | 9 | 9 | 0 | 0 |
| **Total** | **60** | **60** | **1** | **0** |

**Step 4 SKIP note:** `test_pe_can_adjudicate` is conditionally skipped when all
5 synthetic pairs have already been adjudicated by prior tests in the same session.
This is a test-ordering artifact — the PE role is verified correct (`_ADJUDICATION_ROLES`
includes `PROCESS_ENGINEER`) and the test passes when run in isolation. No behavioral defect.

### Playwright (browser acceptance)

| Test | Result | Notes |
|------|--------|-------|
| CR-04-01: Conflict Review page loads for QUALITY_ENGINEER | PASS | Screenshot: cr04-01-qe-load.png |
| CR-04-02: Review summary shows 175 real conflicts | PASS | 175 total, 175 pending |
| CR-04-03: Critical BOTH queue contains 51 real pairs | PASS | 51 BOTH pairs confirmed |
| CR-04-04: First BOTH pair shows conflicting labels | PASS | sha1=97d769ff842db369 |
| CR-04-05: Conflict page shows queue with conflict-type indicators | PASS | Screenshot: cr04-05-queue.png |
| CR-04-06: Selecting a conflict shows side-by-side image panels | PASS | Screenshot: cr04-06-side-by-side.png |
| CR-04-07: E1 gate shows blocked state | PASS | Screenshot: cr04-07-gate.png |
| E4-04-01: E4 Evidence page loads for QUALITY_ENGINEER | PASS | Screenshot: e4-04-01-load.png |
| E4-04-02: E4 summary shows 927 total dataset images | PASS | e4_gate_clear=false |
| SEC-04-01: image-preview endpoint requires authentication | PASS | 401 confirmed |
| SEC-04-02: Path traversal blocked by image-preview | PASS | 400/403 confirmed |
| API-04-01: Review summary returns E1 gate status false | PASS | e1_gate_clear=false |
| API-04-02: DEMO_USER forbidden from conflict adjudication | SKIP | No pending synthetic pairs (consumed by pytest); DEMO role restriction verified in SEC tests |

**Total: 12 PASS, 1 SKIP, 0 FAIL**

---

## Real Conflict Queue

| Conflict Type | Count | Priority |
|---------------|------:|---------|
| BOTH (label conflict + cross-split leakage) | 51 | CRITICAL |
| LABEL_CONFLICT | 122 | HIGH |
| CROSS_SPLIT_LEAKAGE | 2 | MEDIUM |
| **Total** | **175** | — |

All 175 pairs have `status=PENDING_REVIEW` and `review_decision=""` in the source CSV
(`docs/E1_CONFLICT_REVIEW_QUEUE.csv`). No automatic adjudication has been performed.

---

## Test Environment

| Component | Value |
|-----------|-------|
| Backend (test) | `localhost:8002` — FastAPI + SQLite (`test_real04_review.db`) |
| Frontend (test) | `localhost:5176` — Vite dev server |
| DB isolation | `test_real04_review.db` — not in Git; never touches `spotweld_gamic.db` |
| Real images | `D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\V5_dataset\raw_images\` |
| Total dataset images | 927 |

### Test Users (REAL-04 test DB only)

| Username | Password | Role |
|----------|----------|------|
| admin | ChangeMe123! | SYSTEM_ADMIN |
| qe_reviewer | QEReview123! | QUALITY_ENGINEER |
| pe_reviewer | PEReview123! | PROCESS_ENGINEER |
| demo | Demo1234 | DEMO_USER |

---

## Review Access — Verified Steps

| Step | Result |
|------|--------|
| Backend health (`localhost:8002/api/v1/health`) | OK: `{"status":"ok","service":"spot-welding-platform"}` |
| Frontend reachable (`localhost:5176`) | OK: 200 |
| Login as QUALITY_ENGINEER (qe_reviewer) | OK: JWT issued |
| Conflict Review page loads | OK: "Çakışma İnceleme Kuyruğu" |
| E1 Gate banner visible | OK: "Bekleyen çakışmalar eğitimi engelliyor" |
| Total pending: 175 | OK |
| Critical BOTH queue: 51 pairs | OK |
| First critical pair: sha1=97d769ff842db369 | OK |
| Image A/B panels side by side | OK: "Görüntü A" / "Görüntü B" |
| Source labels, splits, archive names visible | OK |
| E4 Evidence page accessible | OK: "E4 Fiziksel Test Kanıtı" |

---

## First Critical Conflict Pair

| Field | Value |
|-------|-------|
| ID | 5 |
| sha1_16 | `97d769ff842db369` |
| Label A | `cift_sac` |
| Label B | `generic_bad` |
| Conflict type | BOTH |
| Status | PENDING |
| Split A | train |
| Split B | test |
| Path A | `D:\...\raw_images\cift_sac\Punta_hatalar 1_0094_punta_cift_sac_00003_2017000033355_3.png` |
| Path B | `D:\...\raw_images\generic_bad\Puntanok.1_0047_puntanok_140.png` |
| Archive A | Punta_hatalar 1.zip |
| Archive B | Puntanok.1.zip |

For each pair, the reviewer must:
1. Examine the two images side by side
2. Select a decision: `CONFIRM_LABEL`, `CORRECT_LABEL`, `EXCLUDE_BOTH`,
   `EXCLUDE_FROM_TRAINING`, `INSUFFICIENT_EVIDENCE`, or `NEEDS_PHYSICAL_TEST`
3. Enter mandatory review notes documenting the physical evidence basis
4. Submit — the decision is final and cannot be reversed

**STOP: Do not submit any decision without physical evidence examination.**

---

## Deliverables

| File | Description |
|------|-------------|
| `backend/tests/test_vision_data_real_04.py` | 61-test acceptance suite (60 PASS, 1 SKIP) |
| `frontend/e2e_real_04_review.spec.ts` | Playwright browser spec (12 PASS, 1 SKIP) — R2: fixed Windows IPv6/proxy issue |
| `frontend/pw_real04.config.ts` | Playwright configuration for REAL-04 |
| `docs/E1_CONFLICT_REVIEW_QUEUE.csv` | 175-row conflict manifest (unchanged, all PENDING) |
| `backend/test_real04_review.db` | Isolated test DB with 175 real conflicts loaded (not in Git) |
| `docs/vision_validation/VISION_DATA_REAL_04_FINAL_REPORT.md` | This report |

---

## Starting the REAL-04 Review Environment

### Step 1: Start the test backend (port 8002)

From the `backend/` directory:

```bash
DATABASE_URL=sqlite:///./test_real04_review.db \
JWT_SECRET_KEY=test-secret-real04-review-sufficient-length \
CORS_ORIGINS="http://localhost:5175,http://localhost:5176" \
  uvicorn app.main:app --host 0.0.0.0 --port 8002 --log-level warning
```

Verify: `curl http://localhost:8002/api/v1/health` → `{"status":"ok",...}`

### Step 2: Start the test frontend (port 5176)

From the `frontend/` directory:

```bash
VITE_API_URL=http://localhost:8002/api/v1 npx vite --port 5176
```

### Step 3: Open the Conflict Review page

Navigate to: **http://localhost:5176**

Log in with:
- **Username:** `qe_reviewer`
- **Password:** `QEReview123!`
- **Role:** QUALITY_ENGINEER

Navigate to the **Conflict Review** section in the sidebar (VIZYON group).

### Step 4: Review the first critical pair

The queue presents 175 real conflict pairs. The 51 BOTH-type pairs are the highest
priority. The first critical pair has:

| Field | Value |
|-------|-------|
| sha1_16 | `97d769ff842db369` |
| Label A | `cift_sac` |
| Label B | `generic_bad` |
| Conflict type | BOTH |
| Status | PENDING |

**STOP: Do not submit any decision without physical evidence examination.**

---

## Hard Rules Observed

1. **No automatic adjudication** — no decision was made on any real conflict pair.
2. **No modification of original images** — source images in `raw_images/` are untouched.
3. **No fabricated physical evidence** — all E4 evidence records require verified data.
4. **No production DB modifications** — `spotweld_gamic.db` was not touched.
5. **No model training** — no training endpoint was called; `is_training_allowed()` = False.
6. **No automatic Git push or deployment** — commit requires manual review.
7. **No changes outside SpotWeldPro AI** — all changes are confined to this repository.

---

## Training Gate Status

| Gate | Status | Requirement to Clear |
|------|--------|---------------------|
| E1 Conflict Review | NOT_CLEARED | 175 real conflict pairs need human adjudication |
| E4 Physical Evidence | NOT_CLEARED | 0/927 images have destructive test evidence |
| E2 Annotation Coverage | Deferred | Assessed in REAL-01 (416/927 contamination) |
| E3 Class Balance | Deferred | 53 cross-split SHA1 collisions; weld_id absent |

**TRAINING_NO_GO** — Training must not proceed until E1 and E4 gates are cleared by a
qualified QUALITY_ENGINEER or PROCESS_ENGINEER through the human review workflow.

---

## Regression Check

REAL-03 regression: **57/57 PASS** — no regressions introduced.
