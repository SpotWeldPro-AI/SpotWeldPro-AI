# ModuleRead R3 Content Audit

**PLATFORM-MODULEREAD-R3-RECOVERY**
Version: 1.0.0 | Date: 2026-11-17

## Purpose

Audit the completeness of all 14 registry entries: section count, bilingual coverage, example count, and accuracy of technical content.

## Section Count Audit

Required: 11 sections per module (both TR and EN), matching the canonical section order:
1. Bu modül nedir? / What is this module?
2. Ne zaman kullanılır? / When should I use it?
3. Gerekli girdiler / Required inputs
4. Adım adım kullanım / Step-by-step tutorial
5. Beklenen çıktı / Expected output
6. Sonucu nasıl yorumlanır? / How to interpret the result
7. Yaygın hatalar / Common mistakes
8. SSS / FAQ
9. Standartlar / Standards and scope
10. Sınırlamalar / Limitations
11. İlgili modüller / Related modules

| Module ID | TR Sections | EN Sections | Examples (TR) | Examples (EN) | R3 Change |
|-----------|------------|------------|---------------|---------------|-----------|
| `analysis` | 11 | 11 | 1 | 1 | None (R2 baseline) |
| `energy` | 11 | 11 | 1 | 1 | Example inputs corrected (R3) |
| `engineering` | 11 | 11 | 1 | 1 | None (R2 baseline) |
| `failure` | 11 | 11 | 1 | 1 | None (R2 baseline) |
| `statistical` | 11 | 11 | 1 | 1 | None (R2 baseline) |
| `inspection` | 11 | 11 | 0 | 0 | None (R2 baseline) |
| `live` | 11 | 11 | 0 | 0 | None (R2 baseline) |
| `models` | 11 | 11 | 0 | 0 | None (R2 baseline) |
| `dashboard` | 11 | 11 | 0 | 0 | None (R2 baseline) |
| `annotation` | 11 | 11 | 0 | 0 | Expanded from 1-section stub (R3) |
| `dataset_dashboard` | 11 | 11 | 0 | 0 | Expanded from 1-section stub (R3) |
| `conflict_review` | 11 | 11 | 0 | 0 | Expanded from 1-section stub (R3) |
| `projects` | 11 | 11 | 0 | 0 | Expanded from 1-section stub (R3) |
| `help` | 11 | 11 | 0 | 0 | Expanded from 1-section stub (R3) |

**Total: 14/14 modules at 11 TR + 11 EN sections**

## Technical Accuracy Notes

### energy — Example Inputs
**R2 problem**: Example used `resistance_mohm`/`weld_time_ms` which do not exist in `EnergyPage.singleForm`.
**R3 fix**: Changed to `resistance_micro_ohm`/`weld_cycles`/`frequency_hz` matching the actual form.
Values: 8kA × 100µΩ × 0.15s (7.5 cycles @ 50Hz) = 960 J verified by I²Rt formula.

### failure — material_family in example
Example in registry uses `'mild steel'` (space) which matches the weld analysis API.
Handler `handleFailureLoadExample` uses hardcoded compatible values (`'mild steel'`), not raw registry inputs, to guarantee API compatibility regardless of future registry edits.

### engineering — material_family display strings
Registry uses API-style keys (`'mild_steel'`); EngineeringPage `elForm` uses Turkish display strings.
`MATERIAL_MAP` in `handleEngineeringLoadExample` translates at handler time. 5 families mapped.

### conflict_review — access restriction
Sections accurately document that DEMO_USER receives 403 PERMISSION_DENIED when accessing conflict review. This is not a bug; it is the intended RBAC behavior documented in the content.

### dataset_dashboard — training gate state
Sections accurately document current state: `training_allowed=False`, 175 E1 conflicts pending. This is a snapshot of the test database state at R3 delivery.

## Registry Structure Audit

| Aspect | R2 State | R3 State |
|--------|----------|----------|
| Main REGISTRY entries | 9 modules | 14 modules |
| STUB_MODULES | 5 stubs (1 section each) | Removed — merged into REGISTRY |
| `makeStub` function | Present | Removed |
| `makeUnknownStub` function | Present | Present (fallback for unknown IDs) |
| `getModuleContent` STUB lookup | Present | Removed (all in REGISTRY) |
| `listSupportedModules` | REGISTRY + STUB_MODULES keys | REGISTRY keys only |

## Load Example Wiring Audit

| Module | R2 Status | R3 Status | Handler |
|--------|-----------|-----------|---------|
| `analysis` | WIRED | WIRED | AnalysisPage:106 `setP(inputs)` |
| `energy` | NOT_WIRED | WIRED | EnergyPage `setSingleForm` + `setTab('single')` |
| `engineering` | NOT_WIRED | WIRED | EngineeringPage `handleEngineeringLoadExample` |
| `statistical` | NOT_WIRED | WIRED | StatisticalAnalysisPage `setTaguchiPending` |
| `failure` | NOT_WIRED | WIRED | FailureProbabilityPage full 2-API chain |
| `inspection` | NOT_WIRED | NOT_WIRED | File-upload module; no scripted example applicable |
| `live` | NOT_WIRED | NOT_WIRED | Streaming module; no scripted example applicable |
| `models` | NOT_WIRED | NOT_WIRED | Read-only; no form to hydrate |
| `dashboard` | NOT_WIRED | NOT_WIRED | Read-only; no form to hydrate |
| `annotation` | NOT_WIRED | NOT_WIRED | Canvas draw; no scripted example |
| `dataset_dashboard` | NOT_WIRED | NOT_WIRED | Read-only counters |
| `conflict_review` | NOT_WIRED | NOT_WIRED | QUALITY_ENGINEER only; DEMO_USER 403 |
| `projects` | NOT_WIRED | NOT_WIRED | CRUD; no example applicable |
| `help` | NOT_WIRED | NOT_WIRED | Static content; no form |

**Wired: 5/14 (35.7%) | Appropriate non-wired: 9/14 (file-upload, streaming, read-only, access-restricted)**
