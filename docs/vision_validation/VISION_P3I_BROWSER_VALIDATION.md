# Vision P3I — API & Build Validation Report

**Date:** 2026-11-14  
**Branch:** main  
**HEAD at start:** 07f58de  
**HEAD after fixes:** pending commit (P3I-R2)  
**Validation type:** Live API E2E + TypeScript + production build

---

## Browser Extension Status

The Claude in Chrome browser extension was not connected during this session. Browser-based screenshot verification was therefore not completed. All functional verification was performed via live API calls against a running backend instance (`http://127.0.0.1:8000`) with a clean SQLite test database (`test_p3i_browser.db`).

**Screenshot evidence:** Not available — browser extension required.

---

## Defects Found and Fixed

### Defect 1: Route Ordering — `GET /annotation/conflicts` returned 422

**Root cause:** FastAPI evaluates routes in declaration order. `GET /{annotation_id}` (line 242) was declared before `GET /conflicts` (line 374). FastAPI matched `/conflicts` as an annotation ID of type `int`, failing to parse `"conflicts"` and returning 422.

**Affected routes:**
- `GET /annotation/conflicts` — 422 instead of 200
- (Note: `GET /conflicts/review-summary` and `GET /conflicts/eligible-counts` were unaffected because FastAPI did not have a matching `GET /{id}/{sub}` route)

**Fix:** Moved all static `/conflicts*` routes (list, adjudicate, review-summary, eligible-counts) to be declared before `/{annotation_id}` in `annotation.py`. The duplicate block at the bottom of the file was removed.

**File:** `backend/app/api/v1/annotation.py`

### Defect 2: Missing Duplicate Decision Prevention

**Root cause:** `adjudicate_conflict()` in `annotation_service.py` updated the conflict record unconditionally without checking whether a decision had already been made. A second `PATCH /conflicts/{id}` call would silently overwrite the existing decision.

**Fix:** Added guard before the update:
```python
if conflict.decision != "PENDING":
    raise AnnotationServiceError(
        f"Conflict {conflict_id} already adjudicated as {conflict.decision!r}. "
        "Re-adjudication is not permitted."
    )
```

**File:** `backend/app/vision/annotation_service.py`

---

## API E2E Verification Results (22/22 PASS)

| Check | Result |
|-------|--------|
| Admin login | PASS |
| Reviewer login | PASS |
| Unauthenticated /conflicts → 401 | PASS |
| Unauthenticated /conflicts/review-summary → 401 | PASS |
| load-e1-queue (admin): inserted=175 | PASS |
| load-e1-queue idempotent: inserted=0 | PASS |
| Reviewer cannot load-e1-queue → 403 | PASS |
| GET /conflicts returns 200 (route fix) | PASS |
| Conflict item fields present (sha1_16, path_a/b, label_a/b, split_a/b, source_archive_a/b) | PASS |
| CONFIRM_LABEL decision accepted | PASS |
| CORRECT_LABEL decision accepted | PASS |
| EXCLUDE_FROM_TRAINING decision accepted | PASS |
| INSUFFICIENT_EVIDENCE decision accepted | PASS |
| NEEDS_PHYSICAL_TEST decision accepted | PASS |
| Empty notes rejected → 400 | PASS |
| Whitespace-only notes rejected → 400 | PASS |
| Re-adjudication of decided conflict → 400 (dup prevention) | PASS |
| Review summary: resolved=5, pending=170, gate_clear=False | PASS |
| Eligible counts returned with training_eligible field | PASS |
| Decisions persist: PENDING=170, CONFIRM_LABEL=1 after refresh | PASS |
| ANNOTATION_AUDIT.csv unchanged: 927 rows | PASS |
| E1_CONFLICT_REVIEW_QUEUE.csv unchanged: 175 rows, no pre-filled decisions | PASS |

---

## Conflict Record Fields Verified

```
id, sha1_16, path_a, path_b, label_a, label_b, split_a, split_b,
conflict_type, source_archive_a, source_archive_b,
decision, adjudicator_id, adjudication_notes, adjudicated_at, created_at
```

**Sample record (id=1):**
- type: CROSS_SPLIT_LEAKAGE
- label_a: ok, label_b: ok
- split_a: train, split_b: test
- path_a: `aw_images\ok\Okpunta_0130_okpunta_90.png`
- source_archive_a: Okpunta.zip

---

## Review Queue Count

| Metric | Value |
|--------|-------|
| Total loaded | 175 |
| LABEL_CONFLICT | 122 |
| BOTH | 51 |
| CROSS_SPLIT_LEAKAGE | 2 |
| Matches E1_CONFLICT_REVIEW_QUEUE.csv | YES |

---

## Post-Fix Unit Tests

| Suite | Pass | Skip | Notes |
|-------|------|------|-------|
| test_vision_p3i_conflict_review.py | 37 | 4 | +2 vs P3I commit (dup prevention now tested) |
| test_vision_p3h_remediation.py | 44 | 0 | Unchanged |

---

## TypeScript & Build

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` | PASS (no output) |
| `npm run build` | PASS ✓ built in 4.91s |
| ConflictReviewPage chunk in dist | YES (`ConflictReviewPage-noGJAUu2.js`) |

---

## Dataset Gate Status

| Gate | Status |
|------|--------|
| E1 total | 175 |
| E1 pending | 175 (clean DB baseline; 170 after test decisions) |
| e1_gate_clear | False |
| training_eligible | 191 (or 190 depending on EXCLUDE_FROM_TRAINING decisions) |
| surface_classifier_go | False |
| DatasetAudit.is_training_allowed() | False |

---

## Authentication & Authorization

| Test | Result |
|------|--------|
| Unauthenticated → 401 | PASS |
| PROCESS_ENGINEER adjudicates → 200 | PASS |
| PROCESS_ENGINEER load-e1-queue → 403 | PASS |
| SYSTEM_ADMIN load-e1-queue → 200 | PASS |

---

## Remaining Blockers for Human Review

1. **175 E1 conflict pairs all PENDING** — no human decisions have been made on the production dataset
2. **E1 gate clear = False** — all conflicts must be resolved with reviewer notes before DatasetAudit can be approved
3. **surface_classifier_go = False** — training_eligible=191 (needs ≥200; gap of 9)
4. **Browser extension not connected** — screenshot evidence of UI not captured this session
5. **All 5 model families: NO-GO** — independent of E1 (see UPDATED_MODEL_READINESS.md)

---

## Human Review Readiness: CONDITIONAL GO

The backend API, service layer, and route registration are verified correct. All 22 API checks pass. The ConflictReviewPage is included in the production build with TypeScript clean.

**Reviewers can begin E1 adjudication.** The two defects fixed in this session (route ordering, duplicate prevention) were blocking the conflict list page from working in a browser. These are now fixed.

**Remaining before training:** Complete all 175 E1 decisions → `DatasetAudit.approve()` → verify `surface_classifier_go: True`.
