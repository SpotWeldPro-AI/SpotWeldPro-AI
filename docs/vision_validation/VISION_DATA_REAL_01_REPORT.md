# VISION-DATA-REAL-01: Real Weld Dataset Qualification Report
# SpotWeldPro AI

**Date:** 2026-11-18  
**Task:** VISION-DATA-REAL-01  
**HEAD commit:** 76742d1  
**Branch:** main  
**Status:** TRAINING_NO_GO — All 5 model families blocked pending E1–E4 resolution

---

## 1. Executive Summary

The V5 real weld dataset (927 annotated images, 13 label classes) has been fully audited across all nine qualification steps. **All five model families are blocked from training.** The primary blocker is 175 unresolved E1 duplicate/conflict pairs — none have been adjudicated by a human reviewer. Additionally: 416/927 images (44.9%) have MEDIUM or HIGH annotation contamination; train/test split leakage has been detected in 53 SHA1 collisions; and all 927 ground-truth labels are SURFACE_OBSERVATION only (0 destructive tests). The real video footage is currently unreadable by OpenCV.

---

## 2. Repository and Dataset Audit

### 2.1 HEAD Verification

```
HEAD:   76742d1  (VISION-SYNTH-E2E-05 — not pushed)
Branch: main
Tree:   clean (only tsconfig.tsbuildinfo modified + untracked deliverables)
```

### 2.2 Real Image Dataset

| Property | Value |
|---|---|
| Dataset location | D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\V5_dataset\raw_images\ |
| Total annotated records (ANNOTATION_AUDIT.csv) | 927 |
| Label classes | 13 |
| Physical directory accessible | YES |
| Physical image count matches annotation CSV | YES (confirmed per-class) |

**Label distribution:**

| Label (TR) | Label (EN) | Count | % of dataset |
|---|---|---|---|
| generic_bad | Generic NOK | 399 | 43.0% |
| ok | Accepted | 139 | 15.0% |
| capak | Spatter/Flash | 112 | 12.1% |
| deformeli | Deformed Electrode | 54 | 5.8% |
| kopuk | Broken Weld | 46 | 5.0% |
| eksik | Missing Weld | 32 | 3.5% |
| kucuk_cekirdek | Small Nugget Indicator | 27 | 2.9% |
| kacik | Misaligned Weld | 27 | 2.9% |
| ust_uste | Overlapping Weld | 27 | 2.9% |
| kenar | Edge Weld | 25 | 2.7% |
| delik | Burn-Through | 21 | 2.3% |
| cift_sac | Double Sheet | 14 | 1.5% |
| cokertme | Crush Dent | 4 | 0.4% |

**Split distribution:** train=540 (58.3%), val=183 (19.7%), test=204 (22.0%)

### 2.3 Source Archives

| Archive | Role | Physical location |
|---|---|---|
| Okpunta.zip | OK weld images | train/good/ |
| Puntanok.1.zip | Generic NOK archive 1 | train/bad/ |
| Puntanok_2.zip | Generic NOK archive 2 | train/bad/ |
| Puntanok._3.zip | Generic NOK archive 3 | train/bad/ |
| Punta_hatalar 1.zip | Specific defect archive | Referenced in audit; not found in train/ |

**Warning:** `Punta_hatalar 1.zip` is referenced in the annotation audit CSV but was not found in the `train/` directory during this audit. Its images are physically present in the V5 dataset raw_images directory via a previous extraction. The ZIP archive itself should be located and preserved for provenance traceability.

### 2.4 Prior Trained Models (Pre-Gate Warning)

