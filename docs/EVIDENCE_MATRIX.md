# EVIDENCE MATRIX — Defect Detection Capabilities
**Project:** SpotWeldPro AI · Vision P3D  
**Version:** P3D-1.0  
**Date:** 2026-11-13

This matrix answers one question for each defect: **which inspection method can reliably detect it?**

Legend:  
✅ Reliable detection · ⚠️ Indicator only (confirms presence, not severity) · ❌ Cannot detect · — Not applicable

---

## Detection Capability Matrix

| Defect Code | Turkish Name | English Name | Surface Image | Manual Visual | Peel / Chisel Test | Ultrasonic (UT) | Cross-Section | Notes |
|-------------|--------------|--------------|:---:|:---:|:---:|:---:|:---:|-------|
| `ok` | Kabul | Accepted | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | Surface OK does NOT confirm nugget diameter |
| `capak` | Çapak | Spatter | ✅ | ✅ | — | — | — | Visible from surface with high confidence |
| `deformeli` | Deformeli | Deformed | ✅ | ✅ | — | — | — | Electrode wear indicator |
| `kopuk` | Kopuk | Broken | ⚠️ | ⚠️ | ✅ | — | ✅ | Surface shows signs; peel confirms |
| `eksik` | Eksik | Missing | ✅ | ✅ | — | — | — | Absence of indentation is unambiguous |
| `kucuk_cekirdek` | Küçük Çekirdek | Small Nugget | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | Surface = indicator only; cross-section required |
| `kacik` | Kaçık | Misaligned | ✅ | ✅ | — | — | — | Offset visible from above |
| `ust_uste` | Üst Üste | Overlapping | ✅ | ✅ | — | — | — | Two impressions visible |
| `kenar` | Kenar | Edge Weld | ✅ | ✅ | — | — | — | Edge proximity visible |
| `delik` | Delik | Burn-Through | ✅ | ✅ | — | — | — | Hole visible; automatic reject |
| `cift_sac` | Çift Sac | Double Sheet | ⚠️ | ⚠️ | ✅ | — | ✅ | Extra layer may not be visible from above |
| `cokertme` | Çökürtme | Crush Dent | ✅ | ✅ | — | — | — | Depth measurement needed for severity |
| `generic_bad` | Genel Hatalı | Generic NOK | ⚠️ | ⚠️ | — | — | — | Unspecified — classifier not applicable |
| `expulsion` | Pıskırma | Expulsion | ✅ | ✅ | ⚠️ | — | ✅ | No V5 labels; cross-section for nugget loss |
| `incomplete_fusion` | Yetersiz Nüfuziyet | Incomplete Fusion | ❌ | ❌ | ✅ | ✅ | ✅ | Surface may be NORMAL; most dangerous defect |
| `porosity` | Gözenek | Porosity | ❌ | ❌ | — | ✅ | ✅ | Phased-array UT or radiography |
| `hot_crack` | Sıcak Çatlak | Hot Crack | ❌ | ❌ | — | ✅ | ✅ | Metallographic or SEM |
| `cold_lap` | Soğuk Bindirme | Cold Lap | ❌ | ❌ | ✅ | ✅ | ✅ | Peripheral bonding failure |

---

## By Inspection Method

### Surface Image Classification (Camera / AI)

**Can reliably detect (11 classes):**  
`capak`, `deformeli`, `eksik`, `kacik`, `ust_uste`, `kenar`, `delik`, `cokertme`, `ok`\*, `expulsion`\*\*

**Can detect as indicator only (4 classes):**  
`kopuk` (surface shows signs; peel confirms), `kucuk_cekirdek` (indicator only), `cift_sac` (surface indicator), `generic_bad` (unspecified — not for training)

**Cannot detect (4 classes):**  
`incomplete_fusion`, `porosity`, `hot_crack`, `cold_lap`

\* `ok` from surface image = SURFACE_OBSERVATION only. Does not confirm nugget diameter.  
\*\* `expulsion` has no V5 training data yet.

### Manual Visual Inspection (Qualified Inspector)

Same capability as surface image classification for the classes listed above. Visual inspection cannot detect internal defects.

### Peel / Chisel Destructive Test

Confirms: `kopuk` (broken), `kucuk_cekirdek` (nugget size), `cift_sac` (extra layer), `incomplete_fusion`, `cold_lap`

### Ultrasonic Testing (UT / Phased-Array)

Detects: `kucuk_cekirdek` (nugget diameter), `incomplete_fusion`, `porosity`, `hot_crack`, `cold_lap`  
Best non-destructive method for internal defects.

### Metallographic Cross-Section

Definitive confirmation for all defects. Required for: `kopuk`, `kucuk_cekirdek`, `cift_sac`, `incomplete_fusion`, `porosity`, `hot_crack`, `expulsion` (nugget loss), `cold_lap`

---

## Implication for SpotWeldPro AI

| Use Case | Feasible with Surface Images? | Additional Requirement |
|----------|-------------------------------|------------------------|
| Binary OK/NOK surface classifier | ⚠️ CONDITIONAL | E1–E4 remediation; SURFACE_OBSERVATION labels; not for nugget acceptance |
| Multi-class surface defect detection | ⚠️ CONDITIONAL | Per-class training data needed; minor classes insufficient |
| Nugget diameter acceptance gate | ❌ NO | UT or cross-section ground truth required |
| Internal defect detection | ❌ NO | UT / NDT infrastructure required |
| Post-weld visual audit (non-safety) | ✅ AFTER REMEDIATION | After E1–E4 gates resolved |

---

## References

- ISO 15614-12: Specification and qualification of welding procedures for metallic materials
- AWS D8.1M: Specification for Automotive Weld Quality — Resistance Spot Welding of Steel
- Khuenkaew 2019: RSW nugget quality study (SUS316L + SUS425, 1.5 mm)
- P3B/P3C reports: `docs/DATASET_AUDIT_REPORT.md`, `docs/DATASET_CLEANING_REPORT.md`
