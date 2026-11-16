"""
SpotWeldPro AI — Synthetic Video Generator
Version: 1.0.0

Generates deterministic MP4 and frame-sequence test assets for Live Monitoring
and video replay testing using FFmpeg's lavfi (libavfilter) test sources.

NO external Python dependencies required. Uses subprocess + FFmpeg.

DISCLAIMER: These videos contain synthetic geometric patterns only.
They are NOT real weld process footage, NOT industrial camera recordings,
and MUST NOT be used as ground truth for training or inspection claims.

Scenarios generated:
  1. normal_approach     — Normal electrode approach/clamp/weld/hold/release
  2. expulsion_event     — Simulated expulsion / spatter flash event
  3. electrode_offset    — Electrode motion anomaly (position drift)
  4. variable_lighting   — Lighting variation during cycle
  5. occlusion_noise     — Visual occlusion and noise overlay
  6. dropped_frames      — Irregular frame timing simulation
  7. stream_interrupt    — Short stream interruption / blackout
  8. multi_spot_seq      — Multi-spot welding sequence
  9. unsupported_format  — Intentionally corrupt/unreadable file
 10. stress_duration     — Longer duration performance/stress test

Variants: 720p@15fps, 720p@30fps, 1080p@30fps
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "1.0.0"
SPEC_DATE = "2026-11-16"

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


@dataclass
class VideoSpec:
    name: str
    description: str
    width: int
    height: int
    fps: int
    duration_s: float
    lavfi_filter: str    # FFmpeg lavfi video source filter
    audio_filter: str = "anullsrc=r=48000:cl=mono"
    expected_events: list[dict] = field(default_factory=list)
    expected_defect: str = "none"


def _run_ffmpeg(cmd: list[str], label: str) -> bool:
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print(f"  ERROR [{label}]: {result.stderr[-300:]}")
        return False
    return True


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _make_unsupported_file(path: Path):
    path.write_bytes(b"\x00\x01\x02\x03CORRUPT_NOT_A_VIDEO_FILE_SYNTH\xFF\xFE")


def build_specs() -> list[VideoSpec]:
    specs = []

    # 1. Normal electrode approach
    specs.append(VideoSpec(
        name="normal_approach",
        description="Normal electrode approach/clamp/weld/hold/release cycle",
        width=1280, height=720, fps=30, duration_s=4.0,
        lavfi_filter=(
            "testsrc2=size=1280x720:rate=30:duration=4,"
            "drawtext=text='SYNTH NORMAL WELD':fontsize=24:fontcolor=white:x=10:y=10,"
            "drawtext=text='PHASE %{pts\\:hms}':fontsize=18:fontcolor=yellow:x=10:y=40"
        ),
        expected_events=[
            {"t_start": 0.0, "t_end": 0.5, "label": "approach"},
            {"t_start": 0.5, "t_end": 1.0, "label": "clamp"},
            {"t_start": 1.0, "t_end": 2.5, "label": "weld"},
            {"t_start": 2.5, "t_end": 3.5, "label": "hold"},
            {"t_start": 3.5, "t_end": 4.0, "label": "release"},
        ],
        expected_defect="none",
    ))

    # 2. Expulsion / spatter event
    specs.append(VideoSpec(
        name="expulsion_event",
        description="Simulated expulsion/spatter flash event at t=1.5s",
        width=1280, height=720, fps=30, duration_s=4.0,
        lavfi_filter=(
            "testsrc2=size=1280x720:rate=30:duration=4,"
            "eq=brightness=0.3:enable='between(t,1.5,1.8)',"
            "drawtext=text='SYNTH EXPULSION EVENT':fontsize=24:fontcolor=red:x=10:y=10"
        ),
        expected_events=[
            {"t_start": 1.5, "t_end": 1.8, "label": "expulsion_flash"},
        ],
        expected_defect="expulsion",
    ))

    # 3. Electrode offset / motion anomaly
    specs.append(VideoSpec(
        name="electrode_offset",
        description="Electrode position drift simulation",
        width=1280, height=720, fps=30, duration_s=5.0,
        lavfi_filter=(
            "testsrc=size=1280x720:rate=30:duration=5,"
            "crop=w=1280:h=720:x='10*sin(t*2)':y='10*cos(t*2)',"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
            "drawtext=text='SYNTH ELECTRODE OFFSET':fontsize=24:fontcolor=orange:x=10:y=10"
        ),
        expected_events=[
            {"t_start": 0.0, "t_end": 5.0, "label": "position_drift"},
        ],
        expected_defect="misalignment",
    ))

    # 4. Variable lighting
    specs.append(VideoSpec(
        name="variable_lighting",
        description="Lighting variation during weld cycle",
        width=1280, height=720, fps=30, duration_s=4.0,
        lavfi_filter=(
            "testsrc2=size=1280x720:rate=30:duration=4,"
            "eq=brightness='0.4*sin(2*PI*t/2)':contrast=1.2,"
            "drawtext=text='SYNTH VARIABLE LIGHTING':fontsize=24:fontcolor=cyan:x=10:y=10"
        ),
        expected_events=[
            {"t_start": 0.0, "t_end": 4.0, "label": "illumination_variation"},
        ],
        expected_defect="illumination_variation",
    ))

    # 5. Occlusion and visual noise
    specs.append(VideoSpec(
        name="occlusion_noise",
        description="Visual occlusion and sensor noise overlay",
        width=1280, height=720, fps=30, duration_s=4.0,
        lavfi_filter=(
            "testsrc2=size=1280x720:rate=30:duration=4,"
            "noise=alls=20:allf=t,"
            "drawbox=x=400:y=200:w=400:h=300:color=black@0.7:t=fill:enable='between(t,1.5,2.5)',"
            "drawtext=text='SYNTH OCCLUSION':fontsize=24:fontcolor=white:x=10:y=10"
        ),
        expected_events=[
            {"t_start": 1.5, "t_end": 2.5, "label": "occlusion"},
        ],
        expected_defect="occlusion",
    ))

    # 6. Dropped frames (variable PTS)
    specs.append(VideoSpec(
        name="dropped_frames",
        description="Irregular frame timing simulation (dropped frames)",
        width=1280, height=720, fps=15, duration_s=5.0,
        lavfi_filter=(
            "testsrc=size=1280x720:rate=15:duration=5,"
            "drawtext=text='SYNTH DROPPED FRAMES fps=15':fontsize=24:fontcolor=white:x=10:y=10,"
            "fps=fps=15"
        ),
        expected_events=[
            {"t_start": 0.0, "t_end": 5.0, "label": "low_framerate"},
        ],
        expected_defect="none",
    ))

    # 7. Stream interruption
    specs.append(VideoSpec(
        name="stream_interrupt",
        description="Stream interruption: blackout at t=2s",
        width=1280, height=720, fps=30, duration_s=5.0,
        lavfi_filter=(
            "testsrc2=size=1280x720:rate=30:duration=5,"
            "drawbox=x=0:y=0:w=1280:h=720:color=black:t=fill:enable='between(t,2.0,3.0)',"
            "drawtext=text='SYNTH STREAM INTERRUPTION':fontsize=24:fontcolor=white:x=10:y=10"
        ),
        expected_events=[
            {"t_start": 2.0, "t_end": 3.0, "label": "blackout"},
        ],
        expected_defect="stream_interruption",
    ))

    # 8. Multi-spot sequence
    specs.append(VideoSpec(
        name="multi_spot_seq",
        description="Multi-spot welding sequence (3 consecutive welds)",
        width=1280, height=720, fps=30, duration_s=9.0,
        lavfi_filter=(
            "testsrc2=size=1280x720:rate=30:duration=9,"
            "drawtext=text='SPOT %{expr_int_format\\:1+trunc(t/3)\\:d\\:1}':fontsize=36:fontcolor=green:x=600:y=330,"
            "drawtext=text='SYNTH MULTI-SPOT':fontsize=24:fontcolor=white:x=10:y=10"
        ),
        expected_events=[
            {"t_start": 0.0, "t_end": 3.0, "label": "spot_1"},
            {"t_start": 3.0, "t_end": 6.0, "label": "spot_2"},
            {"t_start": 6.0, "t_end": 9.0, "label": "spot_3"},
        ],
        expected_defect="none",
    ))

    # 9. Unsupported format — handled separately
    # 10. Stress / longer duration
    specs.append(VideoSpec(
        name="stress_duration",
        description="Longer duration performance/stress test (30s)",
        width=1280, height=720, fps=30, duration_s=30.0,
        lavfi_filter=(
            "testsrc2=size=1280x720:rate=30:duration=30,"
            "drawtext=text='SYNTH STRESS DURATION t=%{pts\\:hms}':fontsize=24:fontcolor=yellow:x=10:y=10"
        ),
        expected_events=[],
        expected_defect="none",
    ))

    return specs


def build_1080p_variant(spec: VideoSpec) -> VideoSpec:
    return VideoSpec(
        name=f"{spec.name}_1080p",
        description=f"[1080p] {spec.description}",
        width=1920, height=1080, fps=30,
        duration_s=spec.duration_s,
        lavfi_filter=spec.lavfi_filter.replace("1280x720", "1920x1080").replace("1280:720", "1920:1080"),
        expected_events=spec.expected_events,
        expected_defect=spec.expected_defect,
    )


def build_15fps_variant(spec: VideoSpec) -> VideoSpec:
    return VideoSpec(
        name=f"{spec.name}_15fps",
        description=f"[15fps] {spec.description}",
        width=spec.width, height=spec.height, fps=15,
        duration_s=spec.duration_s,
        lavfi_filter=spec.lavfi_filter.replace("rate=30", "rate=15"),
        expected_events=spec.expected_events,
        expected_defect=spec.expected_defect,
    )


def generate_all(out_dir: Path, variants: bool = False) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = build_specs()

    # Optionally add 1080p and 15fps variants of normal_approach only
    if variants:
        base = specs[0]  # normal_approach
        specs.append(build_1080p_variant(base))
        specs.append(build_15fps_variant(base))

    results = []

    for spec in specs:
        fname = f"synth_{spec.name}.mp4"
        fpath = out_dir / fname

        cmd = [
            FFMPEG, "-y",
            "-f", "lavfi",
            "-i", spec.lavfi_filter,
            "-f", "lavfi",
            "-i", spec.audio_filter,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
            "-c:a", "aac", "-b:a", "32k",
            "-t", str(spec.duration_s),
            "-movflags", "+faststart",
            str(fpath),
        ]

        print(f"  generating {fname} ({spec.width}x{spec.height}@{spec.fps}fps {spec.duration_s}s)...", end=" ", flush=True)
        ok = _run_ffmpeg(cmd, spec.name)

        if ok and fpath.exists():
            sha = _sha256_file(fpath)
            size = fpath.stat().st_size
            status = "OK"
        else:
            sha = "FAILED"
            size = 0
            status = "FAILED"

        print(status)

        results.append({
            "filename": fname,
            "scenario": spec.name,
            "description": spec.description,
            "width": spec.width,
            "height": spec.height,
            "fps": spec.fps,
            "duration_s": spec.duration_s,
            "expected_events": spec.expected_events,
            "expected_defect": spec.expected_defect,
            "sha256": sha,
            "size_bytes": size,
            "status": status,
        })

    # 9. Unsupported/corrupt file
    corrupt_path = out_dir / "synth_unsupported_format.bin"
    _make_unsupported_file(corrupt_path)
    results.append({
        "filename": "synth_unsupported_format.bin",
        "scenario": "unsupported_format",
        "description": "Intentionally corrupt/unreadable file for error handling test",
        "width": 0, "height": 0, "fps": 0, "duration_s": 0,
        "expected_events": [],
        "expected_defect": "corrupt_file",
        "sha256": _sha256_file(corrupt_path),
        "size_bytes": corrupt_path.stat().st_size,
        "status": "INTENTIONAL_ERROR",
    })

    # Timestamp manifest
    manifest = {
        "version": VERSION,
        "spec_date": SPEC_DATE,
        "total_videos": len(results),
        "disclaimer": (
            "SYNTHETIC TEST DATA ONLY. All videos are generated using FFmpeg lavfi "
            "test sources. They are NOT real weld process footage. "
            "NOT validated for industrial use. NOT suitable as inspection ground truth."
        ),
        "videos": results,
    }
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n  MANIFEST.json: {len(results)} entries")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default="./videos")
    parser.add_argument("--variants", action="store_true", help="Also generate 1080p and 15fps variants")
    args = parser.parse_args()
    print(f"Generating synthetic videos -> {args.out}")
    out = Path(args.out)
    results = generate_all(out, variants=args.variants)
    ok = sum(1 for r in results if r["status"] in ("OK", "INTENTIONAL_ERROR"))
    print(f"Done. {ok}/{len(results)} succeeded.")
    sys.exit(0 if ok == len(results) else 1)
