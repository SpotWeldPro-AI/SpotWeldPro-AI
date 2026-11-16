# SpotWeldPro AI — All Module Coverage Matrix

**Generated:** 2026-11-16  
**HEAD:** b29dce9  
**Branch:** main  
**Baseline tests:** 1805 collected (11 collection errors from incomplete schema stubs)

---

## Coverage Summary

| Dimension | Count |
|---|---|
| Total user-facing modules | 14 |
| Backend API routers | 22 |
| Frontend pages | 14 |
| Backend test files | 82 |
| Baseline tests collected | 1805 |
| ModuleRead button present | 0 (target: 14) |
| Synthetic data scenarios | 0 (target: ≥60) |

---

## Module Coverage Matrix

| ID | TR Name | EN Name | Frontend Page | Backend Endpoint(s) | Required Inputs | Key Outputs | Units | Constraints | Synthetic Test | Expected Result | Limitations | Status | Tutorial |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M01 | Panel | Dashboard | `page=dashboard` | `GET /api/v1/dashboard` | auth token | projects_count, weld_points_count, pending_reviews, model_count | - | authenticated | PARTIAL | summary counts ≥ 0 | counts reflect test DB only | ACTIVE | MISSING |
| M02 | Projeler | Projects & Weld Points | `page=projects` | `POST/GET/PATCH/DELETE /api/v1/projects`, `POST/GET /api/v1/projects/{id}/weld-points` | project name, weld_point params | project CRUD, weld point list | - | owner-scoped | PARTIAL | create→list→delete round-trip | no bulk import UI | ACTIVE | MISSING |
| M03 | Kaynak Lobu | Weld Lobe Lab | `page=engineering` tab=0 | `POST /api/v1/engineering/weld-lobe` | material_family, thickness_mm, force_kn, min_nugget_mm, current range, time range | lobe_points, optimum, safe_window | kA, cycles, mm | thickness_mm 0–10, force_kn 0–50 | PENDING | lobe_points ≥ 10 safe points for mild steel 1.5mm | model is analytical, not physically validated | ACTIVE | MISSING |
| M04 | Elektrot Ömrü | Electrode Life Advisor | `page=engineering` tab=1 | `POST /api/v1/engineering/electrode-life` | material_family, coated, tip_diameter_mm, cooling_flow_lpm, cooling_temp_c, current_ka, annual_spot_count | estimated_life_spots, dress_interval_spots, caps_per_year | spots, lpm, °C, kA | annual_spot_count > 0, tip_diameter > 0 | PENDING | life_spots in [500, 50000] for standard mild-steel | heuristic model, not validated on industrial data | ACTIVE | MISSING |
| M05 | Dinamik Direnç | Dynamic Resistance Analyzer | `page=engineering` tab=2 | `POST /api/v1/engineering/dynamic-resistance` | samples_micro_ohm (≥5 values) | quality_assessment, peak_mohm, initial_mohm, final_mohm | µΩ | min 5 samples | PENDING | quality in {Normal,High,Low,Fault} | classification is heuristic | ACTIVE | MISSING |
| M06 | Pulse Stratejisi | Pulse Strategy Advisor | `page=engineering` tab=3 | `POST /api/v1/engineering/pulse-strategy` | material_family, coated, thickness_ratio, stack_count, adhesive, current_ka, weld_cycles | strategy_name, pulse_count, decision_score | - | thickness_ratio ≥ 1 | PENDING | strategy in {single,double,preheat,post} | advisory only, requires process engineer review | ACTIVE | MISSING |
| M07 | Kaynak Kalite | Weld Quality Analysis | `page=analysis` | `POST /api/v1/weld-analysis` | material_family, subtype, stack_count, layers[], current_ka, weld_cycles, force_kn, tip_diameter_mm, squeeze/hold/cooling | score, risk_level, nugget_opt_mm, compliance_summary | kA, cycles, kN, mm | stack 2T or 3T; layers count must match | PARTIAL | score 0–100, risk in {LOW,MEDIUM,HIGH,CRITICAL} | estimates not independently validated | ACTIVE | MISSING |
| M08 | Hata Analizi | Failure Analysis | `page=failure` | `POST /api/v1/failure-probability/analyze` | material_family, stack_count, thicknesses_mm[], process params, recommended ranges, predicted_nugget_mm | failure_modes (10), probabilities, top_failure | %, mm, kA | thicknesses_mm min_length=2 | PENDING | 10 failure modes returned; probabilities sum ≤ 100 | probabilistic model, not empirically calibrated | ACTIVE | MISSING |
| M09 | Model Kataloğu | Model Catalog | `page=models` | `GET /api/v1/model-catalog`, `POST /api/v1/model-catalog/predict-guard/{id}` | model_id for prediction | catalog list, model metadata, guarded prediction | - | predict-guard respects role permissions | PARTIAL | catalog returns ≥ 1 model | model cards are informational only | ACTIVE | MISSING |
| M10 | İstatistiksel Analiz | Taguchi DOE & ANOVA | `page=statistical` | `POST /api/v1/statistical-analysis/taguchi/design`, `/taguchi/analyze`, `/anova` | array_type (L4/L9/L16/L27), factors[], experiment results | design matrix, S/N ratios, optimal settings, ANOVA table | dB, kA, cycles, kN | L9 requires exactly 3 factors | PARTIAL | L9: 9 runs; optimal within factor range | parametric DOE only; response surface not implemented | ACTIVE | MISSING |
| M11 | Enerji Zekası | Energy Intelligence | `page=energy` | `POST /api/v1/energy/estimate|window|cost|aggregate|dashboard|scenario/compare` | resistance_mohm, current_ka, weld_time_ms, efficiency | I²Rt energy, cost_per_spot, window indicators, dashboard | J, kWh, TRY, € | resistance > 0, current > 0 | PARTIAL | energy_j = I²·R·t within 1% of analytical formula | currency conversion is static, not live | ACTIVE | MISSING |
| M12 | Statik Muayene | Static Inspection | `page=inspection` | `POST /api/v1/vision/static/inspect` | image file (PNG/JPG) | defect_findings, quality_score, annotations | pixels, score 0–100 | file size limit enforced | PARTIAL | synthetic normal image → no defects flagged | vision model is prototype, not production-validated | ACTIVE | MISSING |
| M13 | Canlı İzleme | Live Monitoring | `page=live` | `GET /api/v1/vision/live/sources`, `WS /api/v1/vision/live/ws` | source selection (webcam/RTSP/file) | real-time frames, event flags | fps, ms latency | FILE REPLAY MODE uses local path | PARTIAL | file replay → FILE REPLAY MODE banner displayed | no real industrial camera tested | ACTIVE | MISSING |
| M14 | Anotasyon | Annotation | `page=annotation` | `POST/GET /api/v1/annotations/`, `PATCH /api/v1/annotations/{id}/submit` | annotation data, findings | annotation record, audit trail | - | QUALITY_ENGINEER role required for review | PARTIAL | DEMO_USER can create annotation, not review | 175 E1 pairs PENDING real reviewer assignment | ACTIVE | MISSING |
| M15 | Dataset Paneli | Dataset Dashboard | `page=dataset_dashboard` | `GET /api/v1/annotations/dashboard` | auth token | annotation counts by status, training readiness | - | training_allowed=False until E1-E4 gates pass | PARTIAL | dashboard returns counts; training_allowed=False | E1-E4 gates require QUALITY_ENGINEER sign-off | ACTIVE | MISSING |
| M16 | Çakışma İnceleme | Conflict Review | `page=conflict_review` | `GET /api/v1/annotations/conflicts`, `PATCH /api/v1/annotations/conflicts/{id}` | conflict_id, adjudication decision | updated conflict record | - | QUALITY_ENGINEER only; 175 real pairs PENDING | PARTIAL | DEMO_USER → 403 PERMISSION_DENIED | real E1 pairs must NOT be auto-resolved | RESTRICTED | MISSING |

