# Model Readiness — Updated After P3I Baseline

**Date:** 2026-11-14  
**Phase:** P3I (Human-Guided Conflict Resolution — in progress)  
**Previous assessment:** P3H (all 5 models NO-GO)

---

## Training Gate Status

| Gate | Status |
|------|--------|
| DatasetAudit.is_training_allowed() | **False** |
| E1 conflict queue loaded | Yes (175 pairs) |
| E1 decisions completed | 0 / 175 |
| E1 gate clear | **False** |

No gate status has changed from P3H. Training remains blocked until E1 is fully resolved and DatasetAudit is approved.

---

## Model Readiness (All 5 Families: NO-GO)

### 1. Surface Binary Classifier (ok / defect)

| Requirement | Required | Current | Status |
|-------------|----------|---------|--------|
| Training eligible | ≥ 200 | 191 | **SHORT by 9** |
| Eval eligible | ≥ 40 | 151 | OK |
| DatasetAudit | APPROVED | PENDING | **BLOCKED** |
| E1 gate | CLEAR | PENDING | **BLOCKED** |

**Nearest to GO.** After E1 resolution, CONFIRM_LABEL and CORRECT_LABEL decisions will return paths to training pool. If ≥ 9 paths are recovered, training count crosses threshold. CONDITIONAL_GO possible immediately after E1 completion.

### 2. Defect Type Classifier (12 defect classes)

| Requirement | Required | Current | Status |
|-------------|----------|---------|--------|
| Min per-class training | ≥ 30 | 4 classes < 30 | **INSUFFICIENT** |
| E1 gate | CLEAR | PENDING | **BLOCKED** |
| DatasetAudit | APPROVED | PENDING | **BLOCKED** |

Classes with < 30 training samples: `cokertme` (4), `cift_sac` (14), `kenar` (25), `kucuk_cekirdek` (27). Additional data collection required beyond E1 resolution.

### 3. Severity Estimator (geometric features → severity score)

| Requirement | Required | Current | Status |
|-------------|----------|---------|--------|
| Physical measurement labels | Required | None | **NO DATA** |
| E1 gate | CLEAR | PENDING | **BLOCKED** |

Physical measurement data has not been collected. Blocked independently of E1.

### 4. Multi-Defect Detector (YOLO-format)

| Requirement | Required | Current | Status |
|-------------|----------|---------|--------|
| Bounding box annotations | Required | None | **NO ANNOTATIONS** |
| Min training images | ≥ 500 | 0 bbox | **BLOCKED** |
| E1 gate | CLEAR | PENDING | **BLOCKED** |

Bounding box annotation campaign has not started.

### 5. Weld Quality Regressor (continuous quality score)

| Requirement | Required | Current | Status |
|-------------|----------|---------|--------|
| Destructive test results | Required | None | **NO DATA** |
| E1 gate | CLEAR | PENDING | **BLOCKED** |

Tensile/peel test data not collected. NEEDS_PHYSICAL_TEST decisions from E1 may surface candidates.

---

## Path to First GO

1. Complete E1 conflict review (175 decisions with notes)
2. Verify `e1_gate_clear: true` via `/api/v1/annotation/conflicts/review-summary`
3. Run `DatasetAudit.approve()`
4. Check `/api/v1/annotation/conflicts/eligible-counts` → `surface_classifier_go: true`
5. Surface binary classifier proceeds to Phase 4 training (if training_eligible ≥ 200)

All other models require additional data collection independent of E1.

---

## Reference

- `docs/E1_CONFLICT_REVIEW_QUEUE.csv` — 175 pairs awaiting review
- `docs/vision_validation/E1_REVIEW_PROGRESS.csv` — live metrics snapshot
- `docs/vision_validation/PHASE4_MODEL_READINESS.md` — P3H baseline
- `docs/vision_validation/VISION_P3H_DATASET_REMEDIATION_REPORT.md` — full dataset analysis
