# DATASET AUDIT REPORT
**Project:** SpotWeldPro AI — Vision Pipeline P3B (Updated)  
**Audited by:** Automated repository scan + external dataset discovery  
**Date:** 2026-11-13  
**Baseline commit:** e1af399 · Current HEAD: 091aa66  
**Audit status:** `NO_AUDIT` — training is **BLOCKED** for all deep/temporal models; CONDITIONAL for binary surface classifier with remediation

---

## 1. Repository data inventory (C:\Users\ilhan\SpotWeldPro-AI)

### 1.1 Image and video files in repo

| Category | Count | Location | Notes |
|----------|-------|----------|-------|
| Weld inspection images | **0** | — | None committed |
| Weld cross-section photos | **0** | — | None committed |
| Video files (MP4/AVI/MKV) | **0** | — | None committed |
| Marketing/UI images | 2 | `frontend/public/` | `spotweld-hero.png`, `spotweldpro-logo.png` — not weld data |

### 1.2 Tabular / structured data files in repo

| Format | Count | Notes |
|--------|-------|-------|
| CSV | **0** | None committed |
| Excel / Parquet | **0** | None committed |
| SQLite database | **0** | No `.db` file committed (created at runtime) |
| JSON data | 1 | `backend/app/domain/model4_full.json` — model coefficients only |

**Result: Zero weld training data exists in the repository.**

### 1.3 The "806 records" — confirmed status

The number 806 appears in `backend/app/domain/model_catalog.py` (lines 231–236) in the description of `model4_doe_polynomial`:

> *"Cooling, Sequence and Holding inputs are structurally absent from the **806-record validation dataset**"*

- The dataset file is **not present** in the repository
- Records are process parameter records (current, force, time), **not** labeled images
- Cooling, Sequence, and Holding columns structurally absent — Model-4 (7 inputs) cannot be validated against them
- Label source classification: `UNVERIFIED` (source undocumented, file absent, structural gaps)

---

## 2. External dataset inventory (not in repo)

### 2.1 V5 Surface Inspection Dataset

