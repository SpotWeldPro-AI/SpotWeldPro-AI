# VISION-DATA-REAL-03 Browser Validation Report

**Date:** 2026-11-19  
**Baseline commit:** c1115b3  
**Status:** PASS — 16/16 browser tests pass, 57/57 API tests pass

---

## Executive Summary

VISION-DATA-REAL-03 validates the Conflict Review and E4 Physical Test Evidence workflows
through real authenticated browser tests (Playwright + Chromium) against a seeded test
environment. All acceptance criteria are met.

| Category           | Tests | Pass | Skip | Fail |
|--------------------|------:|-----:|-----:|-----:|
| CR — Conflict Review |   6 |    6 |    0 |    0 |
| E4 — Physical Evidence |  5 |    5 |    0 |    0 |
| SEC — Security       |   2 |    2 |    0 |    0 |
| API — Integration    |   3 |    3 |    0 |    0 |
| **Total Browser**  | **16** | **16** |  **0** |  **0** |
| **Total API (pytest)** | **57** | **57** | — | **0** |

---

## Test Environment

| Component        | Value |
|-----------------|-------|
| Backend (test)  | `localhost:8001` — FastAPI + SQLite (`test_real03_seed.db`) |
| Frontend (test) | `localhost:5175` — Vite dev server (`VITE_API_URL=http://localhost:8001/api/v1`) |
| Browser         | Chromium (Playwright headless) |
| DB users        | admin/SYSTEM_ADMIN, qe_test/QUALITY_ENGINEER, pe_test/PROCESS_ENGINEER, demo/DEMO_USER |
| Conflict pairs  | 5 synthetic pairs seeded in `test_real03_seed.db` |
| E4 evidence     | No prior records (clean state) |

**Hard rules observed:**
- No production DB touched (`spotweld_gamic.db` untouched)
- No automatic adjudication of real images
- No model training triggered
- No E1–E4 training gates bypassed
- No push or deployment performed

---

## Browser Test Results (Playwright)

### CR — Conflict Review

| ID    | Test | Result | Notes |
|-------|------|--------|-------|
| CR-01 | Conflict Review page loads and shows queue | PASS | |
| CR-02 | Conflict queue shows priority badges | PASS | PENDING/Bekliyor badges visible |
| CR-03 | Selecting a conflict shows two image panels | PASS | Synthetic pair `image_a_000.png` vs `image_b_000.png` |
| CR-04 | Taxonomy guidance panel can be toggled | PASS | Toggle button opens/closes panel |
| CR-05 | Save Decision button disabled without notes | PASS | Decision validation enforced |
| CR-06 | Review progress bar and E1 gate visible | PASS | Gate-blocked banner present |

### E4 — Physical Evidence

| ID    | Test | Result | Notes |
|-------|------|--------|-------|
| E4-01 | E4 Evidence page loads for QUALITY_ENGINEER | PASS | QUALITY_ENGINEER role authenticated |
| E4-02 | E4 coverage dashboard shows gate status | PASS | 927-image dataset count present |
| E4-03 | Entry form shows test method selector | PASS | PEEL_TEST / CROSS_SECTION options |
| E4-04 | Nugget fields appear only for applicable methods | PASS | PEEL_TEST hides nugget; CROSS_SECTION shows |
| E4-05 | Empty evidence list shows guidance text | PASS | Guidance shown for clean state |

### SEC — Security

| ID     | Test | Result | Notes |
|--------|------|--------|-------|
| SEC-01 | image-preview endpoint requires authentication | PASS | 401 on unauthenticated request |
| SEC-02 | Path traversal blocked by image-preview | PASS | 400 returned for `../../etc/passwd` |

### API — Integration

| ID     | Test | Result | Notes |
|--------|------|--------|-------|
| API-01 | Review summary endpoint returns expected fields | PASS | `total`, `pending`, `reviewed` fields present |
| API-02 | E4 summary shows 927 total dataset images | PASS | `total_dataset_images` = 927 |
| API-03 | DEMO_USER forbidden from conflict adjudication | PASS | 403 returned |

---

## API Test Results (pytest)

**57/57 PASS** — `backend/tests/test_vision_data_real_03.py`

| Step | Description | Tests | Pass |
|------|-------------|------:|-----:|
| Step 1 | Environment verification | 7 | 7 |
| Step 2 | Conflict Review API | 11 | 11 |
| Step 3 | E4 Physical Evidence API | 13 | 13 |
| Step 4 | Security & role separation | 7 | 7 |
| Step 5 | E2/E3 readiness checks | 11 | 11 |
| Step 6 | Acceptance counts | 8 | 8 |

---

## Key Technical Findings

### 1. FastAPI Route Ordering Bug (Fixed)
Fixed-path routes (`/e4-evidence`, `/image-preview`) must be registered **before** the
`/{annotation_id}` parameterized catch-all route. Without this, FastAPI matches
`/e4-evidence` as `annotation_id="e4-evidence"` and returns 422.

### 2. Playwright API Proxy Required
`ConflictReviewPage` and `E4EvidencePage` use `const API = '/api/v1/annotation'` with raw
`fetch()`. In the test setup (Vite dev server on port 5175), there is no built-in proxy,
so relative-URL fetch calls would fail with connection refused. The browser tests add a
`page.route()` interceptor that transparently forwards `localhost:5175/api/v1/*` requests
to `localhost:8001/api/v1/*`.

### 3. IntegrityError Handling (Added)
`create_e4_evidence` now catches SQLite UNIQUE constraint violations and returns HTTP 409
(Conflict) instead of a 500 crash for duplicate `(image_path, test_method, test_date)` records.

### 4. E4 Nugget-Field Toggle (Confirmed)
Selecting `PEEL_TEST` correctly hides the nugget measurement fields. Selecting `CROSS_SECTION`
shows them. The DOM contains two `<select>` elements (filter + entry form); the entry form's
selector is identified by its "— yöntem seçin —" placeholder option.

---

## Infrastructure Notes

The test environment requires two server processes:

```
# Test backend
DATABASE_URL=sqlite:///./test_real03_seed.db \
JWT_SECRET_KEY=test-secret-real03-with-sufficient-length \
CORS_ORIGINS="http://localhost:5174,http://localhost:5175" \
  uvicorn app.main:app --port 8001

# Test frontend
VITE_API_URL=http://localhost:8001/api/v1 \
  npx vite --port 5175
```

See `docs/vision_validation/REAL_REVIEW_OPERATIONAL_GUIDE.md` for full startup procedure.

---

## Training Gate Status

| Gate | Status | Requirement |
|------|--------|-------------|
| E1 Conflict Review | NOT_CLEARED — pending review | 175 conflict pairs require human adjudication |
| E4 Physical Evidence | NOT_CLEARED — 0 records | Minimum threshold not reached |
| E2 Annotation Coverage | Not assessed in REAL-03 | Deferred |
| E3 Class Balance | Not assessed in REAL-03 | Deferred |

**TRAINING_NO_GO** — Training gates remain blocked. No automated training is initiated.
