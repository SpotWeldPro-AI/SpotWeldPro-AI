# SpotWeldPro-AI Vision Pipeline — Development Roadmap

**Last updated:** 2026-11-11  
**Status:** Phase 2 complete; Phase 3 interfaces defined, blocked on dataset collection

---

## Phase overview

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | Static image inspection, API endpoints, frontend pages | **COMPLETE** (commit 48cfb65) |
| Phase 2 | Live video acquisition, motion detection, WebSocket streaming | **COMPLETE** (commit bf8fc10) |
| Phase 3 | Temporal feature extraction, CNN+GRU/LSTM interfaces, dataset audit, model validation plan | **INTERFACES DEFINED — blocked on dataset** |
| Phase 4 | Model training, evaluation, staged deployment | NOT STARTED — requires Phase 3 dataset approval |

---

## Phase 1 — Static image inspection (COMPLETE)

**Commit:** 48cfb65

### Deliverables
- `POST /api/v1/vision/static/inspect` — synchronous per-image quality indicators
- `GET /api/v1/vision/live/ws` — WebSocket framework (Phase 1 stub)
- `StaticInspectionPage.tsx` — image upload and result display
- `LiveMonitoringPage.tsx` — framework placeholder
- Vision package: `preprocessing.py`, `static_analysis.py`, `schemas.py`
- Capture adapters: `file_adapter.py`, `webcam_stub.py`, `rtsp_stub.py`
- Temporal interfaces: `interfaces.py` (abstract base classes; no weights)

### Tests
- 53 tests: `test_vision_preprocessing` (21), `test_vision_static_analysis` (19), `test_vision_api` (13)

### Known limitations
- Static inspection is stateless; results not linked to weld records yet
- WebSocket is framework-only; no live data delivery in Phase 1

---

## Phase 2 — Live video acquisition and streaming (COMPLETE)

**Commit:** bf8fc10

### Deliverables
- `CaptureWorker` — daemon thread, bounded queue (60 frames), timestamps, dropped-frame tracking, exponential-backoff reconnect
- `MotionEventDetector` — mean absolute difference on Gaussian-blurred frames; emits `TemporalEvent`; explicitly NOT a weld quality classifier
- `WeldEventWindow` — four-state machine (IDLE → MOTION_ONSET → ACTIVE_MOTION → MOTION_END); emits `WeldEventRecord` with disclaimer
- `LiveSessionManager` — singleton; enforces max 8 sources and 8 WebSocket sessions
- `run_capture_benchmark()` — documented hardware benchmarks; never fabricates results
- WebSocket protocol: token auth as first message, 4001/4029 error codes, base64 JPEG frames, `TemporalEvent`, `WeldEventRecord`, `LiveStreamMetrics`
- REST endpoints: `GET /sources`, `GET /sources/{source_id}/metrics` (Bearer auth)
- `LiveMonitoringPage.tsx` — full rewrite; real metrics display, live JPEG preview, motion event log, weld window history with disclaimer

### Tests
- 91 tests: worker (15), motion (18), event_window (17), session_manager (15), benchmark (11), ws (15)

### Benchmark (actual hardware, 2026-11-11)
- Hardware: Windows 10, Intel Core i5-8250U, Python 3.12.7, OpenCV 5.0.0
- 640×480, 300 frames, file adapter (max speed): FPS=148.58, latency p95=4.41ms
- Full pipeline (decode+motion) 640×480, 200 frames: p95=4.12ms, implied max FPS at p95=243
- **Note:** These are in-process benchmarks without real camera I/O. USB/RTSP throughput is I/O-bound; not measured.

### Known limitations (carry forward)
- `WebcamAdapter` and `RTSPAdapter`: interface only; not hardware-validated
- Static inspection results not linked to weld records (deferred)
- `psutil` not installed; CPU%/RSS metrics report None in benchmarks
- i18n: inspection/live nav items use English fallback (no translation keys added)
- Session manager `reset_session_manager` test fixture accesses internals (`_lock`, `_ws_count`) directly

---

## Phase 3 — Temporal feature extraction and model interfaces (IN PROGRESS)

**Status:** Interfaces and gates defined. Blocked on dataset collection and audit approval.

### What is defined
- `DatasetAudit` — mandatory pre-training audit schema; `is_training_allowed()` gate blocks on:
  - Status ≠ APPROVED
  - No reviewer assigned
  - Any class with `VISUAL_INSPECTION` or `ASSUMED` labels
  - Invalid train/validation/test split
  - Any open blocking issues
