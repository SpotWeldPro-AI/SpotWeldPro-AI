# DATASET CLEANING REPORT
**Project:** SpotWeldPro AI — Vision P3C  
**Date:** 2026-11-13  
**Dataset:** V5 Surface Inspection Dataset  
**Label provenance:** `SURFACE_OBSERVATION` — visual inspection records only. No metallographic cross-section ground truth exists for any image in this dataset.  

---

## 1. Summary

| Metric | Value |
|--------|-------|
| Total images | 927 |
| Total duplicate pairs (same SHA1) | 182 |
| Cross-split leakage pairs (test↔train/val) | 53 |
| Label-conflict pairs (same SHA1, different label) | 173 |
| BOTH (cross-split + label conflict) | 51 |
| Same-label same-split (benign duplicates) | 7 |
| Clean images (no annotation markup) | 126 |
| LOW contamination (max markup ≤ 1%) | 385 |
| MEDIUM contamination (max markup 1–5%) | 267 |
| HIGH contamination (max markup > 5%) | 149 |
| Total contaminated | 801 |
| Test images with SHA1 in train/val (leaked) | 53 |
| Leakage-free test images | 151 |

## 2. Cross-split leakage details

**53 test images** have at least one SHA1-identical copy in the train or val split. This means the classifier may have been evaluated on images it effectively saw during training.

| Label | Total test | Leaked | Leakage-free |
|-------|-----------|--------|-------------|
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

## 3. Label conflicts

**173 pairs** share identical SHA1 hashes but carry different class labels. These arise because the same physical image was included in multiple source archives under different defect categories.

| SHA1 | Label A | Label B | Split A | Split B | Conflict |
|------|---------|---------|---------|---------|----------|
| ccc5195a65e8617c | cift_sac | generic_bad | train | val | LABEL_CONFLICT |
| ccc5195a65e8617c | cift_sac | generic_bad | train | val | LABEL_CONFLICT |
| 33e4159239987582 | cift_sac | generic_bad | train | train | LABEL_CONFLICT |
| 97d769ff842db369 | cift_sac | generic_bad | train | test | BOTH |
| 11e484f1b34a7395 | cift_sac | generic_bad | train | train | LABEL_CONFLICT |
| bf04a83b772fee67 | cift_sac | generic_bad | train | train | LABEL_CONFLICT |
| 982caa52f17e7790 | cift_sac | generic_bad | test | train | BOTH |
| 2423a01c5fca08c7 | cift_sac | generic_bad | test | val | BOTH |
| 68b7cbe84cfd99af | cift_sac | generic_bad | test | test | LABEL_CONFLICT |
| 6d076d045ae4f0dd | cift_sac | generic_bad | train | train | LABEL_CONFLICT |
| 66de6b7feafff7f2 | cift_sac | generic_bad | train | test | BOTH |
| ef0d73d678c6539f | cift_sac | generic_bad | train | train | LABEL_CONFLICT |
| 5c5e3d64ee724254 | cift_sac | generic_bad | train | test | BOTH |
| 4c42a44535ba1ab6 | capak | generic_bad | test | train | BOTH |
| a802848592be93cc | cift_sac | generic_bad | train | val | LABEL_CONFLICT |
| af47c2fa92697b6b | cift_sac | generic_bad | val | val | LABEL_CONFLICT |
| c10abc8676183384 | capak | generic_bad | train | train | LABEL_CONFLICT |
| b205e00e97c9ce6b | capak | generic_bad | train | train | LABEL_CONFLICT |
| 4bcdf917a4fe16a2 | capak | generic_bad | val | test | BOTH |
| 0da435fd1a76a780 | capak | generic_bad | train | test | BOTH |
| 0f5c53178ab18447 | capak | generic_bad | val | train | LABEL_CONFLICT |
| 41ced4ca4f439c90 | capak | generic_bad | train | train | LABEL_CONFLICT |
| c4dac90b4d61c3ce | capak | generic_bad | train | test | BOTH |
| 6d9aa44d7d28ae44 | capak | generic_bad | train | train | LABEL_CONFLICT |
| e6a3745f651672aa | capak | generic_bad | train | train | LABEL_CONFLICT |
| 6cc4eaee45f13283 | capak | generic_bad | train | train | LABEL_CONFLICT |
| ea522ce12791bfa9 | capak | generic_bad | train | train | LABEL_CONFLICT |
| 5732a1426c6cfef8 | capak | generic_bad | train | val | LABEL_CONFLICT |
| 6618e4e454a33b95 | capak | generic_bad | train | val | LABEL_CONFLICT |
| 8166ed329b2ce1c5 | capak | generic_bad | train | test | BOTH |
| … | … | … | … | … | 143 more rows in DUPLICATE_MANIFEST.csv |

