# LEAKAGE-SAFE SPLIT REPORT
**Project:** SpotWeldPro AI — Vision P3C  
**Date:** 2026-11-13  

---

## 1. Leakage-safe test set definition

A test image is **leakage-safe** if and only if its SHA1 hash does not appear in any train or val image. Images sharing a SHA1 with a train/val image are **excluded** from evaluation — their decision from `v5_holdout_decisions.csv` cannot be treated as an independent measurement.

- Original test set: **204** images  
- Leaked (SHA1 in train/val): **53** images excluded  
- **Leakage-safe test set: 151 images**  

## 2. Test set size by label

| Label | Original test | Leaked | Leakage-safe |
|-------|--------------|--------|-------------|
| capak | 35 | 6 | 29 |
| cift_sac | 3 | 2 | 1 |
| deformeli | 3 | 3 | 0 |
| delik | 3 | 2 | 1 |
| eksik | 6 | 1 | 5 |
| generic_bad | 80 | 32 | 48 |
| kacik | 8 | 6 | 2 |
| kenar | 5 | 0 | 5 |
| kopuk | 8 | 0 | 8 |
| kucuk_cekirdek | 22 | 0 | 22 |
| ok | 28 | 1 | 27 |
| ust_uste | 3 | 0 | 3 |

## 3. Group-level leakage analysis

- Total unique group_ids in test set: 141  
- Groups **fully** in test (no copies in train/val): 141  
- Groups **partially** leaked (also appear in train or val): 0  

## 4. Recommended new split strategy

**Current problem:** Split was generated per-image without grouping. Images from the same physical weld (same `serial_id` / `group_id`) can appear in both train and test, creating leakage.

**Recommended approach:**

1. **Resolve label conflicts first** (see DATASET_CLEANING_REPORT.md §6).  
2. Extract `serial_id` from each `group_id` (the value is already the canonical identifier).  
3. For images without a serial (generic NOK archives: `puntanok_1_zip__*`, `puntanok_2_zip__*`), treat each file as its own independent group.  
4. Apply **stratified group split**: shuffle `serial_id` groups by label, then assign 70% to train, 15% to val, 15% to test. All images from one serial go to one split.  
5. Verify: `assert len(set(train_serials) & set(test_serials)) == 0`  
6. After splitting, verify SHA1 uniqueness across splits: `assert len(train_sha1s & test_sha1s) == 0`  

**Minimum viable leakage-free test set after remediation:** Depends on deduplication outcome. With current data, the leakage-free test set contains **151** images and covers all 13 classes.

