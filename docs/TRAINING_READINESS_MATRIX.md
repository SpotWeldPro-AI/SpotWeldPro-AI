# TRAINING READINESS MATRIX
**Project:** SpotWeldPro AI — Vision Pipeline P3B (Updated)  
**Date:** 2026-11-13  
**Baseline commit:** e1af399 · Current HEAD: 091aa66

Legend: ✅ Ready · ⚠️ Conditional · ❌ Blocked · 🔲 Not started

---

## GO / NO-GO decisions

| Model / Task | Decision | Blocker summary |
|---|---|---|
| OEM reference table (acceptance criterion) | ✅ **DEPLOYED** | Already in production; not a predictor |
| 4√t literature criterion | ✅ **DEPLOYED** | Already in production; not a predictor |
| Binary surface classifier (OK/NOK) — V5 dataset | ⚠️ **CONDITIONAL** | External dataset exists; 4 remediation gates open (see §Task 1b) |
| Static defect detection (repo-committed dataset) | ❌ **NO-GO** | 0 weld images committed to repo |
| Nugget diameter from image (regression) | ❌ **NO-GO** | 0 calibrated cross-section images |
| Video anomaly classification | ❌ **NO-GO** | 0 labeled video files collected |
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

### Task 1a — Static defect detection (new dataset from scratch)

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| Weld surface images committed to repo | ≥500 labeled | 0 | ❌ |
| Cross-section ground truth for OK/NOK | Required for NOK class | 0 | ❌ |
| Camera calibration (pixels_per_mm) | Fixed setup documented | Not done | ❌ |
| Leakage-safe split by weld_id | Required | Not defined | ❌ |
| DatasetAudit APPROVED | Required | DRAFT (NO_AUDIT) | ❌ |

**Decision: NO-GO — 5/5 gates blocked.**

---

### Task 1b — Binary surface classifier using existing V5 external dataset

