# MODEL READINESS REPORT
**Project:** SpotWeldPro AI — Vision P3C  
**Date:** 2026-11-13  
**Classifier evaluated:** `v5_final_fast` (classical ML, `spot_weld_model_v5_final_fast.joblib`)  
**Decision thresholds:** accept p_good > 0.42 · reject p_good < 0.12 · else REVIEW  
**Label provenance:** `SURFACE_OBSERVATION` — visual inspection records only  

---

## 1. Original vs leakage-safe test set

| Metric | Original (177) | Leakage-safe |
|--------|---------------|---------------|
| Test samples | 177 | 144 |
| OK samples | 27 | 27 |
| NOK samples | 150 | 117 |
| Auto-accept | 4 | 4 |
| Auto-reject | 58 | 50 |
| Review | 115 | 90 |
| False accepts (NOK→OK) | 3 | 3 |
| False rejects (OK→NOK) | 3 | 3 |

## 2. Leakage-safe evaluation (n=144)

**False accept rate (FAR):** 3/117 = **2.6%** (95% CI 0.9%–7.3%)  
**False reject rate (FRR):** 3/27 = **11.1%** (95% CI 3.9%–28.1%)  
**Manual review rate:** 90/144 = 62.5%  
**Auto-accept rate:** 4/144 = 2.8%  
**Auto-reject rate:** 50/144 = 34.7%  

## 3. Confusion matrix — auto-decided leakage-safe samples

*(Excludes 90 review-routed samples; based on 54 auto-decided images)*

```
                 Predicted OK   Predicted NOK
  Actual OK            1              3
  Actual NOK           3             47
```

- True OK auto-cleared: 1 / 27 OK images  
- False accept (NOK→OK): 3  
- False reject (OK→NOK): 3  
- True NOK auto-rejected: 47  

## 4. Reliability caveats

1. **Label source is `SURFACE_OBSERVATION`** — these metrics measure surface visual defect detection performance, not nugget quality acceptance. A weld classified OK by this model may still have an undersized nugget.  
2. **Annotation contamination** — HIGH/MEDIUM contamination images remain in this evaluation. The classifier may partially rely on annotation markings.  
3. **Small OK sample size** — the leakage-safe OK subset has 27 samples. FRR confidence interval is wide; treat with caution.  
4. **Model not integrated** — `v5_final_fast.joblib` is not committed to the SpotWeldPro-AI repository. These metrics cannot be reproduced by CI.  

## 5. Demo MP4 audit

**File:** `Spot_Welding_Detection_6.7.2026.mp4`  
**File size:** 28.4 MB  
**Duration:** 142.8 s  
**Resolution:** 1244 × 684  
**FPS:** 30.0  
**Codec:** h264  
**Frame count:** 4284  

**Suitability assessment:**  
- This is a **marketing demonstration video** created 2026-07-06.  
- It has **no weld cycle labels**, no process signal synchronization, and no cross-section ground truth.  
- It **MUST NOT** be used as labeled training data for any model.  
- It MAY be used to validate the vision pipeline's motion detection and frame capture infrastructure against a real camera stream.  

## 6. GO/NO-GO matrix — updated after leakage analysis

| Model / Task | Decision | Key reason |
|---|---|---|
| OEM reference table (acceptance criterion) | ✅ **DEPLOYED** | Reference threshold, not a predictor |
| 4√t literature criterion | ✅ **DEPLOYED** | Reference threshold, not a predictor |
| Binary surface classifier (v5_final_fast) | ⚠️ **CONDITIONAL** | Leakage-safe FAR=2.6% on n=117 NOK; annotation contamination and label conflicts must be resolved; SURFACE_OBSERVATION labels only |
| Multi-class surface defect detection | ⚠️ **CONDITIONAL** | Major classes viable after dedup+ROI; minor classes (≤4 train samples) remain NO-GO |
| Nugget diameter from image | ❌ **NO-GO** | No calibrated cross-section images; label source is SURFACE_OBSERVATION |
| Video anomaly classification | ❌ **NO-GO** | 0 labeled video files |
| CNN-GRU sequence classifier | ❌ **NO-GO** | 0 labeled weld cycles; no process signals |
| CNN-LSTM sequence classifier | ❌ **NO-GO** | Same as CNN-GRU |
| Sensor fusion (vision + process) | ❌ **NO-GO** | No synchronized DAQ data |
| MLR / GPR nugget predictor | ⚠️ **CONDITIONAL** | Requires Priority 1 metallographic collection (8–12 wk) |
| Model-4 DOE polynomial | ❌ **NO-GO** | 806-record dataset absent; 3 columns missing |

## 7. Data still required

| Priority | Task | Timeline | Unlocks |
|----------|------|----------|---------|
| P0 | V5 dataset remediation (dedup, ROI, resplit) | 0–4 weeks | Surface classifier training |
| P1 | 80–150 metallographic weld specimens (nugget_mm) | 8–12 weeks | MLR, GPR calibration |
| P2 | ≥500 labeled surface images with cross-section GT | 12–20 weeks | Nugget-linked vision model |
| P3 | ≥200 labeled weld cycle videos + 10 kHz DAQ | 20–36 weeks | CNN-GRU/LSTM, sensor fusion |
