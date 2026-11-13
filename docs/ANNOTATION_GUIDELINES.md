# ANNOTATION GUIDELINES — Spot Weld Defect Classification
**Project:** SpotWeldPro AI · Vision P3D  
**Version:** P3D-1.0  
**Date:** 2026-11-13  
**Applies to:** V5 dataset remediation + future image collection

---

## 0. Before You Annotate

1. **Read the defect taxonomy** (`docs/DEFECT_TAXONOMY.md`) and the evidence matrix (`docs/EVIDENCE_MATRIX.md`) before annotating any image.
2. **Use ROI-cropped images** — never annotate full-part photos. Crop to the weld-centred region of interest (ROI) before annotating. Remove inspection annotation markup (red circles, green markers, blue arrows) from the ROI crop.
3. **Multi-label is allowed** — a single image may carry more than one defect label (e.g., spatter + small nugget indicator). Record all visible defects.
4. **Never assign a label you are not confident in** — use `review_flag=True` to escalate to a senior engineer.
5. **Do not label `generic_bad`** for new annotations — this class is deprecated as a training label (see §6).
6. **Do not use annotation marks as defect evidence** — colored circles or arrows drawn by a previous inspector are annotation artifacts, not weld features. If you cannot see the defect without the markup, do not label it.

---

## 1. Annotation Region Types

| Type | When to Use | Example |
|------|-------------|---------|
| `BBOX` | Defect has a localizable, roughly rectangular extent | Deformed indentation, misalignment |
| `POLYGON` | Defect has irregular shape (spatter, burn-through) | Spatter splash, burn-through hole |
| `POINT` | Location only; no spatial extent (missing weld) | Missing weld location |
| `WHOLE_IMAGE` | Defect is global or not localizable | Generic NOK, incomplete fusion (whole weld) |

---

## 2. Per-Defect Annotation Instructions

### 2.1 `ok` — Kabul / Accepted

- **Region type:** WHOLE_IMAGE
- **What to mark:** No bounding box or polygon required. Assign label `ok` to the full image.
- **What NOT to do:** Do not assign `ok` if any other defect is visible, even if minor.
- **Minimum quality threshold:** Circular, undamaged electrode indentation. No visible spatter, cracks, or surface discontinuities within ROI.
- **Caveat:** This label reflects **surface appearance only**. It does not confirm nugget diameter.

---

### 2.2 `capak` — Çapak / Spatter

- **Region type:** POLYGON
- **What to mark:** Draw a polygon enclosing all visible spatter droplets and the central weld impression. If spatter is scattered, include the entire affected area.
- **What NOT to do:** Do not include the inspector's markup circles as spatter.
- **Minimum requirement:** At least 3 clearly visible metallic droplets or a continuous spatter ring.
- **Co-occurrence:** May co-occur with `delik` (burn-through) or `expulsion`. Label both when both are present.

---

### 2.3 `deformeli` — Deformeli / Deformed

- **Region type:** BBOX
- **What to mark:** Draw a tight bounding box around the deformed electrode impression.
- **Positive criterion:** The indentation is clearly non-circular (elongated, partial, mushroomed, or pitted).
- **Negative criterion (do not label):** Slight ellipticity is not deformed — only clearly irregular shapes.

---

### 2.4 `kopuk` — Kopuk / Broken

- **Region type:** BBOX
- **What to mark:** Draw a bounding box around the visible fracture or separation zone.
- **Important:** Mark `review_flag=True` for all broken weld images — definitive confirmation requires a peel or chisel test. The annotation here is a visual indicator only.
- **Co-occurrence:** May co-occur with `eksik` if the broken weld is completely detached.

---

### 2.5 `eksik` — Eksik / Missing

- **Region type:** POINT
- **What to mark:** Place a single point marker at the expected weld location (use reference weld pattern or drawing if available).
- **Positive criterion:** No electrode indentation visible at the planned location; sheet surface undisturbed.

---

### 2.6 `kucuk_cekirdek` — Küçük Çekirdek Göstergesi / Small Nugget Indicator

- **Region type:** BBOX
- **What to mark:** Draw a bounding box around the indentation area.
- **⚠️ IMPORTANT:** This label is a **surface indicator only**. Write a note stating that cross-section confirmation is required.
- **Positive criterion:** Indentation diameter is visibly smaller than expected for the electrode size used.
- **Do NOT use** this label to infer nugget rejection — it must be correlated with cross-section or UT data.
- **Mark as:** Always set `requires_physical_confirmation=True` in the annotation record.

---

### 2.7 `kacik` — Kaçık / Misaligned

- **Region type:** BBOX
- **What to mark:** Draw a bounding box around the indentation. Include reference marks or weld symbols in the ROI if visible, so the offset can be measured.
- **Positive criterion:** Indentation centre is offset from the weld symbol or reference position by a visually clear margin (> 2 mm in ROI at scale).

---

### 2.8 `ust_uste` — Üst Üste / Overlapping

- **Region type:** BBOX
- **What to mark:** Draw a single bounding box that covers both overlapping weld impressions.
- **Positive criterion:** Two distinct electrode impressions are visible and they overlap or are separated by less than the nugget diameter.

---

### 2.9 `kenar` — Kenar / Edge Weld