---

## Backend-only Modules (no direct nav item)

| ID | Name | Endpoint | Purpose | Status |
|---|---|---|---|---|
| B01 | Raporlar | `POST /api/v1/reports/...` | PDF/Excel report generation | ACTIVE |
| B02 | Dijital Kaynak Pasaportu | `POST /api/v1/digital-weld-passport/...` | Lifecycle document | ACTIVE |
| B03 | Makine Hazırlığı | `POST /api/v1/machine-readiness` | Equipment readiness assessment | ACTIVE |
| B04 | Referans Profiller | `GET/POST /api/v1/reference-profiles` | OEM parameter envelopes | ACTIVE |
| B05 | Kural Kayıt | `POST /api/v1/rule-registry/...` | Governance rule lifecycle | ACTIVE |
| B06 | Kural Değerlendirme | `POST /api/v1/rule-evaluation` | Rule applicability checking | ACTIVE |
| B07 | Kanıt Doğrulama | `POST /api/v1/evidence-verification` | Evidence chain validation | ACTIVE |
| B08 | Organizasyonlar | `GET/POST /api/v1/organizations` | Org and membership management | ACTIVE |
| B09 | Mühendislik Kütüphanesi | `GET/POST /api/v1/library/materials|coatings|stack-ups|electrodes|weld-guns|weld-schedules` | Material/process reference data | ACTIVE |

---

## Known Gaps

| Gap | Impact | Resolution |
|---|---|---|
| ModuleRead button absent from all 14 modules | Tutorial system non-functional | Implement in Phase F |
| Synthetic datasets: 0 of 60+ target scenarios | Test coverage limited | Implement in Phase B–D |
| Synthetic PNG images: 1 (synthetic normal only) | Vision testing limited | Implement in Phase C |
| Synthetic MP4 videos: 0 | Live monitoring testing blocked | Implement in Phase D |
| 175 E1 conflict pairs: PENDING | Quality gate blocked | Requires human QUALITY_ENGINEER |
| training_allowed=False | Model training gate closed | Requires E1-E4 completion |
| Playwright E2E tests: 0 for new modules | Browser verification incomplete | Implement in Phase E |
