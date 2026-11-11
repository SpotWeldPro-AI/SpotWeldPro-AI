# TRAINING READINESS MATRIX
**Project:** SpotWeldPro AI — Vision Pipeline P3B  
**Date:** 2026-11-11  
**Baseline commit:** e1af399

Legend: ✅ Ready · ⚠️ Conditional · ❌ Blocked · 🔲 Not started

---

## GO / NO-GO decisions

| Model / Task | Decision | Blocker summary |
|---|---|---|
| OEM reference table (acceptance criterion) | ✅ **DEPLOYED** | Already in production; not a predictor |
| 4√t literature criterion | ✅ **DEPLOYED** | Already in production; not a predictor |
| Static defect detection (CNN classifier) | ❌ **NO-GO** | 0 weld images collected |
| Nugget diameter from image (regression) | ❌ **NO-GO** | 0 calibrated cross-section images |
| Video anomaly classification | ❌ **NO-GO** | 0 video files collected |
| CNN-GRU sequence classifier | ❌ **NO-GO** | 0 labeled weld cycles; no synchronized signals |
| CNN-LSTM sequence classifier | ❌ **NO-GO** | Same as CNN-GRU |
| Sensor fusion (vision + process signal) | ❌ **NO-GO** | No timestamp join key; no synchronized DAQ data |
| Model-4 DOE polynomial validation | ❌ **NO-GO** | 806-record dataset absent; Cooling/Seq/Hold columns missing |
| MLR (mlr_v1) calibration | ⚠️ **CONDITIONAL** | Requires ≥15 metallographic records (Priority 1 collection) |
| GPR (gpr_v1) calibration | ⚠️ **CONDITIONAL** | Requires ≥15 metallographic records with independent test set |
| RSM polynomial calibration | ⚠️ **CONDITIONAL** | Requires CCD/BBD experimental design data |
| Gradient Boosting (gbm_v1) | ❌ **NO-GO** | Requires ≥80–150 metallographic records |
| Physics hybrid / PINN | ❌ **NO-GO** | Requires calibration data + FEA validation |

---

## Detailed readiness by task

### Task 1 — Static defect detection

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| Weld surface images | ≥500 labeled | 0 | ❌ |
| Cross-section ground truth for OK/NOK | Required for NOK class | 0 | ❌ |
| Camera calibration (pixels_per_mm) | Fixed setup documented | Not done | ❌ |
| Class balance (OK:NOK) | ≥1:3 NOK fraction recommended | N/A | ❌ |
| Leakage-safe split by weld_id | Required | Not defined | ❌ |
| DatasetAudit APPROVED | Required | DRAFT (NO_AUDIT) | ❌ |

**Decision: NO-GO — 6/6 gates blocked.**

---

### Task 2 — Nugget diameter measurement from image

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| Calibrated cross-section images | ≥200 | 0 | ❌ |
| Caliper measurement of each specimen | Required | 0 | ❌ |
| Known pixels_per_mm per image | Required | Not recorded | ❌ |
| Metallographic technique documented | Required | Not done | ❌ |

**Decision: NO-GO — 4/4 gates blocked.**

---

### Task 3 — CNN-GRU / CNN-LSTM temporal classification

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| Labeled weld cycle videos | ≥200 cycles (100 OK + 100 NOK) | 0 | ❌ |
| Synchronized process signal (current, force, displacement) | ≥10 kHz DAQ | 0 files | ❌ |
| Cycle boundary from process signal | Required (not from motion detector) | Not implemented | ❌ |
| Cross-section ground truth per cycle | Required | 0 | ❌ |
| Sequential frame continuity in splits | Required | Not defined | ❌ |
| is_causal=True architecture | Required for real-time | Interface defined ✅ | ⚠️ |
| DatasetAudit APPROVED | Required | DRAFT | ❌ |
| CURRENT_PLAN.deployment_allowed() | False | False | ❌ |

**Decision: NO-GO — 7/8 gates blocked.**

---

### Task 4 — Model-4 DOE polynomial validation

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| 806-record dataset file present | Required | File absent | ❌ |
| Cooling column present | Required for 7-variable model | Structurally absent | ❌ |
| Sequence column present | Required | Structurally absent | ❌ |
| Holding column present | Required | Structurally absent | ❌ |
| Nugget diameter measurements linked | Required | Not documented | ❌ |
| Dataset source documented | Required | Undocumented | ❌ |

