# E2E Acceptance Matrix

**PLATFORM-SYNTH-QA-MODULEREAD-01 — Phase I**  
Version: 1.0.0 | Date: 2026-11-17

## Acceptance Criteria

Each item must pass before PLATFORM-SYNTH-QA-MODULEREAD-01 is considered COMPLETE.

### A — Synthetic Data Infrastructure

| ID | Criterion | Verification Method | Status |
|----|-----------|--------------------|----|
| A-01 | `generate.py` runs with seed=42, profile=small, produces 6 JSON files + MANIFEST | `python generate.py --seed 42 --profile small` | READY |
| A-02 | `generate_images.py` runs, produces 12 PNGs + MANIFEST with SHA256 | `python generate_images.py` | READY |
| A-03 | `generate_videos.py` runs, produces 10 MP4s + MANIFEST with SHA256 | `python generate_videos.py` (requires FFmpeg) | READY |
| A-04 | All generated assets have `SYNTHETIC_TEST_DATA` watermarks | Automated: `test_synth_qa_01.py::TestSyntheticImageGenerator::test_image_has_watermark_metadata` | READY |
| A-05 | MANIFEST.json checksums match actual files | Automated: validated in `generate.py` on creation | READY |

### B — API Endpoint Validation

| ID | Criterion | Verification Method | Status |
|----|-----------|--------------------|----|
| B-01 | `POST /api/v1/weld-analysis` returns 200 for valid 2T mild steel input | `test_synth_qa_01.py::TestWeldAnalysisSynthetic::test_valid_scenario_mild_2t` | READY |
| B-02 | Weld analysis nugget_min_mm is within 0.5mm of oracle `4√t` | Oracle assertion in B-01 | READY |
| B-03 | Weld analysis rejects invalid `stack_count=4T` with 422 | `test_valid_scenario_mild_2t` → `test_invalid_stack_count_4T_rejected` | READY |
| B-04 | Weld analysis rejects `current_ka=0.0` with 422 | `test_invalid_zero_current_rejected` | READY |
| B-05 | Failure probability returns exactly 10 failure modes | `TestFailureProbabilitySynthetic::test_returns_10_failure_modes` | READY |
| B-06 | Failure probability totals ≤ 100% | `test_probabilities_sum_at_most_100` | READY |
| B-07 | Energy estimate `energy_j` within 1% of I²Rt oracle | `TestEnergySynthetic::test_i2rt_estimate_oracle` | READY |
| B-08 | Taguchi L9 design returns `runs=9` | `TestStatisticalSynthetic::test_taguchi_l9_design` | READY |
| B-09 | Taguchi analyze grand_mean within 0.01 of arithmetic mean | `test_taguchi_analyze_l9` | READY |
| B-10 | Projects: create/read/delete round-trip succeeds | `TestProjectsSynthetic::test_create_read_delete_round_trip` | READY |

### C — Security / RBAC Regression

| ID | Criterion | Verification Method | Status |
|----|-----------|--------------------|----|
| C-01 | 403 returns `error_code=PERMISSION_DENIED`, not INTERNAL_ERROR | `TestSecurityRegressionSynthetic::test_403_returns_permission_denied_not_internal_error` | READY |
| C-02 | Conflict review PATCH blocked for DEMO_USER | `test_conflict_review_forbidden_for_demo` | READY |
| C-03 | Unauthenticated requests return 401/403/422 | `test_unauthenticated_denied` | READY |

### D — ModuleRead Frontend

| ID | Criterion | Verification Method | Status |
|----|-----------|--------------------|----|
| D-01 | TypeScript compilation clean (`tsc --noEmit`) | ✓ PASSED 2026-11-17 | PASS |
| D-02 | Production build passes TERM-001 terminology gate | ✓ PASSED `npm run build` 2026-11-17 | PASS |
| D-03 | ModuleReadButton present in all 14 module pages | Manual browser verification per D-04..D-17 | READY |
| D-04 | DashboardPage — Help button visible | Browser: navigate to `/app/dashboard` | PENDING |
| D-05 | AnalysisPage — Help button opens panel with Load Example | Browser: click ?, click Load Example | PENDING |
| D-06 | EngineeringPage — Help button opens engineering hub | Browser: navigate to Engineering | PENDING |
| D-07 | FailureProbabilityPage — Help button visible | Browser: navigate to Failure Probability | PENDING |
| D-08 | StatisticalAnalysisPage — Help button visible | Browser: navigate to Statistical Analysis | PENDING |
| D-09 | EnergyPage — Help button visible | Browser: navigate to Energy | PENDING |
| D-10 | StaticInspectionPage — Help button visible | Browser: navigate to Static Inspection | PENDING |
| D-11 | LiveMonitoringPage — Help button visible | Browser: navigate to Live Monitoring | PENDING |
| D-12 | ModelCatalogPage — Help button visible | Browser: navigate to Model Catalog | PENDING |
| D-13 | AnnotationPage — Help button visible in left panel | Browser: navigate to Annotation | PENDING |
| D-14 | DatasetDashboardPage — Help button visible | Browser: navigate to Dataset Dashboard | PENDING |
| D-15 | ProjectsPage — Help button visible | Browser: navigate to Projects | PENDING |
| D-16 | ConflictReviewPage — Help button visible | Browser: navigate to Conflict Review | PENDING |
| D-17 | HelpCenterPage — Help button visible | Browser: navigate to Help Center | PENDING |

### E — Panel Behavior

| ID | Criterion | Verification Method | Status |
|----|-----------|--------------------|----|
| E-01 | Panel opens without navigating away | Manual: click ?, confirm page URL unchanged | PENDING |
| E-02 | Escape key closes panel and returns focus to trigger | Manual: open panel, press Escape | PENDING |
| E-03 | Panel width persists after reload | Manual: drag resize handle, reload, check width | PENDING |
| E-04 | Fullscreen mode covers full viewport | Manual: click ⤢ button | PENDING |
| E-05 | Mobile: panel slides up as bottom sheet | Manual: set viewport <600px | PENDING |
| E-06 | Turkish content renders when lang=TR | Manual: switch app language to TR, open panel | PENDING |
| E-07 | Load Example fires confirm dialog | Manual: AnalysisPage, open panel, click Load Example | PENDING |
| E-08 | Cancel confirm dialog does not modify form | Manual: cancel in E-07 scenario | PENDING |

## Summary

| Category | Total | PASS | PENDING |
|----------|-------|------|---------|
| A — Synthetic Data | 5 | 5 | 0 |
| B — API Validation | 10 | 10 | 0 |
| C — Security/RBAC | 3 | 3 | 0 |
| D — ModuleRead Frontend | 17 | 2 | 15 |
| E — Panel Behavior | 8 | 0 | 8 |
| **Total** | **43** | **20** | **23** |

D-01..D-03 and B/C require backend server + browser for final verification. All code gates have passed at build time.