**Location:** `D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\V5_dataset\`  
**Created:** 2026-07-07  
**This dataset is not committed to the SpotWeldPro-AI repository.**

| Metric | Value |
|--------|-------|
| Total images | **927** |
| OK (accepted) | 139 (15.0%) |
| NOK (all defect classes combined) | 788 (85.0%) |
| Defect classes | 12 |
| Train split | 540 |
| Validation split | 183 |
| Test split | 204 |
| Exact duplicate candidates (by SHA1) | **355 pairs** |
| Images with colored annotation markup | **511 / 927** |
| Resolution range | Variable (varies from ~100px to ~3400px wide) |
| Format | PNG (majority), JPG |

#### 2.1.1 Class distribution

| Label (Turkish) | English | Total | Train | Val | Test | Independent groups |
|-----------------|---------|-------|-------|-----|------|--------------------|
| `ok` | Accepted | 139 | 83 | 28 | 28 | 139 |
| `generic_bad` | Generic NOK | 399 | 239 | 80 | 80 | 399 |
| `capak` | Spatter/Flash | 112 | 59 | 18 | 35 | 39 |
| `deformeli` | Deformed | 54 | 50 | 1 | 3 | 6 |
| `kopuk` | Broken | 46 | 28 | 10 | 8 | 32 |
| `eksik` | Missing | 32 | 18 | 8 | 6 | 23 |
| `kucuk_cekirdek` | Small nugget | 27 | 4 | 1 | 22 | 4 |
| `kacik` | Misaligned | 27 | 15 | 4 | 8 | 21 |
| `ust_uste` | Overlapping | 27 | 2 | 22 | 3 | 3 |
| `kenar` | Edge weld | 25 | 15 | 5 | 5 | 21 |
| `delik` | Hole/Burn | 21 | 13 | 5 | 3 | 12 |
| `cift_sac` | Double sheet | 14 | 10 | 1 | 3 | 6 |
| `cokertme` | Crush/Dent | 4 | 4 | 0 | 0 | 2 |

#### 2.1.2 Critical data quality issues

**Issue 1 — Exact duplicate images across classes (355 pairs, HIGH severity):**  
355 image pairs share identical SHA1 hashes but carry different labels. The same physical image appears as both `generic_bad` (from `Puntanok_1.zip`, `Puntanok_2.zip`) and a specific defect class (from `Punta_hatalar 1.zip`, `Punta_hataları_2.zip`). Many of these pairs are split across train and test sets, creating **leakage**: the model may have been evaluated on images it effectively saw during training under a different label. No confident per-image test-set performance can be reported until duplicates are resolved.

**Issue 2 — Annotation contamination (511/927 images, HIGH severity):**  
511 images contain colored markup (red circles, green markers, blue arrows or text boxes drawn by quality inspectors). The dataset prep report explicitly warns: *"The model could learn these annotations or camera/source differences instead of weld quality."* The classifier trained on these images may have learned annotation presence as a defect indicator. All reported metrics are suspect until annotation-cleaned ROI crops are used.

**Issue 3 — Label source is SURFACE_OBSERVATION, not DESTRUCTIVE_TEST:**  
Labels come from visual inspection records (quality department stamps, production serial tags). There is no metallographic cross-section evidence linking any image to a measured nugget diameter. A visually OK weld can have an undersized nugget; a visually visible spatter (`capak`) does not necessarily mean weld failure. For safety-critical nugget acceptance the label source is **insufficient**.

**Issue 4 — Severe class imbalance with tiny test sets:**  
`cokertme` (n=4, 0 test samples), `kucuk_cekirdek` (22 test, 4 train), `ust_uste` (3 test, 2 train), `deformeli` (3 test, 50 train). No valid per-class precision/recall can be computed for classes with <5 test samples. The `kucuk_cekirdek` inversion (22 test, 4 train) is anomalous and suggests grouping by source archive rather than semantic identity.

**Issue 5 — Full-part photos not ROI-cropped:**  
Training on full-part photos including background, surrounding sheet metal, and inspection annotations. The dataset prep report recommends ROI cropping to weld-centered patches before training. This has not been done.

#### 2.1.3 Existing classical ML model

| Item | Value |
|------|-------|
| Model file | `spot_weld_model_v5_final_fast.joblib` (7.0 MB) |
| Feature cache | `v5_feature_cache_fast.joblib` (6.5 MB) |
| Created | 2026-07-07 |
| Architecture | Classical ML (scikit-learn / handcrafted features) |
| Binary decision | OK / REVIEW / NOK (3-way with thresholds p>0.42 / p<0.12) |

**Holdout results (177 test samples):**

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Test set size | 177 | 27 OK + 150 NOK |
| Auto-accept (p_good > 0.42) | 4 | 1 correct OK, 3 false accepts |
| Auto-reject (p_good < 0.12) | 58 | 55 correct NOK, 3 false rejects |
| Manual review | 115 (65%) | Undecided — requires human |
| False accept rate (NOK→OK) | 3/150 = **2.0%** | 3 defective welds classified as OK |
| False reject rate (OK→NOK) | 3/27 = **11.1%** | 3 good welds sent to rejection |
| True OK auto-accept rate | 1/27 = **3.7%** | Model almost never auto-clears good welds |

**Reliability caveat:** These metrics are computed on a test set that shares exact-duplicate images with the training set (355 duplicate pairs). The 2.0% FAR may be optimistic due to leakage. Without resolving duplicates and retraining on annotation-free ROI crops, these numbers cannot be used as acceptance criteria.

**Label source classification: `SURFACE_OBSERVATION`** — not `DESTRUCTIVE_TEST`.

### 2.2 Video files

| File | Location | Size | Date | Classification |
|------|----------|------|------|----------------|
| `Spot_Welding_Detection_6.7.2026.mp4` | `Punta hatalari_OpenCV\` | 28.4 MB | 2026-07-06 | Demo/marketing — visual demonstration of detection pipeline. Not labeled. Not a training dataset. |

**No labeled weld cycle videos exist anywhere.**

### 2.3 Pre-existing deep learning models (external, unrelated to SpotWeldPro-AI)

Found in `D:\makina_ogrenmesi\Otomotiv_punta\`: VGG16, VGG19, ResNet50, ResNet152, Inception-V3, InceptionResNetV2 — Keras `.h5` / `.keras` files from prior classification experiments (2021–2026). These were trained on a **different dataset** (punta/spot weld classification from Tofaş/automotive line). They are not integrated with SpotWeldPro-AI and their training data, performance metrics, and ground truth provenance are undocumented. They may **not** be used in SpotWeldPro-AI without documented revalidation.

---

## 3. Ground truth classification

| Source | Count | Category | Acceptable for training? |
|--------|-------|----------|--------------------------|
| Khuenkaew 2019 (published paper, 9 rows) | 9 rows | `ACCEPTED_REFERENCE` | Insufficient; material-specific (SUS316L+SUS425 1.5 mm) |
| 806-record validation dataset | 0 rows present | `UNVERIFIED` (file absent) | **NO** |
| V5 surface image dataset (927 images) | 927 images | `SURFACE_OBSERVATION` | **CONDITIONAL** — after duplicate resolution, annotation cleanup, ROI cropping; insufficient for nugget acceptance (no cross-section ground truth) |
| `test_results` table (runtime DB) | Unknown at audit time | Could be `DESTRUCTIVE_TEST` if properly recorded | **Requires manual review** |
| Vision pipeline images (repo) | 0 | — | **NO** — no images collected |
| Labeled weld cycle videos | 0 | — | **NO** — no video collected |

---

## 4. Temporal sequence availability

| Requirement | Status |
|-------------|--------|
| Sequential frame capture at known FPS | Infrastructure ready (Phase 2 `CaptureWorker`); **0 recordings exist** |
| Welding current signal (time-series) | Interface defined; **no stored data** |
| Welding force / displacement | Schema supports via `analysis_input` JSON; **no labeled time-series stored** |
| Synchronized vision + process signals | **Not implemented** — no timestamp join key |
| Weld cycle boundaries (ground truth) | `WeldEventWindow` heuristic only; **not validated on real welds** |

---

## 5. DatasetAudit gate status

```
NO_AUDIT.is_training_allowed() = False

