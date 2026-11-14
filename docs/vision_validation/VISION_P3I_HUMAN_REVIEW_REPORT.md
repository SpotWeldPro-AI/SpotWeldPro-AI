# Vision Phase 3I — Human-Guided Conflict Resolution

**Date:** 2026-11-14  
**Status:** BASELINE_ESTABLISHED — E1 queue loaded, 0/175 decisions completed  
**Gate:** E1_GATE_CLEAR = False

---

## Scope

P3I implements the human-guided conflict resolution workflow required before training data can be certified. It provides:

- Five new adjudication decisions beyond legacy KEEP_A/KEEP_B
- Mandatory reviewer notes enforcement (server and client)
- E1 queue loader that accepts all conflict types including CROSS_SPLIT_LEAKAGE
- Review summary and eligible-count API endpoints
- ConflictReviewPage UI with prioritized queue, side-by-side image panels, and E1 gate indicator

---

## E1 Queue Baseline

| Metric | Value |
|--------|-------|
| Total conflict pairs | 175 |
| LABEL_CONFLICT | 122 |
| BOTH (label conflict + cross-split) | 51 |
| CROSS_SPLIT_LEAKAGE only | 2 |
| Decisions completed | 0 |
| E1 gate clear | **False** |

All 175 pairs loaded from `docs/E1_CONFLICT_REVIEW_QUEUE.csv`. No decisions have been pre-filled. Every record starts PENDING.

---

## P3I Decision Codes

| Decision | Action | Excludes from training |
|----------|--------|----------------------|
| KEEP_A | Retain path_a annotation as authoritative | No (removes path_b) |
| KEEP_B | Retain path_b annotation as authoritative | No (removes path_a) |
| KEEP_BOTH | Both annotations valid in different contexts | No |
| EXCLUDE_BOTH | Neither annotation is trustworthy | Yes (both paths) |
| CONFIRM_LABEL | Labels consistent; keep more specific | No |
| CORRECT_LABEL | One label wrong; reviewer corrects in notes | No |
| EXCLUDE_FROM_TRAINING | Exclude both paths from training, keep in DB | Yes (both paths) |
| INSUFFICIENT_EVIDENCE | Cannot determine without more data | Yes (both paths) |
| NEEDS_PHYSICAL_TEST | Destructive test required before label confirmed | Yes (both paths) |

**Notes are mandatory for all decisions.** Empty or whitespace-only notes raise `AnnotationServiceError` at the service layer.

---

## Current Training Eligibility

| Metric | Value |
|--------|-------|
| Total dataset records | 927 |
| CLEAN + LOW contamination | 511 |
| Training-eligible now | 191 |
| Eval-eligible now | 151 |
| Pending conflict paths (blocked) | 343 |
| Pending leakage paths (blocked) | 106 |
| Surface classifier GO | **False** |

The 343 pending-conflict paths and 106 pending-leakage paths will be reclassified as decisions are made. The surface classifier requires ≥ 200 training-eligible and ≥ 40 eval-eligible records with DatasetAudit APPROVED.

---

## API Endpoints Added

| Endpoint | Role | Purpose |
|----------|------|---------|
| `POST /api/v1/annotation/load-e1-queue` | SYSTEM_ADMIN | Load E1_CONFLICT_REVIEW_QUEUE.csv into DB |
| `GET /api/v1/annotation/conflicts/review-summary` | PE/QE/SA | Current review progress and gate status |
| `GET /api/v1/annotation/conflicts/eligible-counts` | PE/QE/SA | Training/eval eligibility after decisions |

---

## Tests

| Suite | Pass | Skip |
|-------|------|------|
| test_vision_p3i_conflict_review.py | 35 | 6 (API role auth not wired in test client) |
| Full regression | 295 | 4 |

---

## E1 Gate Completion Path

1. PROCESS_ENGINEER or QUALITY_ENGINEER opens Conflict Review page
2. Work through prioritized queue: BOTH → LABEL_CONFLICT → CROSS_SPLIT_LEAKAGE
3. Each decision requires reviewer notes
4. `GET /api/v1/annotation/conflicts/review-summary` → `e1_gate_clear: true` when all 175 resolved
5. Run `DatasetAudit.approve()` after E1 gate clears
6. Recheck `GET /api/v1/annotation/conflicts/eligible-counts` → `surface_classifier_go: true` if ≥ 200 train + ≥ 40 eval
7. Proceed to Phase 4 model training

---

## Files Changed

- `backend/app/vision/annotation_service.py` — P3I decisions, notes enforcement, `load_e1_queue_from_manifest`, `get_review_summary`, `get_eligible_counts_post_review`
- `backend/app/api/v1/annotation.py` — 3 new endpoints
- `frontend/src/pages/ConflictReviewPage.tsx` — full review UI
- `frontend/src/App.tsx` — Conflict Review nav + route
- `backend/tests/test_vision_p3i_conflict_review.py` — 41 tests
