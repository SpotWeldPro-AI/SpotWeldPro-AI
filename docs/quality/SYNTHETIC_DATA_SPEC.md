# Synthetic Test Data Specification

**PLATFORM-SYNTH-QA-MODULEREAD-01 — Phase B/C/D**  
Version: 1.0.0 | Date: 2026-11-17

## Purpose

Synthetic datasets provide deterministic, reproducible test inputs for all application analysis modules. They are used for:

1. Automated regression testing of API endpoints
2. Demo mode with realistic but non-real data
3. Performance/stress testing at configurable scale

**CRITICAL ISOLATION RULE**: Synthetic data is NEVER used as ground truth for model training, real quality decisions, or industrial accuracy claims. All synthetic labels are marked with `SYNTHETIC_TEST_DATA` metadata. The E1-E4 training gates and 175 pending reviewer conflicts use exclusively real industrial data — synthetic data never enters those pipelines.

## Generator Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| `generate.py` | Tabular analysis scenarios | `backend/tests/synthetic_data/` |
| `generate_images.py` | PNG weld surface images | `backend/tests/synthetic_data/` |
| `generate_videos.py` | MP4 inspection stream clips | `backend/tests/synthetic_data/` |

## generate.py — Tabular Dataset Generator

### Usage
```bash
cd backend
python tests/synthetic_data/generate.py [--seed N] [--profile small|medium|stress] [--out PATH]
```

Default output: `backend/tests/synthetic_data/datasets/`

### Profiles

| Profile | Scenarios | Use Case |
|---------|-----------|----------|
| `small` | 40 | Unit tests, CI |
| `medium` | 80 | Integration tests |
| `stress` | 220 | Load/performance testing |

### Output Files
- `weld_analysis.json` — 2T/3T weld analysis scenarios
- `failure_probability.json` — Failure mode analysis scenarios
- `engineering.json` — Lobe/electrode/DR/pulse engineering scenarios
- `statistical.json` — Taguchi L4/L9, ANOVA group scenarios
- `energy.json` — I²Rt energy calculation scenarios
- `projects.json` — Project CRUD scenarios
- `MANIFEST.json` — SHA256 checksums, metadata, generation timestamp

### Oracle Independence

Each scenario includes `expected_oracle` computed by an independent formula, NOT by calling the application. This ensures the application is NOT its own ground truth.

| Module | Oracle Formula |
|--------|---------------|
| Energy | `E = I²Rt` (I in A, R in Ω, t in s) |
| Weld nugget min | `d_min = 4√t` (AWS D8.9 criterion, t = thinnest layer mm) |
| Taguchi grand mean | Arithmetic mean of all response values |
| ANOVA SST | `SST = Σ(xᵢ - x̄)²` |
| Weld lobe safe | Grid enumeration of I×t combinations meeting quality criteria |

### Scenario Schema

```json
{
  "scenario_id": "wa_0001",
  "profile": "small",
  "seed": 42,
  "description": "2T mild steel, nominal parameters",
  "module": "weld_analysis",
  "inputs": { ... },
  "expected_oracle": {
    "nugget_min_mm": 4.899,
    "nugget_oracle_method": "4√t AWS D8.9",
    "score_range": [60, 100],
    "risk_level": "LOW"
  },
  "expected_status": "success",
  "oracle_method": "aws_d8_9_nugget + score_heuristic"
}
```

## generate_images.py — PNG Image Generator

### Usage
```bash
python tests/synthetic_data/generate_images.py [--seed N] [--out PATH]
```

### Scenarios (12 total)

| Scenario | Description | Expected Class |
|----------|-------------|----------------|
| `normal_circular` | Ideal circular nugget impression | PASS |
| `elliptical_indentation` | Elliptical shape from misaligned electrode | WARNING |
| `misalignment` | Off-center weld impression | WARNING |
| `surface_cracks` | Radial cracks in HAZ | FAIL |
| `spatter` | Expulsion material around nugget | WARNING |
| `discoloration` | Heat discoloration (blue/purple) | INFO |
| `missing_weld` | No visible impression | FAIL |
| `multi_spot_pattern` | Multiple sequential spots | INFO |
| `blur_variation` | Motion blur, various levels | UNCERT |
| `illumination_variation` | High contrast, over/underexposed | UNCERT |
| `noise_heavy` | High sensor noise | UNCERT |
| `rotation_45deg` | Rotated 45° acquisition | INFO |

### Image Properties
- Format: PNG, 320×240 pixels
- Color: RGB
- Metadata: `tEXt` chunk with `SYNTHETIC_TEST_DATA` key
- Warning watermark: red X at corners
- Pixel mask JSON: bounding box per region of interest

## generate_videos.py — MP4 Video Generator

### Usage
```bash
python tests/synthetic_data/generate_videos.py [--seed N] [--out PATH] [--variants]
```

Requires: FFmpeg (path: `C:/ffmpeg_new/ffmpeg-9.0.2-essentials_build/bin/ffmpeg`)

### Scenarios (10 total)

| Scenario | Duration | FPS | Description |
|----------|----------|-----|-------------|
| `normal_approach` | 5s | 30 | Clean electrode approach |
| `expulsion_event` | 5s | 30 | Spatter/expulsion at t=2.5s |
| `electrode_offset` | 5s | 30 | 15° tilt throughout |
| `variable_lighting` | 5s | 30 | Brightness oscillation |
| `occlusion_noise` | 5s | 30 | Partial occlusion + noise |
| `dropped_frames` | 5s | 15 | Frame drops (15fps) |
| `stream_interrupt` | 5s | 30 | 0.5s blackout at t=2.5s |
| `multi_spot_seq` | 10s | 30 | 3 consecutive weld events |
| `stress_duration` | 60s | 30 | Long-duration stability |
| `corrupt_header` | — | — | 128-byte corrupt file |

### Video Properties
- Resolution: 1280×720 (base), 1920×1080 and 640×360 with `--variants`
- Codec: H.264 (libx264), AAC audio (lavfi sine)
- Event labels: drawn with `drawtext` filter
- Per-video metadata: `VIDEO_SYNTH_VERSION=1.0`, `SYNTHETIC_TEST_DATA=1`

## Security and Isolation Guarantees

1. **No production database writes**: Generators write only to output directories
2. **No model training**: Synthetic data is never fed to E1-E4 training pipelines
3. **No reviewer conflicts modified**: 175 pending real conflicts untouched
4. **No DEMO_USER isolation breach**: Synthetic test user is separate from DEMO_USER
5. **SHA256 integrity**: All generated files have checksums in MANIFEST.json
6. **Watermarks**: All synthetic images and videos contain embedded `SYNTHETIC_TEST_DATA` metadata
7. **Never claim industrial accuracy**: Synthetic data is explicitly for testing only
