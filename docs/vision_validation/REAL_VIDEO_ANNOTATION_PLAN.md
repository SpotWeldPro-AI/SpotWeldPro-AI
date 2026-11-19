# Real Video Annotation Plan

**Date:** 2026-11-19  
**Task:** VISION-DATA-REAL-02 — Step 5  
**File:** `Spot_Welding_Detection_6.7.2026.mp4`  
**Status:** READ-ONLY PREPARATION REPORT — No model trained, no annotations written

---

## Video Properties (Verified)

| Property | Value |
|----------|-------|
| Filename | Spot_Welding_Detection_6.7.2026.mp4 |
| Duration | 142.77 seconds |
| FPS | 30.007 |
| Total frames | 4,284 |
| Resolution | 1244 × 684 pixels |
| Codec | H.264 |
| Decodable | Yes (OpenCV 4.x, 3/3 test frames) |
| File accessible | Yes (D:\...\Punta hatalari_OpenCV\) |

---

## Weld-Cycle Segmentation Requirements

### What Must Be Identified

Each weld event in the video corresponds to one complete weld cycle:

1. **Electrode approach** — electrode moves toward sheet surface
2. **Contact** — electrode contacts sheet, pre-squeeze pressure applied
3. **Weld current active** — current flows, nugget forms (not visible from surface)
4. **Hold** — electrode holds while nugget solidifies
5. **Electrode release** — electrode lifts, weld mark visible
6. **Post-weld frame** — steady-state indentation visible for annotation

The annotation target is the **post-weld frame** — the first stable frame after electrode release showing the full indentation.

### Timing Estimates

At 30 fps, typical spot welding cycles:
- Fast cycle (automotive): 200–600 ms → 6–18 frames
- Slow cycle (heavy gauge): 600–1200 ms → 18–36 frames
- Total at 142.77 s: estimate 15–50 weld cycles depending on content

**Manual review required to count actual cycles.** Automatic cycle detection from surface motion alone is not reliable for defect labelling.

---

## Annotation Requirements

### Frame Selection

For each weld cycle:
1. Identify the post-weld frame (electrode fully released, indentation visible)
2. Record timestamp (frame number and seconds)
3. Assign a candidate weld ID (sequential, not from production system unless linked)
4. Apply one defect label from the V5 taxonomy
5. Mark evidence type as SURFACE_OBSERVATION

### Required Metadata Per Frame

| Field | Description | Example |
|-------|-------------|---------|
| frame_number | 0-indexed frame number | 1047 |
| timestamp_s | Time in seconds | 34.90 |
| weld_cycle_id | Sequential ID in this video | WC-001 |
| label | Defect code from V5 taxonomy | capak |
| label_provenance | Always SURFACE_OBSERVATION for video | SURFACE_OBSERVATION |
| annotator_id | Email of the human annotator | qe@company.com |
| review_status | DRAFT initially | DRAFT |
| notes | Visible evidence for label choice | Spatter droplets at 3 and 7 o'clock |

### Labels That Cannot Be Assigned from Video Alone

The following labels require physical confirmation and **must not be assigned** solely from video:

| Code | Reason |
|------|--------|
| kucuk_cekirdek | Small indentation ≠ small nugget — cannot confirm nugget size |
| kopuk | Cannot confirm fracture depth from surface motion |
| cift_sac | Cannot confirm sheet stack thickness from video |

Assign NEEDS_PHYSICAL_TEST flag when these are suspected.

---

## Segmentation Approach

### Manual Method (Recommended for First Annotation)

1. Open video in a media player or OpenCV script
2. Advance frame by frame during weld events
3. Record frame number at electrode-release moment
4. Export that frame as PNG for annotation tool
5. Apply label in ConflictReviewPage or AnnotationPage

### Semi-Automatic Approach (Future Work)

Electrode motion can be detected using frame-differencing (absolute difference of consecutive frames). Candidate weld regions show high pixel variance during current-active phase followed by sudden stabilization. This provides timestamp candidates, but defect labelling still requires human review.

**No temporal model must be trained on V5 video footage until E1–E4 gates are clear.**

---

## Output Format

Each annotated frame should produce one record in `weld_annotations`:

```json
{
  "image_path": "<export_dir>/frame_NNNN.png",
  "split": "video_frames",
  "label_provenance": "SURFACE_OBSERVATION",
  "contamination_level": "UNKNOWN",
  "weld_id": "WC-NNN-<frame>",
  "annotator_id": "qe@company.com",
  "review_status": "DRAFT"
}
```

Findings are added separately via `POST /api/v1/annotation/{id}/finding`.

---

## Training Readiness

| Condition | Status |
|-----------|--------|
| Video decodable | Yes |
| Weld-cycle timestamps identified | Not yet — manual work required |
| Frame extraction script | Not created (out of scope for REAL-02) |
| Any video frames annotated | 0 |
| Video-frame training gate | NOT CLEAR |

**No temporal model (CNN-GRU, LSTM, or similar) will be trained on this footage until:**
1. E1 gate is clear (175 conflict pairs resolved)
2. At least 50 weld cycles are manually annotated and reviewed
3. E4 gate has at least VERIFIED evidence for the target defect classes
4. A separate video dataset qualification report (VISION-DATA-REAL-03 or equivalent) is completed

---

## Limitations

- Video contains no production weld IDs — cannot cross-reference with ANNOTATION_AUDIT.csv
- Surface-only view: nugget formation, penetration depth, and internal defects are not observable
- Annotation must not rely on generic_bad — each cycle must receive a specific defect code or be excluded
- Video codec is H.264 / AVC; no raw/lossless alternative available — compression artifacts are present
  at high-motion frames during electrode approach and release

---

## References

- `VISION_DATA_REAL_01_REPORT.md` — real video discovery and initial readiness assessment
- `VISION_DATA_REAL_02_REPORT.md` — Step 5 video verification summary
- `E4_EVIDENCE_READINESS.md` — physical test requirements before video-frame training
- `E1_REVIEW_PROGRESS.md` — E1 gate status (must be clear before training)
