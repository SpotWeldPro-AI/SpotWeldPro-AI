# Vision P3H — Dataset Remediation and Training Readiness Report

**Date:** 2026-11-14  
**Branch:** main  
**HEAD:** 066eec7 + P3H changes (see commit)  
**Status:** REMEDIATION_IN_PROGRESS — training NO-GO; human review required

---

## Executive Summary

P3H carried out a full dataset inventory, duplicate-conflict analysis, contamination audit,
leakage-safe split construction, and ground-truth provenance review against the two existing
manifests (`ANNOTATION_AUDIT.csv`, `DUPLICATE_MANIFEST.csv`).  No model training is permitted.
Four human-review deliverables have been generated.

---

## Phase A — Dataset Inventory

| Metric | Count |
|--------|-------|
| Total annotated records | 927 |
| Total duplicate pairs | 182 |
| Source archives | 5 |
| Unique defect labels | 13 |

### Label Distribution

| Label | Count | % |
|-------|-------|---|
| generic_bad | 399 | 43.0% |
| ok | 139 | 15.0% |
| capak | 112 | 12.1% |
| deformeli | 54 | 5.8% |
| kopuk | 46 | 5.0% |
| eksik | 32 | 3.5% |
| kacik | 27 | 2.9% |
| kucuk_cekirdek | 27 | 2.9% |
| ust_uste | 27 | 2.9% |
| kenar | 25 | 2.7% |
| delik | 21 | 2.3% |
| cift_sac | 14 | 1.5% |
| cokertme | 4 | 0.4% |

**Note:** `generic_bad` (43%) is an underspecified catch-all label.  It cannot be used
directly for multi-label defect detection without further human-confirmed decomposition.

### Split Distribution

| Split | Count |
|-------|-------|
| train | 540 |
| val | 183 |
| test | 204 |

### Contamination Distribution

| Level | Count | Training-safe? |
|-------|-------|---------------|
| CLEAN | 126 | Yes |
| LOW | 385 | Yes |
| MEDIUM | 267 | No |
| HIGH | 149 | No |
| **Training-safe total** | **511** | |
| **Unsafe total** | **416** | |

---

## Phase B — E1 Duplicate Conflicts (BLOCKED)

| Category | Pairs | Unique SHA1s |
|----------|-------|-------------|
| LABEL_CONFLICT (same split) | 122 | — |
| BOTH (leakage + conflict) | 51 | 51 |
| CROSS_SPLIT_LEAKAGE (same label) | 2 | 2 |
| SAME_LABEL_SAME_SPLIT (benign) | 7 | — |
| **Requiring human review** | **175** | **170** |
| Cross-split leakage SHA1s | — | **53** |

### Top Conflicting Label Pairs

| Label A | Label B | Pairs |
|---------|---------|-------|
| deformeli | generic_bad | 53 |
| capak | generic_bad | 52 |
| generic_bad | kacik | 28 |
| delik | generic_bad | 21 |
| cift_sac | generic_bad | 15 |
| cokertme | generic_bad | 4 |

**Root cause:** Source archives were labeled at different granularity.  Punta_hatalar
archives used `generic_bad` as a catch-all; Okpunta/Puntanok archives used specific
defect codes.  The same image received different labels depending on which archive
it was drawn from.

**Resolution required:** Each row in `E1_CONFLICT_REVIEW_QUEUE.csv` needs a human
reviewer to supply `review_decision` (KEEP_A / KEEP_B / EXCLUDE_BOTH) and
`review_notes`.  No automatic resolution is acceptable.  All 175 rows are currently
`PENDING_REVIEW`.

---

## Phase C — E2 Annotation Contamination (PENDING_REVIEW)

416/927 records (44.9%) have MEDIUM or HIGH annotation contamination (markup ratios > 1%).
These records contain visible annotation overlays (bounding boxes, labels painted onto the
image) that would leak annotation metadata into image features during training.

**Key finding:** The annotation audit CSV does not link each contaminated record to its
clean original.  The `source_archive` field names the ZIP the image came from, but does
not provide the original pre-annotation path.

**Clean-source manifest generated:** `E2_CLEAN_SOURCE_MANIFEST.csv` classifies all 927
records.  The `training_eligible` flag is False for MEDIUM/HIGH records and for records
involved in label conflicts.

| training_eligible=True (train split) | 191 |
| eval_eligible=True (test split) | 141 |

---

## Phase D — E3 Leakage-Safe Splits (PENDING_REVIEW)

Without `weld_id`, `part_id`, or `session_id` columns in the annotation audit, grouping
must use `source_archive` as the coarsest available proxy.