The following models exist at `D:\makina_ogrenmesi\Otomotiv_punta\` and were trained before E1–E4 controls were established:

- `spot_weld_model_v5_final_fast.joblib` (Random Forest/SVM)
- `VGG16_model.h5`, `VGG19_model.h5`, `Xception_model.h5`, `InceptionResNetV2_model.h5`, `ResNet152_model.h5` (deep CNN)
- `Eski/spot_weld_model.joblib`, `_balanced.joblib`, `_safe.joblib` (earlier traditional ML)

**These models must NOT be deployed for production weld quality acceptance.** Their training data had 416 contaminated records, 175 unresolved conflicts, and cross-split leakage. See `TEMPORAL_REAL_DATA_READINESS.md` §5 for full details.

---

## 3. E1 Human Review Preparation

### 3.1 Conflict Queue

| Metric | Value |
|---|---|
| Total conflict pairs | 175 |
| Decisions made | 0 |
| E1 gate clear | NO |
| BOTH (leakage + label conflict) | 51 |
| LABEL_CONFLICT only | 122 |
| CROSS_SPLIT_LEAKAGE only | 2 |

**All 175 pairs are PENDING_REVIEW. No automatic adjudication has been performed.**

### 3.2 Review Queue Priority Order

The `E1_HUMAN_REVIEW_PRIORITY.csv` organizes conflicts in priority order:
1. **Priority 1–51: BOTH** — Same image has both a label conflict AND appears in multiple splits. Highest impact on data quality. Reviewer must examine both images and choose a label AND a split assignment.
2. **Priority 52–173: LABEL_CONFLICT** — Same image hash found with two different labels across archives. Reviewer must confirm the correct specific-defect label.
3. **Priority 174–175: CROSS_SPLIT_LEAKAGE** — Same OK weld image in both train and test. Reviewer must assign to one split.

### 3.3 Access Control Verification

The ConflictReviewPage requires `QUALITY_ENGINEER` role. The backend permission check at `/api/v1/vision/conflicts` enforces this. 22/22 API permission tests PASS (from VISION_P3I_HUMAN_REVIEW_REPORT.md).

### 3.4 Available Decision Types

| Decision | When to use |
|---|---|
| KEEP_A | Retain image A's label; discard B's label for training |
| KEEP_B | Retain image B's label; discard A's label |
| KEEP_BOTH | Both copies are distinct enough to keep with their respective labels |
| EXCLUDE_BOTH | Both copies are ambiguous or low quality; exclude from training |
| CONFIRM_LABEL | The specific-defect label is correct; reject the generic_bad duplicate |
| CORRECT_LABEL | A specific label was mislabeled; correct it to the stated label |
| EXCLUDE_FROM_TRAINING | Keep in archive but mark ineligible for training |
| INSUFFICIENT_EVIDENCE | Cannot determine from visual inspection alone |
| NEEDS_PHYSICAL_TEST | Defect type requires destructive verification |

**Notes field is mandatory for all decisions.** Engineering rationale must be documented.

---

## 4. E2 Annotation Contamination

### 4.1 Contamination Overview

| Level | Count | % |
|---|---|---|
| CLEAN | 125 | 13.5% |
| LOW | 386 | 41.6% |
| MEDIUM | 266 | 28.7% |
| HIGH | 150 | 16.2% |

**Training-safe (CLEAN + LOW): 511 / 927 (55.1%)**  
**Medium/High contaminated (not training-safe): 416 / 927 (44.9%)**

### 4.2 Contamination by Class

The highest contaminated class is `capak` (spatter/flash): annotation markup from quality review sessions (red/green/blue circles) overlaps the spatter region in many images, making the contaminating markup and the defect feature visually similar. This creates the highest false positive training risk.

See `E2_CONTAMINATION_INVENTORY.csv` for per-class breakdown.

### 4.3 Contamination Mechanism

Annotation markups (colored circles, bounding box outlines) were applied directly to the raw images during a human review session using an OpenCV-based annotation tool. The markup pixels are present in the raw PNG files in the V5 dataset directory. Clean originals from before the annotation session are not available separately.

**Action required:** The original un-annotated source images are still accessible via the ZIP archives (e.g., `Okpunta.zip`). For each MEDIUM/HIGH record, the clean source image should be located in its source archive by filename and used instead of the contaminated V5 copy.

---

## 5. E3 Leakage-Safe Split

See `E3_SPLIT_LEAKAGE_REPORT.md` for full analysis.

| Metric | Value |
|---|---|
| Records with SHA1 cross-split leakage | 106 |
| Distinct collision SHA1s | 53 |
| Conflicted records (E1-flagged) | 343 |
| Original test count | 204 |
| Excluded test records | 65 |
| Safe test candidate count | 139 |

**E3 gate: NOT CLEARED.** Weld_id metadata unavailable; near-duplicate clustering not performed; E1 unresolved.

---

## 6. E4 Ground Truth

### 6.1 Provenance Summary

| Provenance type | Count |
|---|---|
| SURFACE_OBSERVATION | 927 |
| DESTRUCTIVE_TEST | 0 |
| NDT (UT / radiographic) | 0 |

**0 nugget acceptance measurements exist in this dataset.**

### 6.2 Implications

Surface-observation labels indicate that a human reviewer visually inspected the weld and assigned a defect class. They do NOT:
- Confirm nugget diameter (requires cross-section measurement)
- Confirm weld strength (requires destructive peel/chisel test)
- Confirm absence of internal defects (porosity, incomplete fusion, hot crack)

The V5 dataset is therefore suitable ONLY for training a **surface visual classification model** — not a weld quality acceptance model that makes pass/fail decisions against structural requirements.

See `E4_GROUND_TRUTH_MATRIX.csv` for per-class assessment.

---

## 7. Defect Taxonomy

The taxonomy covers 18 defect classes:
- **13 V5 surface classes** — labeled in the external dataset
- **5 internal defect classes** — from welding literature; not in V5 dataset

Surface-classifier-applicable: 12 classes (generic_bad excluded; 5 internal excluded)

See `DEFECT_CLASS_READINESS.csv` for per-class training readiness.

**Key training restrictions:**
- `generic_bad` (399 samples): `surface_classifier_applicable=False` — conflates multiple specific defect types from generic NOK archives
- `kucuk_cekirdek` (27 samples): 4 train / 22 test — anomalous split; model cannot learn this class from V5 alone
- `cokertme` (4 samples): insufficient for any training
- 5 internal defect classes: require destructive sectioning or NDT; no surface classifier applicable

---

## 8. Temporal Data Readiness

See `TEMPORAL_REAL_DATA_READINESS.md` for full analysis.

| Item | Status |
|---|---|
| Real video file found | YES (1 file) |
| Real video readable by OpenCV | NO (FPS=-1) |
| Weld-cycle-linked frame annotations | NONE |
| CNN-GRU/LSTM training | TEMPORAL_NO_GO |

---

## 9. Dataset Readiness Decision

### 9.1 Model Family Verdicts

| Model family | Decision | Primary blockers |
|---|---|---|
| Binary surface classifier (OK vs NOK) | **NO_GO** | E1 unresolved (175 pending); eligible_train=191 < 200 minimum; E2 contamination |
| Multi-label visible defect classifier | **NO_GO** | E1 unresolved; most specific classes < 30 samples; generic_bad ambiguity |
| Nugget diameter predictor | **NO_GO** | 0 destructive tests; no nugget measurements in ground truth |
| CNN-GRU temporal event detector | **NO_GO** | No readable real video; no weld-cycle annotations; GRU baseline not published |
| CNN-LSTM internal quality predictor | **NO_GO** | No temporal data; no internal defect labels; GRU baseline prerequisite |

### 9.2 DatasetAudit Gate

`DatasetAudit.is_training_allowed()` returns `False`. Gate status: **DRAFT / BLOCKED**.

---

## 10. Required Actions Before TRAINING_GO

In priority order:

| Step | Action | Owner |
|---|---|---|
| E1.1 | Complete all 175 human review decisions in ConflictReviewPage | QUALITY_ENGINEER |
| E1.2 | For each BOTH pair: assign specific label AND split from E1_HUMAN_REVIEW_PRIORITY.csv priority 1–51 | QUALITY_ENGINEER |
| E2.1 | For each MEDIUM/HIGH record: locate clean source image in ZIP archive and replace contaminated copy | DATA_ENGINEER |
| E3.1 | After E1 resolution: regenerate safe-split manifest excluding EXCLUDE_BOTH / EXCLUDE_FROM_TRAINING | DATA_ENGINEER |
| E3.2 | Obtain weld_id metadata or perform perceptual hash clustering (pHash ≤ 8) | DATA_ENGINEER |
| E4.1 | Conduct destructive peel/chisel tests on a representative sample for nugget acceptance ground truth | QUALITY_ENGINEER |
| E4.2 | Record each destructive test result linked to weld_id, test method, reviewer, and date | QUALITY_ENGINEER |
| BINARY.1 | After E1-E4 completion: verify eligible_train ≥ 200 for binary classifier GO | ML_ENGINEER |
| BINARY.2 | Re-run DatasetAudit; verify is_training_allowed() == True before initiating training | ML_ENGINEER |
| TEMPORAL.1 | Decode real video; extract frame sequences; link to weld cycles with quality labels | ML_ENGINEER |

---

## 11. Test Results

| Test suite | Result |
|---|---|
| test_vision_p3h_remediation.py | 51 PASS / 2 SKIP |
| test_vision_p3i_conflict_review.py | 30 PASS / 2 SKIP |
| test_vision_p3c + p3d + p3e | 197 PASS / 0 FAIL |
| test_vision_data_real_01.py | See Step 9 (deliverables verification) |

---

## 12. Deliverables

| File | Description |
|---|---|
| `docs/vision_validation/VISION_DATA_REAL_01_REPORT.md` | This report |
| `docs/vision_validation/E1_HUMAN_REVIEW_PRIORITY.csv` | 175 conflict pairs prioritized for human review |
| `docs/vision_validation/E2_CONTAMINATION_INVENTORY.csv` | Per-class contamination breakdown |
| `docs/vision_validation/E3_SPLIT_LEAKAGE_REPORT.md` | Leakage analysis and safe-split candidate stats |
| `docs/vision_validation/E4_GROUND_TRUTH_MATRIX.csv` | Per-class ground truth provenance |
| `docs/vision_validation/DEFECT_CLASS_READINESS.csv` | All 18 defect classes — training readiness |
| `docs/vision_validation/TEMPORAL_REAL_DATA_READINESS.md` | Real video inventory and CNN-GRU requirements |
| `backend/tests/test_vision_data_real_01.py` | Automated qualification tests |
