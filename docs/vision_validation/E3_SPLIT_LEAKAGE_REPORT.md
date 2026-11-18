# E3 Leakage-Safe Split Report
# SpotWeldPro AI — VISION-DATA-REAL-01

**Date:** 2026-11-18  
**Task:** VISION-DATA-REAL-01 Step 4  
**Status:** CANDIDATE_MANIFESTS_ONLY — Not yet approved

---

## 1. Summary

| Metric | Value |
|---|---|
| Total annotated records | 927 |
| Records with cross-split SHA1 leakage | 106 |
| Records flagged as conflicted (E1 unresolved) | 343 |
| Original test records | 204 |
| Test records excluded (leaking or conflicted) | 65 |
| Safe test records (clean, no leakage) | 139 |
| Safe train records (clean, no leakage) | 322 |
| Distinct cross-split SHA1 collisions | 53 |
| Distinct conflicted SHA1 groups | 170 |

---

## 2. Leakage Definition

A record is flagged `is_leaking=True` when its SHA1 hash appears in more than one split (train, val, or test). The same image pixel content being present in both the training set and the evaluation set would cause the model to "see" its own test samples during training, inflating held-out accuracy metrics.

A record is flagged `is_conflicted=True` when its SHA1 belongs to a conflicted pair in the E1 review queue — meaning the same image hash is associated with two different labels, two different source archives, or both.

---

## 3. Grouping Limitation

**Weld-ID grouping is not available.** The `ANNOTATION_AUDIT.csv` does not contain a `weld_id`, `part_id`, `session_id`, or `production_batch` column. All split integrity checks are therefore based on **SHA1 hash identity** (exact pixel duplicates) and **source archive membership** as a coarse production-session proxy.

The recommended industry practice for resistance spot weld datasets is to group images by weld_id or production batch to prevent **near-duplicate leakage** (images of the same physical weld location captured in rapid succession). Without weld_id grouping, images of the same physical weld in different shots may cross splits undetected.

**Action required before E3 approval:** Contact the original data source (Makina Öğrenmesi / Otomotiv Punta) to obtain weld_id or production batch metadata for the V5 dataset. If metadata is unavailable, perceptual hash clustering (pHash distance ≤ 8) must be performed as a weld_id proxy before final E3 approval.

---

## 4. Split Integrity Results

### 4.1 Cross-Split SHA1 Collisions

53 unique SHA1 hashes appear in more than one split. These 53 hashes map to 106 records (each hash touches 2 records across two splits).

| Collision type | Pairs |
|---|---|
| train ↔ test | 2 (CROSS_SPLIT_LEAKAGE in E1 queue) |
| train ↔ val | Included in 106 leaking count |
| val ↔ test | Included in 106 leaking count |

**All 2 train↔test collision pairs are already in the E1 queue** (`conflict_type=CROSS_SPLIT_LEAKAGE`, both `PENDING_REVIEW`).

### 4.2 Source Archive as Grouping Proxy

Records from the same source archive are considered to come from the same production session. The source archives in the dataset are:

| Archive | Approximate role |
|---|---|
| Okpunta.zip | OK weld production shots |
| Puntanok.1.zip | Generic NOK archive 1 |
| Punta_hatalar 1.zip | Specific defect archive |

Cross-archive SHA1 matches indicate the same physical image was imported from two different source archives, often with different labels — these are the LABEL_CONFLICT and BOTH entries in the E1 queue.

### 4.3 Safe Split Counts (Candidate Only)

| Split | Original | Excluded | Safe (candidate) |
|---|---|---|---|
| train | 540 | 218 | 322 |
| val | 183 | — | — |
| test | 204 | 65 | 139 |

The 65 excluded test records break down as: records where `is_leaking=True OR is_conflicted=True` in the original test split.

**These are candidate safe splits only.** The E3 manifest at `docs/E3_LEAKAGE_SAFE_SPLITS.csv` must NOT be treated as approved until:
1. E1 human review is complete (all 175 decisions made)
2. Weld_id metadata is obtained and near-duplicate clustering is performed
3. The safe split re-verification is run after E1 resolutions are applied

---

## 5. Minimum Evaluation Set Adequacy

The 139 safe test records distribute across label classes as follows (approximate):

| Label | Total in test | Estimated safe |
|---|---|---|
| generic_bad | ~70 | ~40 |
| ok | ~30 | ~20 |
| capak | ~25 | ~15 |
| deformeli | ~3 | ~2 |
| Other classes | ~76 | ~62 |

For classes with fewer than 5 safe test records, per-class accuracy metrics will be statistically unreliable. These classes are: `cokertme`, `ust_uste`, `kucuk_cekirdek`, `delik`, `cift_sac`.

---

## 6. E3 Gate Status

| Requirement | Status |
|---|---|
| SHA1 exact-duplicate scan complete | PASS |
| Cross-split collision detection complete | PASS |
| E1 conflict exclusions applied to candidate manifest | PASS |
| Weld_id grouping available | FAIL — metadata not in V5 CSV |
| Near-duplicate perceptual hash clustering | NOT_PERFORMED |
| E1 human review complete | FAIL — 175/175 pending |
| Candidate manifest regenerated post-E1 resolution | NOT_STARTED |

**E3 Gate: NOT CLEARED**

The safe-split candidate manifest exists as a reference for the human reviewer. It MUST NOT be used as the approved train/test split for model training.

---

## 7. Next Steps

1. Complete all 175 E1 human review decisions via the ConflictReviewPage
2. After E1 resolution, regenerate the E3 manifest excluding images adjudicated as EXCLUDE_BOTH or EXCLUDE_FROM_TRAINING
3. Request weld_id metadata from the data source, or perform perceptual hash clustering (pHash ≤ 8) as a near-duplicate proxy
4. Apply weld_id-based grouping to the split regeneration
5. Re-verify: no test record's weld_id group should appear in the train split
6. Submit the final E3 manifest for Engineering Sign-Off before any model training begins
