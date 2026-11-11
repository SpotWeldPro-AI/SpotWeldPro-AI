# DATASET AUDIT REPORT
**Project:** SpotWeldPro AI — Vision Pipeline P3B  
**Audited by:** Automated repository scan  
**Date:** 2026-11-11  
**Baseline commit:** e1af399  
**Audit status:** `NO_AUDIT` — training is **BLOCKED**

---

## 1. Repository data inventory

### 1.1 Image and video files

| Category | Count | Location | Notes |
|----------|-------|----------|-------|
| Weld inspection images | **0** | — | None exist in repository |
| Weld cross-section photos | **0** | — | None exist |
| Weld surface photos | **0** | — | None exist |
| Video files (MP4/AVI/MKV) | **0** | — | None exist |
| Marketing/UI images | 2 | `frontend/public/` | `spotweld-hero.png`, `spotweldpro-logo.png` — not weld data |

**Result: Zero weld images or video files exist in the repository.**

### 1.2 Tabular / structured data files

| Format | Count | Notes |
|--------|-------|-------|
| CSV | **0** | None committed |
| Excel (.xlsx/.xls) | **0** | None committed |
| Parquet | **0** | None committed |
| SQLite database | **0** | No `.db` file committed (created at runtime) |
| JSON data | 1 | `backend/app/domain/model4_full.json` — model coefficients only, not measurement data |

**Result: Zero measurement data files exist in the repository.**

### 1.3 The "806 records" — what they actually are

The number 806 appears in `backend/app/domain/model_catalog.py` lines 231–236 in the description of `model4_doe_polynomial`:

> *"Cooling, Sequence and Holding inputs are structurally absent from the **806-record validation dataset**; validation is not currently possible."*

**Findings:**
- The 806 records are process parameter records (current, force, time, etc.) from an **undocumented source** — they are not labeled images, not video frames, and not cross-section measurements.
- They are described as having **structural gaps**: the Cooling, Sequence, and Holding columns are absent from the dataset, making Model-4 (which requires all 7 inputs) un-validatable against them.
- The dataset file is **not present** anywhere in the repository. It is referenced in a comment but never committed.
- The model4_full.json coefficients (intercept = −70.3, 27 terms) carry `validation_status: "Experimental — requires calibration"`, confirming the model is not validated against these records.

**These 806 records are NOT:**
- Labeled weld OK/NOK images
- Video frames
- Cross-section measurements (metallographic)
- Usable as ground truth for any vision or temporal model

**Label source classification under DatasetAudit schema:** `UNVERIFIED` (source undocumented, file absent, structural gaps)

### 1.4 Database schema (from migrations 0001–0019)

The relational database defines the following tables:

| Table | Relevant columns | Vision relevance |
|-------|-----------------|-----------------|
| `weld_points` | `analysis_input` (JSON), `analysis_result` (JSON), `criticality`, `approval_status` | Process parameters only; no image foreign keys |
| `test_results` | `test_type`, `result_value`, `result_unit`, `acceptance_status`, `note` | Could hold destructive test results (nugget diameter) but no image link |
| `projects` | `project_code`, `customer`, `vehicle_platform` | Organizational context only |
| `users`, `audit_logs` | — | Access control |
| Engineering library tables (0011–0012) | Electrode/gun/schedule parameters | No measurement data |
| `import_batches` (0019) | Energy CSV import | Energy data, not weld geometry |

**No table stores image paths, video paths, frame timestamps, or labeled sequences.**

### 1.5 Existing model validation evidence

| Model ID | Governance | n_train | n_test | RMSE (mm) | R² | Dataset |
|----------|-----------|---------|--------|-----------|-----|---------|
| `oem_table` | VALIDATED | — | — | — | — | OEM acceptance criterion (reference threshold, not a predictor) |
| `literature_4sqrt_t` | VALIDATED | — | — | — | — | Published standard criterion (not a predictor) |
| `weld_lobe_v0_9` | **REJECTED** | 0 | 9 | 11.34 | −276.6 | Khuenkaew 2019 (Metals 9, 710), SUS316L+SUS425, 1.5 mm |
| `model4_doe_polynomial` | EXPERIMENTAL | None | None | None | None | 806-record dataset (undocumented, absent, structurally incomplete) |
| `mlr_v1` | EXPERIMENTAL | None | None | None | None | No dataset |
| `rsm_polynomial_v1` | NOT_AVAILABLE | None | None | None | None | No dataset |
| `gpr_v1` | NOT_AVAILABLE | None | None | None | None | Requires ≥15 metallographic records |
| `gbm_v1`, `pinn_v1`, `physics_hybrid_v1` | NOT_AVAILABLE | None | None | None | None | No dataset |

The only external dataset ever used in this repository is **Khuenkaew 2019 (9 rows)**, used solely to reject `weld_lobe_v0_9`.

---

## 2. Ground truth classification

