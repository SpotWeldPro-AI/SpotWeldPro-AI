# DEFECT TAXONOMY — Spot Weld Quality Classification
**Project:** SpotWeldPro AI · Vision P3D  
**Version:** P3D-1.0  
**Date:** 2026-11-13  
**Languages:** Turkish (TR) / English (EN)  
**Reference standard:** ISO 15614-12, AWS D8.1M, OEM RSW acceptance criteria

---

## Overview

This taxonomy covers all 18 defect classes used in SpotWeldPro AI.  
13 classes come from the external V5 surface inspection dataset (surface-visible defects).  
5 additional classes from resistance spot welding literature require cross-section or NDT for detection.

**Multi-label:** A single weld may exhibit more than one defect simultaneously.  
**Observability levels:**

| Level | Description |
|-------|-------------|
| `SURFACE_VISIBLE` | Reliably detectable from a surface image; classifier can be trained |
| `SURFACE_INDICATOR` | Surface signs present but insufficient for final pass/fail without internal confirmation |
| `NDT_REQUIRED` | Requires ultrasonic, radiographic, or other NDT; no surface indicator |
| `DESTRUCTIVE_ONLY` | Only visible after metallographic cross-section |

---

## Taxonomy Table

### Accept Class

| Code | Turkish | English | Observability | Severity | In V5 | Surface Classifier |
|------|---------|---------|---------------|----------|-------|--------------------|
| `ok` | Kabul | Accepted | SURFACE_VISIBLE | ACCEPT | ✅ | ✅ |

**Notes:** SURFACE_OBSERVATION labels only — does not confirm nugget diameter. A visually OK weld may still have an undersized nugget; metallographic cross-section or UT is required for nugget acceptance.

---

### Surface-Visible Defects (V5 Dataset Classes)

#### `capak` — Çapak / Spatter-Flash

| Field | Value |
|-------|-------|
| **Turkish** | Çapak / Kaynak Sıçraması |
| **English** | Spatter / Flash |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | MEDIUM |
| **Annotation** | POLYGON |
| **In V5** | ✅ (112 samples) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Visual indicators:**
- Bright metallic droplets scattered around the weld point
- Ring of solidified spatter at varying radii from weld centre
- May include discolouration from heat

**Notes:** Spatter presence does not confirm nugget quality. 71% of V5 spatter images have MEDIUM or HIGH annotation contamination; ROI crop strongly recommended.

---

#### `deformeli` — Deformeli Elektrod İzi / Deformed Electrode Impression

| Field | Value |
|-------|-------|
| **Turkish** | Deformeli Elektrod İzi |
| **English** | Deformed Electrode Impression |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | HIGH |
| **Annotation** | BBOX |
| **In V5** | ✅ (54 samples; 50 train / 1 val / 3 test) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Visual indicators:**
- Non-circular or asymmetric indentation on sheet surface
- Partial or double impression
- May show electrode face pitting or mushrooming pattern

**Notes:** Severe class imbalance in V5 (50 train, 3 test). Indicates electrode replacement is overdue.

---

#### `kopuk` — Kopuk Kaynak / Broken Weld

| Field | Value |
|-------|-------|
| **Turkish** | Kopuk Kaynak |
| **English** | Broken / Severed Weld |
| **Observability** | SURFACE_INDICATOR |
| **Severity** | CRITICAL |
| **Annotation** | BBOX |
| **In V5** | ✅ (46 samples) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | Yes |

**Visual indicators:**
- Visible fracture line or crack at the weld periphery
- Sheet separation visible under light loading
- Distorted or absent electrode indentation

**Notes:** Surface appearance alone may not distinguish partial break from full break; peel or chisel test required for definitive confirmation. Automatic reject in all automotive OEM standards.

---

#### `eksik` — Eksik Kaynak / Missing Weld

| Field | Value |
|-------|-------|
| **Turkish** | Eksik Kaynak |
| **English** | Missing Weld |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | CRITICAL |
| **Annotation** | POINT |
| **In V5** | ✅ (32 samples) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Visual indicators:**
- No electrode indentation visible at expected weld location
- Sheet surface undisturbed; no heat-affected zone
- Adjacent welds present but this location skipped

**Notes:** High confidence surface detection; absence of indentation is unambiguous.

---

#### `kucuk_cekirdek` — Küçük Çekirdek Göstergesi / Small Nugget Indicator

