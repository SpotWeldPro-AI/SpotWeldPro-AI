# E4 Physical Test Evidence — Readiness Assessment

**Date:** 2026-11-19  
**Task:** VISION-DATA-REAL-02  
**Gate:** E4 — Ground Truth Qualification  
**Status:** NOT CLEAR (0 destructive tests on 927 real images)

---

## Summary

All 927 images in the V5 dataset carry `label_provenance = SURFACE_OBSERVATION`. No destructive or NDT tests have been conducted on any of the original weld images. The E4 gate is not clear.

| Metric | Value |
|--------|-------|
| Dataset images | 927 |
| Images with physical evidence | 0 |
| Nugget measurements | 0 |
| Qualified destructive tests | 0 |
| E4 coverage | 0.0% |
| E4 gate clear | False |

---

## Infrastructure Status (REAL-02 — COMPLETE)

The following E4 infrastructure has been implemented and is ready for use:

### Database Model

`PhysicalTestEvidence` table in `physical_test_evidence`.

Supported test methods:

| Method | Nugget Measurement | Physical Evidence Level |
|--------|--------------------|------------------------|
| CROSS_SECTION | Yes (required for exact nugget size) | Highest |
| PEEL_TEST | No | High |
| CHISEL_TEST | No | High |
| UT_SCAN | Yes (non-destructive) | High |
| XRF | No | Medium |
| RADIOGRAPHIC | No | Medium |
| OTHER | No | Variable |

**SURFACE_OBSERVATION is explicitly excluded** — it must not appear in this table.

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/annotation/e4-evidence` | Record a new physical test result |
| `GET /api/v1/annotation/e4-evidence` | List records (filterable by method/verdict/quality) |
| `GET /api/v1/annotation/e4-evidence/summary` | Coverage summary and E4 gate status |
| `GET /api/v1/annotation/e4-evidence/{id}` | Fetch one record |

Access: PROCESS_ENGINEER, QUALITY_ENGINEER, SYSTEM_ADMIN only.

### Frontend Page

E4EvidencePage is available at VISION → E4 Physical Evidence.

Features:
- Coverage dashboard (% of 927 images with physical evidence)
- E4 gate indicator (always NOT CLEAR at current 0% coverage)
- Evidence entry form with method-aware validation rules
- Nugget fields visible only when test method supports measurement
- VERIFIED quality enforces non-empty report reference number
- Expandable record list filtered by test method
- Read-only original image path reference (no file modification)

---

## Validation Rules Enforced

| Rule | Enforcement Level |
|------|------------------|
| SURFACE_OBSERVATION rejected | Server 422 |
| nugget_diameter_mm requires CROSS_SECTION or UT_SCAN | Server 422 |
| VERIFIED quality requires test_report_ref | Server 422 |
| Only PE/QE/SYSTEM_ADMIN can submit | Server 403 |
| Duplicate (image_path, test_method, test_date) blocked | DB unique constraint |
| created_by set from authenticated user | Server-side only |
| No automatic training gate changes | No gate-write code |

---

## Recommended Testing Program

To satisfy E4 requirements for surface classifier training, the following physical tests are recommended:

### Minimum Viable Sample

| Defect Class | Min Samples | Recommended Method | Priority |
|-------------|-------------|-------------------|---------|
| kopuk (Broken) | 10 | Peel test + cross-section | CRITICAL |
| kucuk_cekirdek (Small Nugget indicator) | 15 | Cross-section | CRITICAL |
| cift_sac (Double Sheet indicator) | 5 | Cross-section | CRITICAL |
| ok (Accepted) | 20 | Cross-section | HIGH |
| capak (Spatter) | 10 | Visual + peel | HIGH |
| deformeli (Deformed) | 5 | Visual + peel | MEDIUM |
| Other classes | 3–5 each | Method appropriate | MEDIUM |
| **TOTAL** | **~80–100** | | |

### Evidence Quality Requirements

- **VERIFIED**: Report reference number from certified lab required
- **Acceptance standard**: Document ISO 15614-12, AWS D8.1, or applicable OEM standard
- **Test operator**: Badge or name of certified technician
- **Test date**: ISO 8601 (YYYY-MM-DD)

---

## E4 Gate Clearing Conditions

The E4 gate clears when:
1. Physical evidence records with `evidence_quality = VERIFIED` exist for a representative sample
2. A QUALITY_ENGINEER signs off on the evidence quality and coverage
3. The E4 gate flag is manually set to True after QE review (requires a separate gate-sign-off endpoint or admin action — not automatic)

**The E4 gate cannot be cleared automatically from this system.**

---

## Defect Codes That Require Physical Confirmation

The following defect codes have label provenance that depends on surface-only visual classification. Physical tests are required before these can be used as confirmed ground truth for model training:

| Code | Surface-Only Limitation | Required Test |
|------|-------------------------|---------------|
| kucuk_cekirdek | Surface indentation ≠ nugget size | Cross-section or UT scan |
| kopuk | Cannot confirm fracture depth | Peel test |
| cift_sac | Cannot confirm stack thickness | Cross-section |
| ok | Cannot confirm nugget formation | Cross-section (sample) |

---

## History

| Date | Coverage | Notes |
|------|----------|-------|
| 2026-11-14 | 0% | REAL-01 baseline — 927/927 SURFACE_OBSERVATION |
| 2026-11-19 | 0% | REAL-02 — E4 infrastructure deployed; no real tests yet |