## 4. Annotation contamination by label

| Label | Total | CLEAN | LOW | MEDIUM | HIGH |
|-------|-------|-------|-----|--------|------|
| capak | 112 | 10 | 31 | 51 | 20 |
| cift_sac | 14 | 0 | 3 | 4 | 7 |
| cokertme | 4 | 0 | 2 | 2 | 0 |
| deformeli | 54 | 13 | 31 | 7 | 3 |
| delik | 21 | 0 | 7 | 9 | 5 |
| eksik | 32 | 0 | 5 | 11 | 16 |
| generic_bad | 399 | 47 | 208 | 94 | 50 |
| kacik | 27 | 2 | 4 | 12 | 9 |
| kenar | 25 | 1 | 5 | 15 | 4 |
| kopuk | 46 | 3 | 6 | 26 | 11 |
| kucuk_cekirdek | 27 | 16 | 10 | 1 | 0 |
| ok | 139 | 30 | 55 | 31 | 23 |
| ust_uste | 27 | 4 | 18 | 4 | 1 |

**Contamination levels:**  
- `CLEAN`: all markup ratios = 0.0  
- `LOW`: max markup ratio ≤ 0.01  
- `MEDIUM`: max markup ratio 0.01–0.05  
- `HIGH`: max markup ratio > 0.05  

Images with HIGH or MEDIUM contamination may cause the classifier to learn annotation styles (inspector circles, arrows, text) rather than weld features.

## 5. Source archive provenance

| Archive | Images | Labels |
|---------|--------|--------|
| Punta_hatalar 1.zip | 285 | capak, cift_sac, cokertme, deformeli, delik, eksik, kacik, kenar, kopuk, kucuk_cekirdek, ust_uste |
| Puntanok_2.zip | 200 | generic_bad |
| Puntanok.1.zip | 199 | generic_bad |
| Okpunta.zip | 139 | ok |
| Punta_hataları_2.zip | 104 | capak, deformeli, kucuk_cekirdek, ust_uste |

**Key observation:** `Puntanok_1.zip` and `Puntanok_2.zip` provide generic NOK images without specific defect labels. `Punta_hatalar 1.zip` and `Punta_hataları_2.zip` contain the same images re-labeled with specific defect types — this is the root cause of the 355 duplicate pairs.

## 6. Recommended remediation steps

1. **Resolve label conflicts** (Priority: CRITICAL): For each SHA1 appearing in both a specific-defect class and `generic_bad`, keep the specific-defect label. Remove the `generic_bad` copy. This affects 173 pairs.

2. **Eliminate cross-split leakage** (Priority: CRITICAL): After step 1, regenerate train/val/test splits by grouping on `serial_id` (extracted from `group_id`). Never let images from the same physical weld span splits. Currently 53 test images are leaked.

3. **Handle annotation-contaminated images** (Priority: HIGH):  
   - 149 HIGH-contamination images: exclude from training unless ROI crop removes the annotation area.  
   - 267 MEDIUM-contamination images: flag for manual review; use ROI crop if available.  
   - 385 LOW-contamination images: acceptable risk; include in training.  

4. **Apply ROI crops** (Priority: HIGH): ROI coordinates exist in `roi_candidates.csv`. Use `candidate_crop_path` for training instead of full-part photos.

5. **Document label provenance** (Priority: MEDIUM): Record camera setup, lighting conditions, operator, date range, and production batch for each source archive.

6. **Install psutil and scikit-learn** (Priority: LOW): Required for backend integration and model deployment gates.

7. **DO NOT use this dataset for nugget acceptance classification** until cross-section metallographic ground truth is obtained. All labels are `SURFACE_OBSERVATION` only.