**New finding (2026-11-13):** An external dataset exists at  
`D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\V5_dataset\`  
with 927 labeled images (139 OK, 788 NOK in 12 defect classes) and a trained classical ML model (`spot_weld_model_v5_final_fast.joblib`).

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| Images exist | ≥500 labeled | 927 available | ✅ |
| Binary OK/NOK labels | Required | Present (surface observation) | ⚠️ SURFACE_OBSERVATION only |
| Cross-section ground truth | Required for safety-critical nugget accept | **None** | ❌ for nugget; ⚠️ for surface-only classifier |
| Duplicate resolution | 0 cross-split duplicates | 355 exact-duplicate pairs found | ❌ |
| Annotation cleanup | No colored markings | 511/927 images contaminated | ❌ |
| ROI crops | Weld-centered patches | Full-part photos only | ❌ |
| Split re-generated post-dedup | Required | Current split has leakage | ❌ |
| Label provenance documented | Required | Partially (serial numbers exist) | ⚠️ |
| DatasetAudit APPROVED | Required | DRAFT | ❌ |

**Decision: CONDITIONAL — 4/8 blocking gates remain (E1–E4).  
Remediation path: 0–4 weeks (Priority 0 in DATASET_AUDIT_REPORT.md).**

#### Existing classifier performance (pre-remediation, treat as INDICATIVE only)

| Metric | Value | Note |
|--------|-------|------|
| Test set | 177 samples (27 OK, 150 NOK) | May contain leakage duplicates |
| Auto-accept rate (good welds cleared) | 1/27 = 3.7% | Very conservative |
| False accept rate (bad welds cleared) | 3/150 = **2.0%** | Suspect until leakage resolved |
| False reject rate (good welds rejected) | 3/27 = **11.1%** | — |
| Manual review rate | 115/177 = **65%** | Most samples undecided |
| Label source | `SURFACE_OBSERVATION` | Not `DESTRUCTIVE_TEST` |

**These metrics are NOT acceptance criteria.** They are indicative of the existing classical model on a leaky, annotation-contaminated test set. After remediation (Priority 0), re-evaluate before treating as production metrics.

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
| Labeled weld cycle videos | ≥200 cycles | 0 labeled | ❌ |
| Synchronized process signal (current, force, displacement) | ≥10 kHz DAQ | 0 files | ❌ |
| Cycle boundary from process signal | Required | Not implemented | ❌ |
| Cross-section ground truth per cycle | Required | 0 | ❌ |
| Sequential frame continuity in splits | Required | Not defined | ❌ |
| is_causal=True architecture | Required for real-time | Interface defined ✅ | ⚠️ |
| DatasetAudit APPROVED | Required | DRAFT | ❌ |

**Decision: NO-GO — 6/7 gates blocked.**  
*Note: 1 demo MP4 exists (28.4 MB, 2026-07-06) but is a marketing demonstration video — no labels, no process signals, not a training dataset.*

---

### Task 4 — Model-4 DOE polynomial validation

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| 806-record dataset file present | Required | File absent | ❌ |
| Cooling column present | Required for 7-variable model | Structurally absent | ❌ |
| Sequence column present | Required | Structurally absent | ❌ |
| Holding column present | Required | Structurally absent | ❌ |

**Decision: NO-GO — 4/4 gates blocked.**

---

### Task 5 — MLR / GPR calibration (conditional path, Priority 1)

| Gate | Required | Current state | Status |
|------|----------|---------------|--------|
| Metallographic records with nugget_diameter_mm | ≥15 (GPR), ≥50 (MLR) | 0 | ❌ |
| weld_id linkage | Required | Not recorded | ❌ |
| Independent test set (different batch) | Required | Not defined | ❌ |
| Cross-section report reference per record | Required | Not recorded | ❌ |
| DatasetAudit APPROVED | Required | DRAFT | ❌ |

**Decision: CONDITIONAL — achievable in 8–12 weeks (Priority 1 collection).  
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
| `POST /vision/static/inspect` | ✅ Ready | Returns indicators from actual image analysis |
| `DatasetAudit` gate | ✅ Ready | `is_training_allowed()` enforced |
| `ModelValidationPlan` gate | ✅ Ready | `deployment_allowed()` = False |
| `NotLoadedExtractor` / `NotLoadedClassifier` | ✅ Ready | Sentinels raise on call |
| Feature extractor (CNN weights) | ❌ Not loaded | No model weights exist |
| Sequence classifier (GRU/LSTM weights) | ❌ Not loaded | No model weights exist |
| External V5 classical model | ⚠️ External only | `spot_weld_model_v5_final_fast.joblib` exists externally; not integrated |
| scikit-learn dependency | ⚠️ Not in requirements | Required for GPR, MLR, GBM, and V5 model integration |
| psutil | ⚠️ Not installed | Benchmark CPU%/RSS reports None |

---

## Test suite status (2026-11-13)

| Suite | Tests | Result |
|-------|-------|--------|
| Vision Phase 1 | 53 | ✅ 53 PASS |
| Vision Phase 2 | 91 | ✅ 91 PASS |
| Vision Phase 3 | 27 | ✅ 27 PASS |
| **Total vision** | **171** | ✅ **171 PASS** |
| All backend tests (excluding collection-error files) | 1275 | ✅ 1275 PASS |
| Pre-existing failures (non-vision) | 122 | ❌ 122 FAIL (baseline, unchanged) |
| Collection errors (postgresql / missing deps) | 11 files | ❌ COLLECTION ERROR (pre-existing) |

Pre-existing failures include: `test_rule_registry_service`, `test_deploy_config`, and infrastructure-dependent tests. None involve vision code.

---

## Recommended next actions (ordered)

1. **Immediately (Priority 0):** Resolve V5 dataset quality issues:
   - Deduplicate: remove exact-duplicate cross-label images (keep specific-label version)
   - Exclude annotated images or extract annotation-free ROI crops
   - Re-generate splits with group-safe shuffling
   - Document: label provenance, camera setup, date range
2. **Week 1:** Install `psutil` and `scikit-learn` in backend.
3. **Week 1–2:** Decide whether to integrate the V5 classical model into the SpotWeldPro-AI pipeline (after remediation). If yes, add `v5_classical_model.joblib` to repo under a documented data management policy.
4. **Week 2–8:** Execute Priority 1 metallographic collection (80–150 specimens).
5. **Week 8:** Create `DatasetAudit` record for Priority 1 dataset, assign qualified reviewer.
6. **Week 10:** After approval, begin MLR/GPR calibration.
7. **Do not start** CNN, GRU/LSTM, or temporal model work until Priority 2 collection is complete.