| Field | Value |
|-------|-------|
| **Turkish** | Küçük Çekirdek Göstergesi |
| **English** | Small Nugget Indicator (Surface) |
| **Observability** | SURFACE_INDICATOR |
| **Severity** | HIGH |
| **Annotation** | BBOX |
| **In V5** | ✅ (27 samples; 4 train / 1 val / 22 test — anomalous) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | Yes |

**Visual indicators:**
- Indentation diameter visibly smaller than the electrode face diameter
- Shallow, faint, or barely visible impression
- Unusually small heat-affected zone

**⚠️ CRITICAL CAUTION:** This is a surface *indicator* only. A small surface impression does NOT confirm nugget undersizing. For nugget diameter acceptance, destructive testing (cross-section + caliper measurement) or UT is required. The V5 split is anomalous (4 train / 22 test); this class cannot be reliably learned from V5 alone.

---

#### `kacik` — Kaçık Kaynak / Misaligned Weld

| Field | Value |
|-------|-------|
| **Turkish** | Kaçık Kaynak / Hizalama Hatası |
| **English** | Misaligned Weld |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | HIGH |
| **Annotation** | BBOX |
| **In V5** | ✅ (27 samples) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Visual indicators:**
- Electrode indentation visibly offset from weld symbol or reference mark
- Indentation partially on sheet edge or flange boundary
- Weld sequence spacing inconsistent with adjacent points

---

#### `ust_uste` — Üst Üste Kaynak / Overlapping Weld

| Field | Value |
|-------|-------|
| **Turkish** | Üst Üste Kaynak |
| **English** | Overlapping Weld |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | MEDIUM |
| **Annotation** | BBOX |
| **In V5** | ✅ (27 samples; 2 train / 22 val / 3 test — anomalous) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Notes:** Severely imbalanced split (2 train / 22 val); insufficient for classifier training.

---

#### `kenar` — Kenar Kaynağı / Edge Weld

| Field | Value |
|-------|-------|
| **Turkish** | Kenar Kaynağı |
| **English** | Edge Weld |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | HIGH |
| **Annotation** | BBOX |
| **In V5** | ✅ (25 samples) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Visual indicators:**
- Electrode indentation within minimum edge distance
- Partial nugget impression — one side truncated by sheet edge
- Visible sheet deformation or tear at edge

---

#### `delik` — Delik / Burn-Through

| Field | Value |
|-------|-------|
| **Turkish** | Delik / Yanma Deliği |
| **English** | Burn-Through / Hole |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | CRITICAL |
| **Annotation** | POLYGON |
| **In V5** | ✅ (21 samples) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Visual indicators:**
- Visible hole or void at weld centre
- Molten material residue around hole perimeter
- Severe discolouration and surface oxidation
- May coexist with heavy spatter

**Notes:** Automatic reject in all automotive OEM standards.

---

#### `cift_sac` — Çift Sac / Double Sheet

| Field | Value |
|-------|-------|
| **Turkish** | Çift Sac / Fazladan Tabaka |
| **English** | Double Sheet / Extra Layer |
| **Observability** | SURFACE_INDICATOR |
| **Severity** | HIGH |
| **Annotation** | BBOX |
| **In V5** | ✅ (14 samples) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | Yes |

**Notes:** Extra layer may not always be visible from above; surface indicator only.

---

#### `cokertme` — Çökürtme / Crush Dent

| Field | Value |
|-------|-------|
| **Turkish** | Çökürtme / Ezilme |
| **English** | Crush Dent |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | MEDIUM |
| **Annotation** | BBOX |
| **In V5** | ✅ (4 samples; 4 train / 0 test — insufficient) |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Notes:** Only 4 samples in V5, all in train; classifier training not feasible.

---

#### `generic_bad` — Genel Hatalı / Generic NOK

| Field | Value |
|-------|-------|
| **Turkish** | Genel Hatalı (Tanımsız Hata) |
| **English** | Generic NOK (Unspecified Defect) |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | HIGH |
| **Annotation** | WHOLE_IMAGE |
| **In V5** | ✅ (399 samples) |
| **Surface Classifier** | ❌ |
| **Cross-section required** | No |

