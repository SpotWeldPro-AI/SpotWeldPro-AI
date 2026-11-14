# Phase 4 Model Readiness Assessment

**Date:** 2026-11-14  
**Branch:** main  
**HEAD:** (see git log)  
**Prepared by:** P3H Dataset Remediation Pass

---

## Overall Verdict: NO-GO for all model families

No model training is permitted.  
`DatasetAudit.is_training_allowed()` = **False** (status=DRAFT, no approved reviewer).

---

## 1. Binary Surface Classifier (OK vs NOK) — NO-GO

**Architecture:** CNN fine-tune  
**Purpose:** Predict visible surface quality from still images; does NOT assess nugget acceptance.

| Gate | Result | Detail |
|------|--------|--------|
| E1 — duplicates resolved | BLOCKED | 170 unique SHA1s with unresolved label conflicts; 53 with cross-split leakage |
| E2 — contamination | PENDING | 416/927 records MEDIUM/HIGH; clean originals not verified as available |
| E3 — leakage-safe splits | PENDING | 65 test records excluded after E1+E2 analysis; 139 test remain |
| E4 — ground truth | PENDING_REVIEW | All 927 labels are SURFACE_OBSERVATION; none confirmed from destructive testing |
| Eligible clean train samples | 191 | Below 200 minimum while E1 unresolved |
| Eligible test samples | 141 | Usable once E1 resolved |

**Path to GO (after E1–E4 remediation):**
- Resolve 170 conflicting SHA1s via human adjudication (E1_CONFLICT_REVIEW_QUEUE.csv)
- Confirm clean originals are available for 416 contaminated records or exclude them (E2)
- Rebuild splits after E1 resolution; verify weld_id grouping if available (E3)
- Obtain DatasetAudit APPROVED status with qualified reviewer sign-off (E4)
- With E1 resolved: estimated 350–450 eligible train, 141 eligible test → CONDITIONAL GO

**Mandatory caveat:** This model predicts visible surface appearance only.  
A visually acceptable weld may have an undersized or cracked nugget.  
The deployment specification must state: "This system DOES NOT perform nugget acceptance testing."

---

## 2. Multi-label Defect Detection (18 classes) — NO-GO

**Architecture:** CNN + multi-head classifier

| Blocker | Detail |
|---------|--------|
| E1 unresolved | 173 conflicting pairs pollute class examples |
| generic_bad ambiguity | 399 records (43%) labeled 'generic_bad' cannot be decomposed into specific classes without destructive-test confirmation |
| Insufficient per-class samples | Most specific classes have < 30 clean training examples (minimum 30/class required) |
| Label provenance | SURFACE_OBSERVATION does not confirm defect type for nugget-affecting defects (deformeli, kopuk, kucuk_cekirdek) |

**Specific per-class counts (clean train after E1 filter):**

| Label | Total in audit | Est. clean train |
|-------|---------------|-----------------|
| generic_bad | 399 | ~180 (but unlabelled at class level) |
| ok | 139 | ~95 |
| capak | 112 | ~55 |
| deformeli | 54 | ~20 |
| kopuk | 46 | ~18 |
| eksik | 32 | ~12 |
| kacik | 27 | ~10 |
| kucuk_cekirdek | 27 | ~10 |
| ust_uste | 27 | ~10 |
| kenar | 25 | ~9 |
| delik | 21 | ~8 |
| cift_sac | 14 | ~5 |
| cokertme | 4 | ~1 |

All specific defect classes fall below the 30-sample minimum.

---

## 3. Image Segmentation — NO-GO

**Architecture:** U-Net / Mask-RCNN

| Blocker | Detail |
|---------|--------|
| No masks exist | Dataset contains image-level labels only; no polygon or pixel-level mask annotations |
| Annotation effort required | Each defect instance needs individual polygon/mask annotation before segmentation training is possible |

---

## 4. CNN-GRU — NO-GO

**Architecture:** CNN feature extractor + GRU classifier

| Blocker | Detail |
|---------|--------|
| No temporal data | Dataset is a still-image archive; no video sequences or frame timestamps exist |
| Sequence requirements | CNN-GRU requires contiguous frame sequences from complete weld cycles |
| DatasetAudit gate | status=DRAFT; no approved reviewer |

---

## 5. CNN-LSTM — NO-GO

**Architecture:** CNN feature extractor + LSTM classifier

| Blocker | Detail |
|---------|--------|
| No temporal data | Same as CNN-GRU: still-image archive only |
| Ordering constraint | GRU baseline must be published and compared before LSTM training begins (per model_plan.py) |
| DatasetAudit gate | status=DRAFT; no approved reviewer |

---

## Summary Table

| Model | Verdict | Primary Blocker |
|-------|---------|----------------|
| Binary Surface Classifier | NO-GO | E1 unresolved (170 conflict SHA1s); < 200 eligible train |
| Multi-label Defect Detection | NO-GO | generic_bad ambiguity; < 30 samples per specific class |
| Image Segmentation | NO-GO | No pixel-level masks exist |
| CNN-GRU | NO-GO | No temporal sequences; DatasetAudit DRAFT |
| CNN-LSTM | NO-GO | No temporal sequences; GRU baseline not published |

---

## Minimum Requirements for Surface Classifier GO Decision

1. E1: Human adjudication of all 175 conflict-queue rows → resolve or exclude each SHA1
2. E2: Verify clean originals for ≥ 200 contamination-free train samples per class (OK + surface-defect)
3. E3: Rebuild splits after E1 resolution; add weld_id grouping if source archives can be traced
4. E4: DatasetAudit record with status=APPROVED, qualified reviewer signed, all blocking_issues cleared
5. Total eligible train ≥ 200 (OK + generic_bad combined); eligible test ≥ 40

Meeting these requirements permits CONDITIONAL GO for the surface classifier with the documented caveat that it does not assess nugget quality.