| Source | Count | Category | Acceptable for training? |
|--------|-------|----------|--------------------------|
| Khuenkaew 2019 (published paper, 9 rows) | 9 rows | `ACCEPTED_REFERENCE` | Insufficient quantity; material-specific (SUS316L+SUS425 1.5 mm) |
| 806-record validation dataset | 0 rows present | `UNVERIFIED` (file absent) | **NO** — undocumented, absent, structurally incomplete |
| `test_results` table (runtime DB) | Unknown at audit time | Could be `DESTRUCTIVE_TEST` if properly recorded | **Requires manual review** — `test_type` is free text; no metadata enforces destructive test provenance |
| Vision pipeline images | 0 | — | **NO** — no images collected |
| Weld cycle videos | 0 | — | **NO** — no video collected |

---

## 3. Temporal sequence availability

| Requirement | Status |
|-------------|--------|
| Sequential frame capture at known FPS | Infrastructure ready (Phase 2 `CaptureWorker`); **0 recordings exist** |
| Welding current signal (time-series) | `dynamic_resistance.py` accepts `samples_micro_ohm`; **no stored data** |
| Welding force / displacement | Schema supports via `analysis_input` JSON; **no labeled time-series stored** |
| Synchronized vision + process signals | **Not implemented** — no timestamp join key between vision frames and process parameters |
| Weld cycle boundaries (ground truth) | `WeldEventWindow` detects motion onset (heuristic); **not validated against real welds** |

---

## 4. DatasetAudit gate status

```
NO_AUDIT.is_training_allowed() = False

Reason: "Dataset status is DRAFT; must be APPROVED."

Blocking conditions:
  [1] No dataset file present in repository
  [2] 806-record dataset: undocumented source, structurally incomplete, file absent
  [3] Zero weld images or video frames collected
  [4] No metallographic measurement records (nugget_diameter_mm linked to weld_id)
  [5] No qualified reviewer assigned
  [6] No leakage-safe split defined (grouping by weld_id/part_id/session_id/batch)
  [7] No synchronized process signal data with timestamps
```

---

## 5. Data collection specification (prioritized)

### Priority 1 — Minimum viable dataset for MLR/GPR nugget predictor (8–12 weeks)

Collect at minimum **80 weld specimens** (target: 150) across the production parameter space:

| Parameter | Range to cover | Levels |
|-----------|---------------|--------|
| Sheet thickness (mm) | 0.6 – 2.5 | ≥4 levels |
| Material family | Mild steel, AHSS/UHSS, GI-coated | ≥2 materials |
| Current (kA) | Per OEM lobe for each thickness | ≥3 levels |
| Force (kN) | Per OEM spec | ≥3 levels |
| Weld time (cycles) | Per OEM spec | ≥3 levels |

**Ground truth requirement (mandatory):**
- Physical cross-section (metallographic) of each weld specimen
- Nugget diameter measured with calibrated caliper on etched cross-section
- Each measurement recorded with: weld_id, part_id, session_id, production_batch, operator_id, date, instrument_id, measurement_report_ref
- Label source: `DESTRUCTIVE_TEST` only
- Minimum: 2 independent cross-sections per weld (measure both and report average + range)

**Split requirement:**
- Group by weld_id — all measurements from the same physical weld go to the same split
- 70% train / 15% validation / 15% test
- Test set: welds from a different production batch than the training set

### Priority 2 — Vision dataset for static defect detection (12–20 weeks)

Collect **≥500 labeled weld surface images** (target: 2000):

| Class | Min samples | Defect types |
|-------|-------------|-------------|
| OK (acceptable nugget) | 300 | Confirmed by cross-section |
| Surface splash / expulsion | 50 | Visible spatter ring |
| Indentation defect | 50 | Electrode impression depth > spec |
| Electrode contamination | 50 | Discolouration, pitting pattern |
| NOK — undersized nugget | 100 | Confirmed by cross-section (critical: ground truth required) |

**Image capture requirements:**
- Fixed camera position and lighting (document exact setup)
- Calibration target in every session (mm scale for `pixels_per_mm`)
- Linked to: weld_id, part_id, session_id, production_batch, timestamp_utc
- Label source: `DESTRUCTIVE_TEST` for OK/NOK; `ACCEPTED_REFERENCE` for surface defect types with established reference images

### Priority 3 — Temporal video dataset for CNN-GRU/LSTM (20–36 weeks, after Priority 2)

Collect **≥200 complete weld cycles** on video:

- 60 FPS minimum; 1080p recommended; fixed focal length
- Synchronized process signals: current (kA vs time), force (kN vs time), displacement (mm vs time) at ≥10 kHz via DAQ
- Weld cycle boundaries from process signal (current onset/offset), not from motion detection
- Label each cycle from cross-section (destructive) of the same weld
- Store: video file path, cycle start/end frame, synchronized process signal file, weld_id, nugget_mm
- Minimum: 100 OK cycles + 100 NOK cycles (or defect-specific subcategories)

---

## 6. Summary

| Item | Finding |
|------|---------|
| Weld images in repo | **0** |
| Weld video files in repo | **0** |
| Labeled measurement data | **0 rows present** |
| 806 records | Process parameters only; file absent; undocumented; structurally incomplete |
| Any ground truth from destructive testing | **None** |
| `DatasetAudit.is_training_allowed()` | **False** |
| Blocking conditions cleared | **0 of 7** |
| Weeks to minimum viable dataset (Priority 1) | **8–12 weeks** |