After applying leakage (53 SHA1s) and conflict (170 SHA1s) exclusions to the test split:

| Safe split | Count |
|-----------|-------|
| train | 540 |
| val | 183 |
| test (safe) | 139 |
| EXCLUDED | 65 |

**Limitation:** `source_archive` grouping does not prevent leakage at the weld-cycle level.
Records from the same weld in different archives can still appear across splits.  Full
leakage safety requires `weld_id` tracing from the archive metadata.

**Leakage-safe split manifest generated:** `E3_LEAKAGE_SAFE_SPLITS.csv`

---

## Phase E — E4 Ground Truth (PENDING_REVIEW)

No `label_provenance` column exists in the annotation audit.  All 927 records default to
`SURFACE_OBSERVATION` (visual inspection label).

| Provenance | Count | Acceptable for nugget training | Acceptable for surface classifier |
|-----------|-------|-------------------------------|----------------------------------|
| SURFACE_OBSERVATION (assumed) | 927 | No | Yes (conditional) |
| DESTRUCTIVE_TEST | 0 | Yes | Yes |
| ACCEPTED_REFERENCE | 0 | Yes | Yes |

**Consequence:** No record is currently acceptable for nugget-acceptance classification training.
Surface classifier training remains conditionally acceptable, subject to E1 and E3 resolution
and DatasetAudit APPROVED status.

**Ground truth review manifest generated:** `E4_GROUND_TRUTH_REVIEW.csv`

---

## Phase F — Model Readiness

| Model | Verdict | Primary Blocker |
|-------|---------|----------------|
| Binary Surface Classifier | NO-GO | E1 unresolved; eligible_train=191 (< 200 min) |
| Multi-label Defect Detection | NO-GO | generic_bad ambiguity; < 30 samples/class |
| Image Segmentation | NO-GO | No pixel masks |
| CNN-GRU | NO-GO | No temporal sequences |
| CNN-LSTM | NO-GO | No temporal sequences; GRU baseline not published |

See `PHASE4_MODEL_READINESS.md` for per-model detail.

---

## Per-Gate Status

| Gate | Status | Remaining work |
|------|--------|----------------|
| E1 — Duplicate conflicts | BLOCKED | 175-row human review queue; no auto-resolution |
| E2 — Annotation contamination | PENDING_REVIEW | Verify clean originals for 416 records |
| E3 — Leakage-safe splits | PENDING_REVIEW | Add weld_id; rebuild after E1 resolution |
| E4 — Ground truth | PENDING_REVIEW | Add provenance column; obtain destructive-test reports |
| DatasetAudit | BLOCKED | status=DRAFT; no reviewer; no approved record |
| Training | BLOCKED | Requires all E1–E4 + DatasetAudit APPROVED |

---

## Deliverables

| File | Description | Rows |
|------|-------------|------|
| `docs/E1_CONFLICT_REVIEW_QUEUE.csv` | 175 conflict pairs for human adjudication | 175 |
| `docs/E2_CLEAN_SOURCE_MANIFEST.csv` | All 927 records classified by training suitability | 927 |
| `docs/E3_LEAKAGE_SAFE_SPLITS.csv` | Safe split assignment per record | 927 |
| `docs/E4_GROUND_TRUTH_REVIEW.csv` | Provenance audit with verification status | 927 |
| `docs/vision_validation/PHASE4_MODEL_READINESS.md` | Per-model GO/NO-GO with blocking detail | — |

---

## Test Results

| Suite | Passed | Failed |
|-------|--------|--------|
| test_vision_p3h_remediation.py (new) | 44 | 0 |
| test_vision_p3c_dataset_quality.py | 66 | 0 |
| test_vision_p3d_taxonomy.py | 85 | 0 |
| test_vision_p3e_annotation.py | 50 | 0 |
| test_migrations.py | 17 | 0 |
| **Total** | **258** | **0** |

PostgreSQL migration 0020_annotation_tables: compatible (verified in P3G-R2, 066eec7).

---

## Final Decision: NO-GO for Model Training

`DatasetAudit.is_training_allowed()` = **False**

The gate is not bypassed.  Training may begin only when:
1. E1_CONFLICT_REVIEW_QUEUE.csv is fully adjudicated by a human reviewer
2. DatasetAudit record created with status=APPROVED, qualified engineer as reviewer
3. All blocking_issues cleared (split.grouping_keys set, label sources verified)

The surface binary classifier is the most viable near-term candidate; it can reach
CONDITIONAL GO once E1 is resolved and eligible training samples exceed 200.