- `SplitDescriptor` — leakage-safe split with required grouping keys (weld_id, part_id, session_id, production_batch)
- `ModelValidationPlan` — deployment gate; `deployment_allowed()` requires:
  - Dataset audit approved
  - GRU/LSTM baseline published
  - Latency validated on target hardware
  - At least one causal experiment passing all evaluation gates
- `ExperimentSpec` — per-experiment config and gate checker
- `EvaluationGates` — placeholder targets: precision ≥ 0.85, recall ≥ 0.80, F1 ≥ 0.82, latency ≤ 50ms
- `NO_AUDIT` sentinel — training blocked; no dataset exists
- `CURRENT_PLAN` sentinel — `deployment_allowed()` = False; both experiments `DATASET_PENDING`

### What is NOT present
- No model weights of any kind
- No training metrics (all placeholders in tests are gate-logic verification only)
- No dataset (no labeled images, no ground truth)
- No training code

### Tests
- 27 tests: `test_temporal_phase3.py`
  - `TestDatasetAuditGate` (8), `TestSplitDescriptorValidation` (3)
  - `TestModelValidationPlan` (8), `TestExperimentSpec` (4)
  - `TestNotLoadedSentinels` (3)

### Blockers before Phase 4 can begin
1. **Dataset collection** — ground truth from destructive testing (physical cross-section or accepted reference test reports); never from visual inspection alone
2. **Dataset audit approval** — `DatasetAudit` with `status=APPROVED`, qualified reviewer, all labels from `DESTRUCTIVE_TEST` or `ACCEPTED_REFERENCE`, leakage-safe split
3. **Minimum dataset size** — define based on expected OK:NOK ratio and desired precision/recall targets; document in `DatasetAudit.notes`
4. **Temporal continuity** — all frames of a weld cycle must stay in one split (train OR test, never both)
5. **Hardware latency validation** — confirm inference latency on actual target hardware (camera + compute unit) before `hardware_latency_validated=True`

---

## Phase 4 — Model training, evaluation, staged deployment (NOT STARTED)

**Gate:** Phase 4 cannot begin until `DatasetAudit.is_training_allowed() == True` and `ModelValidationPlan.dataset_audit_approved == True`.

### Planned experiment order
1. CNN feature extractor (MobileNetV2 or EfficientNet-Lite0 backbone, frozen weights as starting point)
2. GRU baseline classifier (window_size=16, hidden_dim=128) — `exp_01_gru_baseline`
3. LSTM baseline classifier (same window_size and hidden_dim) — `exp_02_lstm_baseline`
4. Publish GRU vs LSTM comparison (precision, recall, F1, inference latency)
5. Only after baseline is published: consider transformer or attention variant

### Deployment conditions (all required)
- `DatasetAudit.is_training_allowed() == True`
- Baseline (GRU/LSTM) published and reviewed
- Latency validated on target hardware
- At least one experiment with `is_causal=True` and all gates passing
- Human sign-off (not covered by programmatic gate)

### Hard constraints (from specification)
- `is_causal=True` required for any real-time inference model
- No automatic PLC actuation in initial release
- No automatic model deployment
- No hardcoded weld acceptance thresholds without verified applicability
- Do not claim accuracy until measured on a held-out test set

---

## Cumulative test counts

| Phase | New tests | Total vision tests |
|-------|-----------|-------------------|
| Phase 1 | 53 | 53 |
| Phase 2 | 91 | 144 |
| Phase 3 (interfaces) | 27 | 171 |

Pre-existing test failures (unrelated to vision): 137 (baseline from before Phase 1; not introduced by vision work)

---

## Architecture summary

```
Camera/File → CaptureWorker → bounded queue → WS session
                                   ↓
                          MotionEventDetector (deterministic MAD)
                                   ↓
                          WeldEventWindow (4-state machine)
                                   ↓
                    [Phase 4: CNN extractor → GRU/LSTM classifier]
                                   ↓
                          WebSocket → LiveMonitoringPage
```

**Separation of concerns:**
- STATIC inspection: `POST /vision/static/inspect` — per-image, synchronous
- LIVE monitoring: WebSocket — real-time metrics, motion events, weld windows
- TEMPORAL AI (Phase 4): CNN+GRU/LSTM — not deployed; blocked on dataset