**⚠️ TRAINING RESTRICTION:** `surface_classifier_applicable = False`. This label conflates multiple specific defect types from generic NOK archives (Puntanok_1/2.zip). Using it for classifier training would dilute class-specific features. **Preferred remediation:** replace each `generic_bad` duplicate with its specific label from Punta_hatalar archives (173 label-conflict pairs resolved in P3C).

---

### Internal / NDT Defects (Literature, Not in V5)

These defects are **not in the V5 dataset** and cannot be detected by surface image classification. They require cross-section metallography or NDT (ultrasonic, radiographic).

#### `incomplete_fusion` — Yetersiz Kaynak Nüfuziyeti / Incomplete Fusion

| Field | Value |
|-------|-------|
| **Turkish** | Yetersiz Kaynak Nüfuziyeti |
| **English** | Incomplete Fusion / Cold Weld |
| **Observability** | DESTRUCTIVE_ONLY |
| **Severity** | CRITICAL |
| **In V5** | ❌ |
| **Surface Classifier** | ❌ |
| **Cross-section required** | Yes |
| **NDT required** | Yes |

**⚠️ Most dangerous defect in RSW.** Surface appearance is completely normal. Only visible on metallographic cross-section or by UT. This is why SURFACE_OBSERVATION labels are **insufficient for nugget acceptance** in automotive safety applications.

---

#### `porosity` — Gözenek / Porosity

| Field | Value |
|-------|-------|
| **Turkish** | Gözenek / İçsel Boşluklar |
| **English** | Porosity / Internal Voids |
| **Observability** | NDT_REQUIRED |
| **Severity** | HIGH |
| **In V5** | ❌ |
| **Surface Classifier** | ❌ |
| **Cross-section required** | Yes |
| **NDT required** | Yes |

---

#### `hot_crack` — Sıcak Çatlak / Hot Crack

| Field | Value |
|-------|-------|
| **Turkish** | Sıcak Çatlak |
| **English** | Hot Crack / Solidification Crack |
| **Observability** | DESTRUCTIVE_ONLY |
| **Severity** | CRITICAL |
| **In V5** | ❌ |
| **Surface Classifier** | ❌ |
| **Cross-section required** | Yes |
| **NDT required** | Yes |

**Notes:** Common in high-carbon or galvanized steel. Radial cracks propagating from nugget centre.

---

#### `expulsion` — Pıskırma / Expulsion

| Field | Value |
|-------|-------|
| **Turkish** | Pıskırma / Eriyik Metal Fırlaması |
| **English** | Expulsion / Molten Metal Ejection |
| **Observability** | SURFACE_VISIBLE |
| **Severity** | HIGH |
| **In V5** | ❌ |
| **Surface Classifier** | ✅ |
| **Cross-section required** | No |

**Notes:** Surface-visible but no labeled training data available. Visually similar to spatter but typically more severe. Cross-section recommended to confirm residual nugget diameter.

---

#### `cold_lap` — Soğuk Bindirme / Cold Lap

| Field | Value |
|-------|-------|
| **Turkish** | Soğuk Bindirme |
| **English** | Cold Lap / Lack of Bonding |
| **Observability** | DESTRUCTIVE_ONLY |
| **Severity** | HIGH |
| **In V5** | ❌ |
| **Surface Classifier** | ❌ |
| **Cross-section required** | Yes |
| **NDT required** | Yes |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Total classes | 18 |
| V5 dataset classes | 13 |
| Internal / NDT only classes | 4 |
| Surface-visible (SURFACE_VISIBLE) | 11 |
| Surface indicator (SURFACE_INDICATOR) | 4 |
| NDT required | 1 |
| Destructive only | 4 (incl. incomplete_fusion, hot_crack, cold_lap) |
| Surface classifier applicable | 13 |
| Requires cross-section | 7 |
| CRITICAL severity | 5 |
| Accept (OK) | 1 |

## Fundamental Limitation

**All V5 labels are `SURFACE_OBSERVATION`** — visual inspection records from production quality stamps and serial tags. No metallographic cross-section evidence exists for any image. A surface image classifier trained on V5 data:

- **Can** detect: surface-visible deformation, spatter, missing welds, burn-through, misalignment
- **Cannot** detect: incomplete fusion, porosity, hot cracking, cold lap, actual nugget diameter
- **Must NOT** be used as a nugget acceptance gate without additional metallographic validation

This taxonomy is encoded in `backend/app/vision/defect_taxonomy.py` (version `P3D-1.0`).