**Decision: NO-GO — 6/6 gates blocked.  
Model-4 router will remain `router_active=False` until all gates clear.**

---

### Task 5 — MLR / GPR calibration (conditional path, Priority 1)

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| Metallographic records with nugget_diameter_mm | ≥15 (GPR), ≥50 (MLR) | 0 | ❌ |
| weld_id linkage | Required | Not recorded | ❌ |
| Independent test set (different batch) | Required | Not defined | ❌ |
| Cross-section report reference per record | Required | Not recorded | ❌ |
| DatasetAudit APPROVED | Required | DRAFT | ❌ |

**Decision: CONDITIONAL — achievable in 8–12 weeks (see Priority 1 collection spec).  
These are the first models that become trainable once Priority 1 data is collected.**

---

## Infrastructure readiness

| Component | Status | Notes |
|-----------|--------|-------|
| `CaptureWorker` (Phase 2) | ✅ Ready | Daemon thread, bounded queue, timestamps, reconnect |
| `MotionEventDetector` | ✅ Ready | Deterministic MAD baseline; not a weld quality classifier |
| `WeldEventWindow` | ✅ Ready | 4-state machine; not validated on real welds |
| `LiveSessionManager` | ✅ Ready | 8-source/8-WS limit enforced |
| `WebcamAdapter` / `RTSPAdapter` | ⚠️ Interface only | Not hardware-validated |
| `StaticInspectionPage.tsx` | ✅ Ready | Upload + result display; awaits real images |
| `LiveMonitoringPage.tsx` | ✅ Ready | Real-time metrics, motion log, weld window history |
| `POST /vision/static/inspect` | ✅ Ready | Stateless; returns indicators from actual image analysis |
| `DatasetAudit` gate | ✅ Ready | `is_training_allowed()` enforced |
| `ModelValidationPlan` gate | ✅ Ready | `deployment_allowed()` = False |
| `NotLoadedExtractor` / `NotLoadedClassifier` | ✅ Ready | Sentinels raise on call |
| Feature extractor (CNN weights) | ❌ Not loaded | No model weights exist |
| Sequence classifier (GRU/LSTM weights) | ❌ Not loaded | No model weights exist |
| scikit-learn dependency | ⚠️ Not approved | Required for GPR, MLR, GBM |
| psutil | ⚠️ Not installed | Benchmark CPU%/RSS reports None |

---

## Test suite status (2026-11-11)

| Suite | Tests | Result |
|-------|-------|--------|
| Vision Phase 1 | 53 | ✅ 53 PASS |
| Vision Phase 2 | 91 | ✅ 91 PASS |
| Vision Phase 3 | 27 | ✅ 27 PASS |
| **Total vision** | **171** | ✅ **171 PASS** |
| Pre-existing failures (non-vision) | 137 | ❌ 137 FAIL (baseline, unchanged from pre-Phase 1) |

Pre-existing failures are confined to: `test_registry_persistence`, `test_parameter_engine_01b2`, `test_api_digital_weld_passport`, `test_draft_evidence_revision`, `test_api_machine_readiness`, `test_gate07_demo_login`, and others. None involve vision code.

---

## Recommended next actions (ordered)

1. **Immediately:** Install `psutil` (`pip install psutil`) to enable CPU%/RSS in benchmarks.
2. **Week 1–2:** Define and document the metallographic measurement protocol. Agree on weld_id schema, instrument calibration procedure, and cross-section report template.
3. **Week 2–8:** Execute Priority 1 data collection (80–150 weld specimens, destructive cross-section).
4. **Week 8:** Create `DatasetAudit` record with `status=UNDER_REVIEW`, populate `ClassStatistics`, define `SplitDescriptor`. Assign qualified reviewer.
5. **Week 10:** After reviewer approval, set `status=APPROVED`. MLR and GPR calibration can begin.
6. **Week 10–12:** Train and evaluate MLR (`mlr_v1`) and GPR (`gpr_v1`) against held-out test set. Record `actual_metrics` in `ExperimentSpec`.
7. **After MLR/GPR results:** Update `model_catalog.py` with `n_train`, `n_test`, `rmse_mm`, `r2`, `dataset_name`.
8. **Parallel (ongoing):** Begin Priority 2 image collection. Add `image_path` and `pixels_per_mm` columns to `weld_points` or a new `weld_images` table.
9. **Do not start** CNN, GRU/LSTM, or temporal model work until Priority 2 collection is complete and a second `DatasetAudit` record is approved.
