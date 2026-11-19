# E1 / E4 Acceptance Matrix

**VISION-DATA-REAL-03 · 2026-11-19**

---

## Purpose

This matrix records the acceptance status of E1 (Conflict Review) and E4 (Physical Test
Evidence) workflows. Each row maps a workflow capability to its evidence, test ID, and
current status.

---

## E1 — Conflict Review Workflow

| # | Capability | Evidence | Test | Status |
|---|-----------|----------|------|--------|
| E1-C01 | Page loads and queue renders | `h1` heading visible; filter tabs present | CR-01 | ✅ PASS |
| E1-C02 | Priority badges displayed | CRITICAL/HIGH/MEDIUM/PENDING colors shown | CR-02 | ✅ PASS |
| E1-C03 | Selecting item shows side-by-side images | `Görüntü A` and `Görüntü B` panels present on click | CR-03 | ✅ PASS |
| E1-C04 | Taxonomy guidance panel toggles | Toggle button opens/closes class-label guide | CR-04 | ✅ PASS |
| E1-C05 | Decision validation enforced | Save button disabled; notes required; 400 on empty | CR-05 | ✅ PASS |
| E1-C06 | E1 gate status visible | Gate-blocked banner shows pending count | CR-06 | ✅ PASS |
| E1-C07 | List API returns synthetic pairs | `/conflicts` returns `synth*` items sorted by priority | API-01 (pytest Step 2) | ✅ PASS |
| E1-C08 | Decision endpoints respect roles | DEMO_USER → 403; PROCESS_ENGINEER → 403; QE → 200 | API-03 / pytest Step 2 | ✅ PASS |
| E1-C09 | Decision requires notes | Empty notes → 400; Valid notes → 200 | pytest Step 2 | ✅ PASS |
| E1-C10 | PENDING count decrements after decision | `review-summary.pending` decreases after confirm | pytest Step 2 | ✅ PASS |
| E1-C11 | Real 175 pairs unchanged | `eligible_for_training` count matches expected ≥ 100 | pytest Step 5 | ✅ PASS |

**E1 Workflow:** 11/11 acceptance criteria met.  
**E1 Training Gate:** NOT_CLEARED — 175 real conflict pairs still require human adjudication.

---

## E4 — Physical Test Evidence Workflow

| # | Capability | Evidence | Test | Status |
|---|-----------|----------|------|--------|
| E4-C01 | Page loads for authorized role | QUALITY_ENGINEER authenticated; heading visible | E4-01 | ✅ PASS |
| E4-C02 | Coverage dashboard present | 927-image dataset count; gate status shown | E4-02 | ✅ PASS |
| E4-C03 | Test method selector functional | PEEL_TEST, CROSS_SECTION, UT_SCAN options present | E4-03 | ✅ PASS |
| E4-C04 | Nugget fields conditional on method | PEEL_TEST hides; CROSS_SECTION shows nugget fields | E4-04 | ✅ PASS |
| E4-C05 | Empty state guidance shown | Descriptive placeholder for empty evidence list | E4-05 | ✅ PASS |
| E4-C06 | Evidence creation — PEEL_TEST | POST `/e4-evidence` with `test_method=PEEL_TEST` → 201 | pytest Step 3 | ✅ PASS |
| E4-C07 | Evidence creation — CROSS_SECTION | POST with nugget fields → 201 | pytest Step 3 | ✅ PASS |
| E4-C08 | Evidence creation — UT_SCAN | POST with nugget fields → 201 | pytest Step 3 | ✅ PASS |
| E4-C09 | SURFACE_OBSERVATION rejected | POST with invalid method → 422 | pytest Step 3 | ✅ PASS |
| E4-C10 | Nugget on PEEL_TEST rejected | nugget > 0 on PEEL_TEST → 422 | pytest Step 3 | ✅ PASS |
| E4-C11 | Verified verdict requires reference | `verdict=VERIFIED` with no ref → 422 | pytest Step 3 | ✅ PASS |
| E4-C12 | DEMO_USER forbidden | POST by DEMO_USER → 403 | pytest Step 3 | ✅ PASS |
| E4-C13 | List filtering by method | `?test_method=PEEL_TEST` returns filtered records | pytest Step 3 | ✅ PASS |
| E4-C14 | List filtering by verdict | `?verdict=VERIFIED` returns filtered records | pytest Step 3 | ✅ PASS |
| E4-C15 | GET by ID | Exact record retrieval by ID | pytest Step 3 | ✅ PASS |
| E4-C16 | GET nonexistent → 404 | Unknown ID returns 404 | pytest Step 3 | ✅ PASS |
| E4-C17 | Summary gate reflects count | `gate_clear=False` when count < threshold | pytest Step 3 | ✅ PASS |
| E4-C18 | Duplicate blocked | Same `(image_path, test_method, test_date)` → 409 | pytest Step 3 | ✅ PASS |

**E4 Workflow:** 18/18 acceptance criteria met.  
**E4 Training Gate:** NOT_CLEARED — 0 physical test evidence records; minimum threshold not reached.

---

## Security Acceptance

| # | Capability | Evidence | Test | Status |
|---|-----------|----------|------|--------|
| SEC-C01 | image-preview requires auth | Unauthenticated GET → 401 | SEC-01 | ✅ PASS |
| SEC-C02 | Path traversal blocked | `../../etc/passwd` input → 400 | SEC-02 | ✅ PASS |
| SEC-C03 | Null byte injection blocked | Null-byte path → 400 | pytest Step 4 | ✅ PASS |
| SEC-C04 | Disallowed extension rejected | `.php` extension → 400 | pytest Step 4 | ✅ PASS |
| SEC-C05 | Non-dataset-root path blocked | Path outside dataset dir → 400 | pytest Step 4 | ✅ PASS |
| SEC-C06 | CR role separation | DEMO/PE cannot adjudicate; QE/ADMIN can | pytest Step 4 | ✅ PASS |
| SEC-C07 | E4 role separation | DEMO cannot create evidence; PE/QE can | pytest Step 4 | ✅ PASS |
| SEC-C08 | E4 summary requires role | DEMO → 403; authorized roles → 200 | pytest Step 4 | ✅ PASS |

**Security:** 8/8 acceptance criteria met.

---

## Overall REAL-03 Acceptance

| Area | Criteria | Met | Status |
|------|---------|----:|--------|
| E1 Conflict Review | 11 | 11 | ✅ ALL PASS |
| E4 Physical Evidence | 18 | 18 | ✅ ALL PASS |
| Security | 8 | 8 | ✅ ALL PASS |
| **Total** | **37** | **37** | **✅ PASS** |

**VISION-DATA-REAL-03: PASS**  
**TRAINING_NO_GO** — Training gates remain blocked pending human review.