- **Region type:** BBOX
- **What to mark:** Draw a bounding box around the indentation. Include the sheet edge in the bounding box so the proximity can be assessed.
- **Positive criterion:** The edge of the indentation is within the minimum edge distance (per OEM standard, typically 1.5× nugget diameter from sheet edge).

---

### 2.10 `delik` — Delik / Burn-Through

- **Region type:** POLYGON
- **What to mark:** Draw a polygon tightly around the hole or void, including any molten material residue at the perimeter.
- **Positive criterion:** A through-hole is visible — light passes through or a void is clearly present.
- **Co-occurrence:** Often co-occurs with `capak`.

---

### 2.11 `cift_sac` — Çift Sac / Double Sheet

- **Region type:** BBOX
- **What to mark:** Draw a bounding box around the area where the extra sheet layer is visible.
- **Important:** Mark `requires_physical_confirmation=True` — the extra layer may not be visible from above in all cases.

---

### 2.12 `cokertme` — Çökürtme / Crush Dent

- **Region type:** BBOX
- **What to mark:** Draw a tight bounding box around the dented region.
- **Positive criterion:** The indentation depth appears greater than nominal; sheet surface is visibly concave.

---

### 2.13 `generic_bad` — Genel Hatalı / Generic NOK

**⚠️ DEPRECATED FOR NEW ANNOTATIONS.**  
Do not use `generic_bad` as a primary label for new annotations. If you can identify the specific defect type, use that label instead.  

If you cannot identify the specific type:
- Assign the most specific label you are confident in
- Set `review_flag=True` for escalation
- If truly unidentifiable, label as `generic_bad` with a note explaining why

---

### 2.14 `expulsion` — Pıskırma / Expulsion

- **Region type:** POLYGON
- **What to mark:** Draw a polygon around the ejected metal traces, channels, or impact craters on the sheet surface.
- **Note:** No V5 training data exists for this class. All `expulsion` annotations will be used for initial dataset creation.
- **Distinguish from `capak`:** Expulsion involves larger quantities of ejected metal and typically leaves radial channels; spatter is smaller droplets.

---

### 2.15 Internal Defects (`incomplete_fusion`, `porosity`, `hot_crack`, `cold_lap`)

- **Do NOT label** these from surface images alone — they are not surface-detectable.
- These labels may only be assigned by a qualified metallurgical engineer after cross-section examination or NDT.
- Region type: WHOLE_IMAGE (whole weld; defect location within nugget is not visible from surface).
- Always include the cross-section report reference number in the annotation notes.

---

## 3. Quality Control Rules

| Rule | Requirement |
|------|-------------|
| Annotator qualification | Qualified weld inspector or engineer; completed P3D taxonomy training |
| Review for CRITICAL findings | All `kopuk`, `eksik`, `delik`, `incomplete_fusion`, `hot_crack` must be reviewed by a second qualified engineer |
| ROI cropping | Mandatory before annotation; annotation markup removed |
| Multi-label consistency | If co-occurrence codes are assigned, verify all visible defects are captured |
| `kucuk_cekirdek` escalation | Always flag for cross-section confirmation |
| Confidence threshold | Only label defects you are ≥80% confident in; use `review_flag=True` for 60–79% |
| Do not use this for nugget acceptance | These annotations support surface defect classification only |

---

## 4. File Naming and Metadata

Each annotated image must have an accompanying JSON metadata record with:

```json
{
  "image_path": "relative/path/to/roi_crop.png",
  "annotator_id": "ENGINEER_ID",
  "annotation_date": "YYYY-MM-DD",
  "image_type": "SURFACE",
  "is_roi_cropped": true,
  "annotation_markup_removed": true,
  "label_source": "SURFACE_OBSERVATION",
  "findings": [
    {
      "defect_code": "capak",
      "confidence": 0.9,
      "confidence_source": "HUMAN_ANNOTATION",
      "bbox_pixels": [x, y, w, h],
      "requires_physical_confirmation": false
    }
  ],
  "notes": []
}
```

For internal defect annotations (destructive test origin):
- Set `label_source` to `"DESTRUCTIVE_TEST"`
- Include cross-section report reference in `notes`

---

## 5. What DOES NOT Count as a Defect

| Item | Action |
|------|--------|
| Inspector circles or arrows from prior QC | Ignore; do not label; crop out of ROI |
| Sheet discolouration from normal heat-affected zone | Ignore unless accompanied by another defect |
| Slight ellipticity of indentation from normal electrode wear | Do not label as `deformeli` |
| Spatter below 2 mm diameter that is isolated | Do not label as `capak` unless multiple droplets visible |
| Normal surface oxidation tint | Ignore |

---

## 6. Training Eligibility Checklist

Before a record is submitted for dataset inclusion, confirm:

- [ ] ROI crop applied; annotation markup removed from weld region
- [ ] At least one specific defect label assigned (not `generic_bad` alone)
- [ ] Annotation region type matches taxonomy specification
- [ ] Multi-label cooccurrences checked
- [ ] `requires_physical_confirmation` set correctly for `kopuk`, `kucuk_cekirdek`, `cift_sac`
- [ ] Internal defect labels (`incomplete_fusion`, etc.) accompanied by cross-section report reference
- [ ] Record passed secondary review for CRITICAL findings
- [ ] DatasetAudit gates E1–E4 resolved before submitting for model training

**Training is blocked until `DatasetAudit.is_training_allowed() == True`.**
