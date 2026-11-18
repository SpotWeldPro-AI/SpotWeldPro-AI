# Temporal Real Data Readiness
# SpotWeldPro AI — VISION-DATA-REAL-01 Step 7

**Date:** 2026-11-18  
**Task:** VISION-DATA-REAL-01 Step 7  
**Status:** TEMPORAL_NO_GO

---

## 1. Summary

| Item | Value |
|---|---|
| Real video files found | 1 |
| Synthetic MP4 files | 10 |
| Video files readable by OpenCV | 1 (real ~30fps) / 10 (synthetic) |
| Weld-cycle-linked frame annotations | 0 |
| CNN-GRU/LSTM training readiness | NO_GO |

---

## 2. Real Video Inventory

### 2.1 Found

| File | Path | Size | Codec readable by OpenCV |
|---|---|---|---|
| Spot_Welding_Detection_6.7.2026.mp4 | D:\makina_ogrenmesi\Otomotiv_punta\Punta hatalari_OpenCV\ | Present on disk | YES — ~30fps (confirmed by test suite) |

**OpenCV confirms: ~30.0 fps.** The video is decodable by OpenCV via the system DirectShow/FFmpeg backend. The file was recorded on 2026-07-06 (from filename). Its frame count, resolution, and total duration are accessible via `cv2.VideoCapture`. The video is physically accessible and machine-readable. The remaining blockers for temporal training are **weld-cycle linkage, frame-level ground truth annotations, and minimum sequence count** — not video readability.

### 2.2 Synthetic MP4 Files (Excluded from Temporal Training)

Located at `backend/tests/synthetic_data/videos/`:

| File | Purpose |
|---|---|
| synth_normal_approach.mp4 | 120 frames, 30fps, normal weld |
| synth_stress_duration.mp4 | 900 frames, 30fps, stress test |
| synth_ok_approach.mp4 | OK weld simulation |
| synth_capak_weld.mp4 | Spatter defect simulation |
| synth_kopuk_weld.mp4 | Broken weld simulation |
| synth_eksik_weld.mp4 | Missing weld simulation |
| synth_deformeli_weld.mp4 | Deformed electrode simulation |
| synth_kacik_weld.mp4 | Misaligned weld simulation |
| synth_kenar_weld.mp4 | Edge weld simulation |
| synth_delik_weld.mp4 | Burn-through simulation |

Synthetic videos are created by OpenCV (solid-color frames + noise overlay) and do not represent real weld appearance. They are **excluded from temporal model training**.

---

## 3. Requirements for CNN-GRU / CNN-LSTM Training

A temporal model (CNN-GRU or CNN-LSTM) for weld quality prediction requires:

| Requirement | Current Status |
|---|---|
| Frame sequences from real welds | MISSING — video unreadable |
| Each sequence linked to a weld_id | MISSING — no weld_id metadata |
| Frame-level timestamps synchronized with weld cycle | MISSING |
| Quality labels per weld cycle (nugget acceptance or defect class) | MISSING — no ground truth |
| Minimum sequence length (e.g., 30 frames at 30fps = 1 weld cycle) | UNVERIFIABLE |
| Minimum labeled sequence count (typically ≥ 100 per class) | MISSING |
| Train/test split at the weld_id level (not frame level) | NOT_POSSIBLE without weld_id |

---

## 4. Separation of Real vs Synthetic Data

| Category | Count | Location | Use |
|---|---|---|---|
| Real video files | 1 | D:\makina_ogrenmesi\... | NOT READABLE — requires codec investigation |
| Synthetic MP4s | 10 | backend/tests/synthetic_data/videos/ | WebSocket pipeline testing only |
| Synthetic PNG frames | 12 | backend/tests/synthetic_data/images/ | Vision API acceptance testing |

The real video and all synthetic files are **physically separated** in different directories. The synthetic data directory contains a `MANIFEST.json` that explicitly labels all files as `source: "synthetic"`.

---

## 5. Prior Trained Models Found

The following models were found outside the SpotWeldPro AI repository at `D:\makina_ogrenmesi\Otomotiv_punta\`:

| Model file | Architecture | Notes |
|---|---|---|
| spot_weld_model_v5_final_fast.joblib | Traditional ML (Random Forest/SVM) | Pre-gate training without E1-E4 controls |
| Eski/spot_weld_model.joblib | Traditional ML | Earlier version, no controls |
| Eski/spot_weld_model_balanced.joblib | Traditional ML (class-weighted) | No controls |
| Eski/spot_weld_model_safe.joblib | Traditional ML | No controls |
| VGG16_model.h5 | Deep learning CNN | Pre-gate training |
| VGG19_model.h5 | Deep learning CNN | Pre-gate training |
| Xception_model.h5 | Deep learning CNN | Pre-gate training |
| InceptionResNetV2_model.h5 | Deep learning CNN | Pre-gate training |
| ResNet152_model.h5 | Deep learning CNN | Pre-gate training |

**These models were trained on the V5 dataset BEFORE E1-E4 quality controls were established.** Their performance metrics are therefore unreliable as production quality benchmarks because:

1. Training data included 416 contamination-annotated images (MEDIUM/HIGH)
2. 175 duplicate/conflict pairs (175 PENDING_REVIEW) were not resolved before training
3. Train/test split leakage was not verified (53 cross-split SHA1 collisions present)
4. Nugget acceptance labels were SURFACE_OBSERVATION only (not destructive test)

These pre-gate models must NOT be deployed for production weld quality acceptance decisions.

---

## 6. Temporal Data Readiness Decision

**TEMPORAL_NO_GO**

Blocking conditions (all must be resolved):

1. **Real video unreadable** — `Spot_Welding_Detection_6.7.2026.mp4` cannot be decoded. Install OpenCV with FFmpeg backend or convert with ffmpeg.exe first.
2. **No weld-cycle linkage** — The video file has no metadata linking frames to weld_id, cycle timestamp, or quality outcome.
3. **No frame ground truth** — No `VIDEO_FRAME_ANNOTATIONS.csv` or equivalent annotation file exists.
4. **Static image dataset E1-E4 incomplete** — The CNN-GRU baseline cannot be trained until the static-image dataset gates are resolved (prerequisite for temporal model development per Phase 4 roadmap).
5. **Minimum sequence count not met** — 1 real video file is insufficient for a temporal training dataset.

---

## 7. Required Actions to Reach TEMPORAL_GO

1. Install FFmpeg-enabled OpenCV or run `ffmpeg -i Spot_Welding_Detection_6.7.2026.mp4 -c:v libx264 out.mp4` to verify/convert the video
2. Confirm frame count, resolution, FPS, and duration
3. Annotate the video: segment into individual weld cycles; link each cycle to a weld_id
4. For each weld cycle: record quality outcome (acceptable/defective) with evidence (peel test or UT result)
5. Collect ≥ 100 weld cycle sequences per class (minimum; typically 300+ for reliable training)
6. Apply weld_id-based train/test split (never split by frame within a single weld cycle)
7. Obtain Engineering Sign-Off on the temporal ground truth before training begins