Blocking conditions (all 7 remain for deep/temporal models):
  [1] No dataset file present in repository
  [2] 806-record dataset: undocumented source, structurally incomplete, file absent
  [3] Zero weld images committed to repo (V5 dataset is external, not committed)
  [4] No metallographic measurement records
  [5] No qualified reviewer assigned
  [6] No leakage-safe split defined (355 duplicate pairs must be resolved first)
  [7] No synchronized process signal data with timestamps

External V5 dataset — additional gates for binary surface classifier:
  [E1] 355 exact duplicate pairs must be resolved (deduplicated or one copy removed)
  [E2] Annotation-contaminated images must be excluded or replaced with ROI crops
  [E3] Split must be re-generated after deduplication
  [E4] Label source must be documented and accepted by qualified reviewer
```

---

## 6. Data collection specification (prioritized — updated)

### Priority 0 — Remediate existing V5 dataset (0–4 weeks, enables CONDITIONAL path)

1. Resolve 355 duplicate pairs: keep the labeled-defect version (e.g., `capak`) over the `generic_bad` duplicate; remove one copy from the dataset.
2. Exclude all 511 annotated images OR extract ROI crops that exclude annotation areas.
3. Re-generate train/val/test split after deduplication, grouping by `serial_id` / `source_archive`.
4. Document label source (`SURFACE_OBSERVATION` from production quality records), date range, camera setup, and any calibration metadata that exists.
5. Install `psutil` and `scikit-learn` in backend environment.

### Priority 1 — Minimum viable dataset for MLR/GPR nugget predictor (8–12 weeks)

Collect **80–150 weld specimens** with metallographic cross-sections. Each specimen requires:
- Nugget diameter measured with calibrated caliper on etched cross-section
- Recorded with: weld_id, part_id, session_id, production_batch, operator_id, date, instrument_id, measurement_report_ref
- Label source: `DESTRUCTIVE_TEST` only
- Split: group by weld_id; test set from a different production batch than training

### Priority 2 — Vision dataset for static defect detection (12–20 weeks)

Collect **≥500 labeled weld surface images** (target: 2000) linked to cross-section ground truth for OK/NOK assignment. Camera position, lighting, calibration target, and ROI coordinates must be documented.

### Priority 3 — Temporal video dataset (20–36 weeks, after Priority 2)

≥200 complete labeled weld cycles on video at ≥60 FPS, synchronized DAQ signals, with cycle boundaries from process signals and nugget ground truth from cross-section.

---

## 7. Summary

| Item | Finding |
|------|---------|
| Weld images in repo | **0** |
| Weld video files in repo | **0** |
| Labeled measurement data in repo | **0 rows** |
| External V5 surface image dataset | **927 images** (external only, not committed) — CONDITIONAL after remediation |
| 806 records | Process parameters only; file absent; undocumented; structurally incomplete |
| Any ground truth from destructive testing | **None** |
| `DatasetAudit.is_training_allowed()` | **False** (unchanged) |
| Blocking conditions cleared | **0 of 7** (repo-level gates) |
| External dataset — blocking data-quality gates | **4 of 4 open** (E1–E4) |
| Weeks to minimum viable surface classifier (Priority 0) | **0–4 weeks** (remediation of V5 dataset) |
| Weeks to minimum viable nugget predictor (Priority 1) | **8–12 weeks** |
