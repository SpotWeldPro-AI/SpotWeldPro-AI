# ModuleRead R3 Example Matrix

**PLATFORM-MODULEREAD-R3-RECOVERY**
Version: 1.0.0 | Date: 2026-11-17

## Purpose

Records every `Example` entry in `registry.ts` as of R3, the form fields it targets, the expected output, and whether the page handler is wired.

## Matrix

| Module | Example ID | Label | Key Inputs | Expected Output | Handler Wired |
|--------|-----------|-------|------------|-----------------|---------------|
| `analysis` | `weld_mild_2t` | Kaynak Analizi — DC01 2×1.5mm | `material_family:'mild steel'`, `stack_count:'2T'`, `current_ka:8.0`, `weld_cycles:12.0`, `force_kn:3.5`, `tip_diameter_mm:6.0` | `nugget_opt_mm≈5.6` | YES (R2) |
| `energy` | `energy_estimate_mild` | Enerji Tahmini — 100µΩ 8kA 7.5 çevrim@50Hz | `current_ka:8.0`, `resistance_micro_ohm:100.0`, `weld_cycles:7.5`, `frequency_hz:50.0` | `energy_j≈960 J (I²Rt: 8000²×100×10⁻⁶×0.15s)` | YES (R3) |
| `engineering` | `electrode_life_mild` | Elektrot Ömrü — DC01 6mm uç Ø 8kA 50k spot/yıl | `material_family:'mild_steel'`, `tip_diameter_mm:6.0`, `current_ka:8.0`, `annual_spot_count:50000` | `electrode_life_caps≈3000–5000` | YES (R3) |
| `failure` | `failure_mild_2t` | Hata Analizi — DC01 2×1.5mm | Full weld analysis params (mild steel 2T) | Failure mode probabilities | YES (R3) |
| `statistical` | `taguchi_l9_weld` | Taguchi L9 — Kaynak parametreleri | `array_type:'L9'`, 3-4 factors (current, force, time, tip) | L9 design matrix | YES (R3) |
| `inspection` | — | — | File-upload module; no scripted example | — | NO (file-driven) |
| `live` | — | — | Streaming module; no scripted example | — | NO (stream) |
| `models` | — | — | Read-only catalog; no scripted example | — | NO |
| `dashboard` | — | — | Read-only overview; no scripted example | — | NO |
| `annotation` | — | — | Bounding-box draw; no scripted example | — | NO |
| `dataset_dashboard` | — | — | Read-only counters; no scripted example | — | NO |
| `conflict_review` | — | — | QUALITY_ENGINEER only; DEMO_USER 403 | — | NO (access-restricted) |
| `projects` | — | — | CRUD module; example not applicable | — | NO |
| `help` | — | — | Static content; no form | — | NO |

## Energy Example Derivation

Formula: **E = I² × R × t**

- I = 8 kA = 8000 A
- R = 100 µΩ = 100 × 10⁻⁶ Ω
- t = 7.5 cycles ÷ 50 Hz = 0.15 s
- E = 8000² × 100 × 10⁻⁶ × 0.15 = **960 J**

Registry inputs align with EnergyPage `singleForm` field names: `current_ka`, `resistance_micro_ohm`, `weld_cycles`, `frequency_hz`.

## Engineering Material Key Mapping

EngineeringPage uses Turkish display strings; registry uses API-style keys.

| Registry key | EngineeringPage display string |
|-------------|-------------------------------|
| `mild_steel` | `Düşük / Orta Karbonlu Çelik` |
| `galvanized_steel` | `Galvanizli / Kaplamalı Çelik` |
| `AHSS` | `AHSS / UHSS / PHS` |
| `stainless_steel` | `Paslanmaz Çelik` |
| `aluminum_alloys` | `Alüminyum Alaşımları` |

Mapping applied in `handleEngineeringLoadExample()` before calling `setElForm`.

## Statistical Pending Example Flow

`TaguchiTab` is a standalone function component with its own state. Load Example uses a two-step prop mechanism:

1. `StatisticalAnalysisPage.handleStatLoadExample` sets `taguchiPending` state + switches to `'taguchi'` tab.
2. `TaguchiTab` receives `pendingExample` prop; `useEffect` fires when it becomes non-null.
3. `useEffect` applies `arrayType` + `factors` then calls `onExampleConsumed()` to clear.

## Failure Load Example Chain

FailureProbabilityPage has no independent form — it reads from `WeldAnalysisContext`. Load Example fires a full two-API chain:

1. `analyzeWeld(weldReq)` — POST `/weld-analysis` with mild steel 2T 8kA parameters.
2. `setLastAnalysis(weldReq, analysisResult)` — populates context (shared with AnalysisPage).
3. POST `/failure-probability/analyze` with recommended ranges extracted from analysis result.
4. `setResult(resp.data)` — displays failure mode probabilities.
