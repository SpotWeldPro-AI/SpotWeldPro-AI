# Module Example Execution Matrix

**PLATFORM-SYNTH-QA-MODULEREAD-R2**
Version: 1.0.0 | Date: 2026-11-17

## Purpose

This matrix documents the Load Example and Run Example capability for each ModuleRead-enabled page. It distinguishes between:
- **WIRED**: Example loads into live form and fires real API call
- **NOT_WIRED**: Button present in panel but no `onLoadExample` callback provided
- **NOT_SUPPORTED**: Module has no form inputs to load
- **STUB**: Module has minimal help content; no examples defined

## Example Execution Matrix

| Module ID | Page | Has Examples in Registry | onLoadExample Wired | onRunExample Wired | Actual API Tested | Status |
|-----------|------|--------------------------|---------------------|--------------------|--------------------|--------|
| `analysis` | AnalysisPage | YES (2: TR+EN) | YES — `setP(inputs as WeldAnalysisRequest)` | No | `POST /api/v1/weld-analysis` | WIRED |
| `dashboard` | DashboardPage | No | No | No | None (read-only) | NOT_SUPPORTED |
| `engineering` | EngineeringPage | No | No | No | Multiple `/api/v1/engineering/*` | NOT_WIRED |
| `failure` | FailureProbabilityPage | No | No | No | `POST /api/v1/failure-probability/analyze` | NOT_WIRED |
| `statistical` | StatisticalAnalysisPage | No | No | No | Multiple `/api/v1/statistical-analysis/*` | NOT_WIRED |
| `energy` | EnergyPage | No | No | No | `POST /api/v1/energy/estimate` | NOT_WIRED |
| `inspection` | StaticInspectionPage | YES (file note only) | No | No | `POST /api/v1/vision/static/analyze` | FILE_UPLOAD_ONLY |
| `live` | LiveMonitoringPage | No | No | No | WebSocket stream | NOT_WIRED |
| `models` | ModelCatalogPage | No | No | No | `GET /api/v1/model-catalog` | NOT_SUPPORTED |
| `annotation` | AnnotationPage | No | No | No | None | STUB |
| `dataset_dashboard` | DatasetDashboardPage | No | No | No | None | STUB |
| `projects` | ProjectsPage | No | No | No | CRUD endpoints | STUB |
| `conflict_review` | ConflictReviewPage | No | No | No | PATCH /api/v1/annotation/conflicts/* | STUB |
| `help` | HelpCenterPage | No | No | No | None | NOT_SUPPORTED |

## Working Example Actions (Verified)

### analysis — Mild Steel 2T Example

The `AnalysisPage` has `onLoadExample` wired to `setP(inputs as WeldAnalysisRequest)`. When a user clicks "Load Example" in the ModuleRead panel:

1. Confirm Replace dialog shows (if form has data)
2. On confirm: `setP` is called with the example inputs
3. Form fields populate with:
   - `material_family`: `mild steel`
   - `stack_count`: `2T`
   - `current_ka`: `8.0`
   - `weld_cycles`: `12.0`
   - `force_kn`: `3.5`
   - `tip_diameter_mm`: `6.0`
4. User clicks Analyze to run the backend call

**R2 fix**: Example inputs updated from `mild_steel` (rejected with 422) to `mild steel` (accepted — matches API alias).

### inspection — Static Synth Image Note

The `inspection` module has an example with a file note:
```
_note: 'Upload frontend/public/fixtures/swp-test-weld-surface.png'
```
No form population is possible (image upload is file-picker only). The note is informational.

## NOT_WIRED Modules — Implementation Path

For form-heavy modules where `onLoadExample` could be useful:

| Module | Complexity | Recommended Approach |
|--------|-----------|---------------------|
| `energy` | Low (4 fields) | Direct `setForm(inputs)` callback |
| `failure` | Medium (12+ fields) | Spread inputs across controlled form state |
| `engineering` | High (tab-dependent) | Per-tab form refs needed |
| `statistical` | High (dynamic factor/results arrays) | Custom deserializer needed |

**Decision**: Phase G scope. No inert buttons added. The `onLoadExample` prop exists on `ModuleReadPanel`; pages simply omit it when not ready.

## Confirmation Before Replace — Verified

`ModuleReadPanel.tsx` implements the confirm dialog:
1. User clicks "Load Example" in panel
2. `setConfirmReplace(exampleId)` and `setPendingExample({id, inputs})`
3. A dialog renders: "Replace form values with example?"
4. Only on confirm does `onLoadExample(exampleId, inputs)` fire
5. Cancel: `setConfirmReplace(null); setPendingExample(null)` — form unchanged

## Synthetic Data Example Schemas (Used in Tests)

| Module | Test Scenario | API Input Schema Change (R2) |
|--------|--------------|------------------------------|
| Weld Analysis | `mild steel 2T` | `material_family: "mild steel"` (space) |
| Weld Analysis | `galvanized steel 2T` | `material_family: "galvanized steel"` (space) |
| Failure Probability | base payload | `material_family: "mild steel"` (space) |
| Engineering: Weld Lobe | mild steel | `material_family: "mild steel"` (space) |
| Engineering: Electrode Life | mild/galvanized | `material_family: "mild steel"` / `"galvanized steel"` |
| Engineering: Pulse Strategy | mild/galvanized | Same as above |
| Energy Estimate | I²Rt oracle | `resistance_micro_ohm: 120.0` + `weld_cycles: 16.0` (not `resistance_mohm`/`weld_time_ms`) |
| Projects | CRUD round-trip | `project_code`/`project_name` (not `name`/`description`) |
| Statistical: Taguchi Analyze | L9 | `sn_objective: "larger_is_better"` + `responses: [...]` list (not `optimize`/`results` dict) |
| Statistical: ANOVA | 3 groups | `group_name` (not `name`) + no `significance_level` field |
