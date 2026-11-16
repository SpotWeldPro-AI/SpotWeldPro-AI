"""
SpotWeldPro AI — Synthetic Dataset Factory
Version: 1.0.0
Seed: deterministic, configurable via --seed

Usage:
    python generate.py --seed 42 --profile small --out ./datasets
    python generate.py --seed 42 --profile medium --out ./datasets
    python generate.py --seed 42 --profile stress --out ./datasets

Outputs:
    datasets/weld_analysis.json
    datasets/failure_probability.json
    datasets/engineering_weld_lobe.json
    datasets/engineering_electrode_life.json
    datasets/engineering_dynamic_resistance.json
    datasets/engineering_pulse_strategy.json
    datasets/statistical_taguchi.json
    datasets/energy_estimate.json
    datasets/energy_window.json
    datasets/projects.json
    datasets/invalid_inputs.json
    datasets/MANIFEST.json

Each file contains a list of scenarios with keys:
    scenario_id, profile, seed, description, inputs, expected_oracle,
    expected_status (pass|fail|review|unknown|not_evaluated),
    oracle_method (formula|constraint|schema|heuristic)

IMPORTANT: Oracle values are computed by independent mathematical formulas,
NOT by calling the application. The application is not its own ground truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
SPEC_DATE = "2026-11-16"

# ── Material families supported by the application ──────────────────────────
MATERIAL_FAMILIES = ["mild_steel", "galvanized_steel", "stainless_steel", "hsla"]
MATERIAL_SUBTYPES = {
    "mild_steel": ["DC01", "DC04", "S235"],
    "galvanized_steel": ["DX51D+Z", "DX53D+ZF"],
    "stainless_steel": ["304", "316L"],
    "hsla": ["S355MC", "DP600"],
}
STACK_COUNTS = ["2T", "3T"]

# ── Profile sizes ─────────────────────────────────────────────────────────────
PROFILE_SIZES = {
    "small": 5,
    "medium": 15,
    "stress": 50,
}


@dataclass
class ScenarioResult:
    scenario_id: str
    profile: str
    seed: int
    description: str
    module: str
    inputs: dict
    expected_oracle: dict
    expected_status: str  # pass|fail|review|unknown|not_evaluated
    oracle_method: str


# ── Independent Oracle Functions ─────────────────────────────────────────────

def oracle_i2rt_energy(resistance_mohm: float, current_ka: float, weld_time_ms: float) -> float:
    """I²Rt formula: energy in Joules. Independent of application logic."""
    R = resistance_mohm * 1e-3   # mΩ → Ω
    I = current_ka * 1e3          # kA → A
    t = weld_time_ms * 1e-3       # ms → s
    return I * I * R * t


def oracle_nugget_min_mm(thickness_mm: float) -> float:
    """AWS D8.9 nugget acceptance criterion: d_min = 4√t (mm)."""
    return 4.0 * math.sqrt(thickness_mm)


def oracle_weld_lobe_safe_count(
    current_min: float, current_max: float, current_step: float,
    time_min: float, time_max: float, time_step: float,
    min_nugget_mm: float, thickness_mm: float,
) -> dict:
    """
    Independent oracle: count grid points where nugget > min_nugget.
    Uses simplified linear model: d = k1*I*sqrt(t) where k1 calibrated for mild steel.
    Not the same as the application model.
    """
    k1 = 0.08  # heuristic calibration constant for mild steel
    total = 0
    safe = 0
    currents = []
    c = current_min
    while c <= current_max + 1e-9:
        currents.append(round(c, 3))
        c += current_step
    times = []
    t = time_min
    while t <= time_max + 1e-9:
        times.append(round(t, 3))
        t += time_step
    total = len(currents) * len(times)
    for I in currents:
        for T in times:
            d = k1 * I * math.sqrt(T)
            if d >= min_nugget_mm:
                safe += 1
    return {"total_points": total, "oracle_safe_count": safe}


def oracle_annual_caps(annual_spots: int, estimated_life: int) -> int:
    """caps_per_year = ceil(annual_spots / dress_interval). Used to verify application output."""
    if estimated_life <= 0:
        return 0
    dress_interval = max(1, estimated_life // 3)
    return math.ceil(annual_spots / dress_interval)


def oracle_anova_sst(values: list[float]) -> float:
    """Total sum of squares: SST = Σ(yi - ȳ)². Independent validation for ANOVA."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values)


def oracle_sn_ratio_nominal(value: float) -> float:
    """S/N ratio for nominal-is-best: -10·log10(σ²/μ²). Requires at least 1 value."""
    if value <= 0:
        return float("-inf")
    return 10.0 * math.log10(value * value)  # single replicate approximation


# ── Scenario Builders ─────────────────────────────────────────────────────────

def build_weld_analysis_scenarios(rng: random.Random, n: int, profile: str, seed: int) -> list[ScenarioResult]:
    scenarios = []
    for i in range(n):
        mf = rng.choice(["mild_steel", "galvanized_steel", "stainless_steel"])
        subtype = rng.choice(MATERIAL_SUBTYPES[mf])
        thickness = round(rng.uniform(0.8, 3.0), 2)
        current = round(rng.uniform(5.0, 12.0), 2)
        weld_t = round(rng.uniform(5.0, 25.0), 1)
        force = round(rng.uniform(2.0, 6.0), 2)
        tip = round(rng.uniform(5.0, 8.0), 1)

        inputs = {
            "material_family": mf,
            "material_subtype": subtype,
            "stack_count": "2T",
            "layers": [
                {"material_family": mf, "material_subtype": subtype,
                 "thickness_mm": thickness, "coated": mf == "galvanized_steel"},
                {"material_family": mf, "material_subtype": subtype,
                 "thickness_mm": thickness, "coated": mf == "galvanized_steel"},
            ],
            "current_ka": current,
            "weld_cycles": weld_t,
            "force_kn": force,
            "tip_diameter_mm": tip,
            "squeeze_cycles": 10.0,
            "hold_cycles": 5.0,
            "cooling_flow_lpm": 2.0,
            "cooling_temp_c": 20.0,
            "dc_current": True,
            "adhesive": False,
            "shunt_risk": False,
        }
        min_nugget = oracle_nugget_min_mm(thickness)
        scenarios.append(ScenarioResult(
            scenario_id=f"WA-{profile.upper()}-{i+1:03d}",
            profile=profile,
            seed=seed,
            description=f"Weld analysis: {mf} {thickness}mm 2T {current}kA {weld_t}cyc",
            module="weld_analysis",
            inputs=inputs,
            expected_oracle={
                "min_nugget_mm_oracle": round(min_nugget, 3),
                "oracle_method": "aws_d8_9_4sqrt_t",
                "score_range": [0, 100],
                "risk_values": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            },
            expected_status="pass",
            oracle_method="formula+schema",
        ))

    # Add invalid scenarios
    scenarios.append(ScenarioResult(
        scenario_id=f"WA-{profile.upper()}-INV001",
        profile=profile, seed=seed,
        description="Invalid: stack_count=4T (unsupported)",
        module="weld_analysis",
        inputs={**scenarios[0].inputs, "stack_count": "4T"},
        expected_oracle={"expected_http_status": 422, "error_contains": "stack_count"},
        expected_status="fail",
        oracle_method="schema_validation",
    ))
    scenarios.append(ScenarioResult(
        scenario_id=f"WA-{profile.upper()}-INV002",
        profile=profile, seed=seed,
        description="Invalid: current_ka=0 (zero current)",
        module="weld_analysis",
        inputs={**scenarios[0].inputs, "current_ka": 0.0},
        expected_oracle={"expected_http_status": 422, "error_contains": "current_ka"},
        expected_status="fail",
        oracle_method="schema_validation",
    ))
    return scenarios


def build_engineering_scenarios(rng: random.Random, n: int, profile: str, seed: int) -> list[ScenarioResult]:
    scenarios = []

    # Weld Lobe
    for i in range(n):
        t = round(rng.uniform(0.8, 2.5), 2)
        min_nug = round(oracle_nugget_min_mm(t), 3)
        c_min, c_max, c_step = 5.0, 12.0, 0.5
        t_min, t_max, t_step = 5.0, 20.0, 1.0
        grid = oracle_weld_lobe_safe_count(c_min, c_max, c_step, t_min, t_max, t_step, min_nug, t)
        scenarios.append(ScenarioResult(
            scenario_id=f"EL-LOBE-{profile.upper()}-{i+1:03d}",
            profile=profile, seed=seed,
            description=f"Weld lobe: mild_steel {t}mm min_nugget={min_nug}mm",
            module="engineering_weld_lobe",
            inputs={
                "material_family": "mild_steel",
                "thickness_mm": t,
                "force_kn": round(rng.uniform(2.0, 5.0), 1),
                "min_nugget_mm": min_nug,
                "current_min_ka": c_min, "current_max_ka": c_max, "current_step_ka": c_step,
                "time_min_cycles": t_min, "time_max_cycles": t_max, "time_step_cycles": t_step,
            },
            expected_oracle=grid,
            expected_status="pass",
            oracle_method="grid_enumeration",
        ))

    # Electrode Life
    for i in range(min(n, 5)):
        cur = round(rng.uniform(6.0, 10.0), 1)
        ann = rng.randint(10000, 100000)
        scenarios.append(ScenarioResult(
            scenario_id=f"EL-LIFE-{profile.upper()}-{i+1:03d}",
            profile=profile, seed=seed,
            description=f"Electrode life: mild_steel coated=False {cur}kA {ann} spots/yr",
            module="engineering_electrode_life",
            inputs={
                "material_family": "mild_steel",
                "coated": False,
                "tip_diameter_mm": 6.0,
                "cooling_flow_lpm": 2.0,
                "cooling_temp_c": 20.0,
                "current_ka": cur,
                "annual_spot_count": ann,
            },
            expected_oracle={"life_spots_range": [500, 50000], "caps_per_year_min": 1},
            expected_status="pass",
            oracle_method="heuristic_range",
        ))

    # Dynamic Resistance — 3 scenarios
    for quality, samples in [
        ("Normal", [80.0, 100.0, 120.0, 115.0, 105.0, 95.0, 90.0]),
        ("High", [50.0, 80.0, 180.0, 170.0, 160.0, 150.0, 140.0]),
        ("Fault", [200.0, 210.0, 220.0, 230.0, 240.0, 250.0, 260.0]),
    ]:
        scenarios.append(ScenarioResult(
            scenario_id=f"EL-DR-{quality.upper()}-001",
            profile=profile, seed=seed,
            description=f"Dynamic resistance: {quality} quality pattern",
            module="engineering_dynamic_resistance",
            inputs={"samples_micro_ohm": samples},
            expected_oracle={
                "peak_range": [min(samples), max(samples) * 1.1],
                "quality_possible_values": ["Normal", "High", "Low", "Fault", "Unknown"],
            },
            expected_status="pass",
            oracle_method="range_check",
        ))

    # Pulse Strategy
    for mf, coated, expected_strategy in [
        ("mild_steel", False, "single"),
        ("galvanized_steel", True, "preheat"),
        ("stainless_steel", False, "single"),
    ]:
        scenarios.append(ScenarioResult(
            scenario_id=f"EL-PS-{mf.upper()[:5]}-001",
            profile=profile, seed=seed,
            description=f"Pulse strategy: {mf} coated={coated}",
            module="engineering_pulse_strategy",
            inputs={
                "material_family": mf,
                "coated": coated,
                "thickness_ratio": 1.0,
                "stack_count": "2T",
                "adhesive": False,
                "current_ka": 8.0,
                "weld_cycles": 12.0,
            },
            expected_oracle={"pulse_count_range": [1, 4]},
            expected_status="pass",
            oracle_method="heuristic_range",
        ))

    return scenarios


def build_failure_probability_scenarios(rng: random.Random, n: int, profile: str, seed: int) -> list[ScenarioResult]:
    scenarios = []
    for i in range(n):
        t = round(rng.uniform(0.8, 2.5), 2)
        cur = round(rng.uniform(6.0, 11.0), 1)
        min_nug = round(oracle_nugget_min_mm(t), 3)
        pred_nug = round(min_nug * rng.uniform(0.9, 1.3), 3)

        scenarios.append(ScenarioResult(
            scenario_id=f"FP-{profile.upper()}-{i+1:03d}",
            profile=profile, seed=seed,
            description=f"Failure probability: mild_steel {t}mm {cur}kA pred={pred_nug}mm",
            module="failure_probability",
            inputs={
                "material_family": "mild_steel",
                "stack_count": "2T",
                "coated": False,
                "adhesive": False,
                "shunt_risk": False,
                "thicknesses_mm": [t, t],
                "current_ka": cur,
                "weld_cycles": 12.0,
                "force_kn": 3.5,
                "tip_diameter_mm": 6.0,
                "squeeze_cycles": 10.0,
                "hold_cycles": 5.0,
                "cooling_flow_lpm": 2.0,
                "cooling_temp_c": 20.0,
                "recommended_current_min_ka": max(1.0, cur - 1.5),
                "recommended_current_max_ka": cur + 1.5,
                "recommended_time_min_cycles": 8.0,
                "recommended_time_max_cycles": 20.0,
                "recommended_force_min_kn": 2.0,
                "recommended_force_max_kn": 6.0,
                "recommended_tip_min_mm": 5.0,
                "recommended_tip_max_mm": 8.0,
                "predicted_nugget_mm": pred_nug,
                "minimum_nugget_mm": min_nug,
            },
            expected_oracle={
                "failure_mode_count": 10,
                "probabilities_sum_max": 100.0,
                "top_failure_in_response": True,
            },
            expected_status="pass",
            oracle_method="schema+count",
        ))
    return scenarios


def build_statistical_scenarios(rng: random.Random, n: int, profile: str, seed: int) -> list[ScenarioResult]:
    scenarios = []

    # L9 Taguchi design
    factors_l9 = [
        {"name": "Current", "unit": "kA", "levels": [7.0, 9.0, 11.0]},
        {"name": "WeldTime", "unit": "cycles", "levels": [8.0, 12.0, 16.0]},
        {"name": "Force", "unit": "kN", "levels": [2.5, 3.5, 4.5]},
    ]
    scenarios.append(ScenarioResult(
        scenario_id=f"SA-L9-DESIGN-001",
        profile=profile, seed=seed,
        description="Taguchi L9 design: 3 factors × 3 levels",
        module="statistical_taguchi_design",
        inputs={"array_type": "L9", "factors": factors_l9},
        expected_oracle={"runs": 9, "n_factors": 3, "levels_per_factor": 3},
        expected_status="pass",
        oracle_method="combinatoric",
    ))

    # L9 analyze: generate response values
    l9_responses = [5.1, 5.3, 4.9, 5.4, 5.6, 5.0, 5.7, 5.9, 5.2]
    sst = oracle_anova_sst(l9_responses)
    scenarios.append(ScenarioResult(
        scenario_id=f"SA-L9-ANALYZE-001",
        profile=profile, seed=seed,
        description="Taguchi L9 analyze: nugget diameter responses",
        module="statistical_taguchi_analyze",
        inputs={
            "array_type": "L9",
            "factors": factors_l9,
            "results": [
                {"run_number": i + 1, "response_value": v}
                for i, v in enumerate(l9_responses)
            ],
            "optimize": "maximize",
            "response_unit": "mm",
        },
        expected_oracle={
            "grand_mean_range": [4.5, 6.5],
            "oracle_sst": round(sst, 6),
            "optimal_within_factor_ranges": True,
        },
        expected_status="pass",
        oracle_method="formula+range",
    ))

    # ANOVA
    groups = [[5.1, 5.3, 4.9], [5.4, 5.6, 5.0], [5.7, 5.9, 5.2]]
    all_vals = [v for g in groups for v in g]
    grand_mean = sum(all_vals) / len(all_vals)
    sst_total = oracle_anova_sst(all_vals)
    scenarios.append(ScenarioResult(
        scenario_id=f"SA-ANOVA-001",
        profile=profile, seed=seed,
        description="One-way ANOVA: 3 groups of nugget diameters",
        module="statistical_anova",
        inputs={
            "groups": [
                {"name": f"Level{i+1}", "values": g}
                for i, g in enumerate(groups)
            ],
            "significance_level": 0.05,
        },
        expected_oracle={
            "oracle_grand_mean": round(grand_mean, 4),
            "oracle_sst": round(sst_total, 6),
            "k": 3,
            "n_total": 9,
        },
        expected_status="pass",
        oracle_method="formula",
    ))

    return scenarios


def build_energy_scenarios(rng: random.Random, n: int, profile: str, seed: int) -> list[ScenarioResult]:
    scenarios = []
    for i in range(n):
        R = round(rng.uniform(80.0, 150.0), 1)   # mΩ
        I = round(rng.uniform(5.0, 12.0), 2)       # kA
        t = round(rng.uniform(80.0, 300.0), 1)     # ms
        energy_j = oracle_i2rt_energy(R, I, t)

        scenarios.append(ScenarioResult(
            scenario_id=f"EN-EST-{profile.upper()}-{i+1:03d}",
            profile=profile, seed=seed,
            description=f"Energy estimate: R={R}mΩ I={I}kA t={t}ms oracle={energy_j:.2f}J",
            module="energy_estimate",
            inputs={
                "resistance_mohm": R,
                "current_ka": I,
                "weld_time_ms": t,
                "efficiency_pct": 100.0,
            },
            expected_oracle={
                "oracle_energy_j": round(energy_j, 4),
                "tolerance_pct": 1.0,
            },
            expected_status="pass",
            oracle_method="i2rt_formula",
        ))

    # Invalid
    scenarios.append(ScenarioResult(
        scenario_id=f"EN-EST-INV001",
        profile=profile, seed=seed,
        description="Invalid: resistance_mohm=0",
        module="energy_estimate",
        inputs={"resistance_mohm": 0.0, "current_ka": 8.0, "weld_time_ms": 150.0, "efficiency_pct": 100.0},
        expected_oracle={"expected_http_status": 422},
        expected_status="fail",
        oracle_method="schema_validation",
    ))
    return scenarios


def build_project_scenarios(rng: random.Random, n: int, profile: str, seed: int) -> list[ScenarioResult]:
    scenarios = []
    for i in range(n):
        name = f"SynthProject_{seed}_{i+1:03d}"
        scenarios.append(ScenarioResult(
            scenario_id=f"PROJ-{profile.upper()}-{i+1:03d}",
            profile=profile, seed=seed,
            description=f"Project CRUD: create '{name}'",
            module="projects",
            inputs={"name": name, "description": f"Synthetic test project {i+1}"},
            expected_oracle={
                "id_present": True,
                "name": name,
                "owner_match": True,
            },
            expected_status="pass",
            oracle_method="schema+invariant",
        ))
    return scenarios


# ── Main Generator ────────────────────────────────────────────────────────────

def generate(seed: int, profile: str, out_dir: Path) -> dict:
    rng = random.Random(seed)
    n = PROFILE_SIZES[profile]

    all_scenarios: dict[str, list] = {
        "weld_analysis": build_weld_analysis_scenarios(rng, n, profile, seed),
        "failure_probability": build_failure_probability_scenarios(rng, n, profile, seed),
        "engineering": build_engineering_scenarios(rng, n, profile, seed),
        "statistical": build_statistical_scenarios(rng, n, profile, seed),
        "energy": build_energy_scenarios(rng, n, profile, seed),
        "projects": build_project_scenarios(rng, min(n, 3), profile, seed),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": VERSION,
        "spec_date": SPEC_DATE,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "seed": seed,
        "profile": profile,
        "files": {},
        "total_scenarios": 0,
    }

    for module_key, scenarios in all_scenarios.items():
        file_path = out_dir / f"{module_key}.json"
        rows = [
            {
                "scenario_id": s.scenario_id,
                "profile": s.profile,
                "seed": s.seed,
                "description": s.description,
                "module": s.module,
                "inputs": s.inputs,
                "expected_oracle": s.expected_oracle,
                "expected_status": s.expected_status,
                "oracle_method": s.oracle_method,
            }
            for s in scenarios
        ]
        content = json.dumps(rows, indent=2, ensure_ascii=False)
        file_path.write_text(content, encoding="utf-8")
        checksum = hashlib.sha256(content.encode()).hexdigest()
        manifest["files"][str(file_path.name)] = {
            "count": len(rows),
            "sha256": checksum,
        }
        manifest["total_scenarios"] += len(rows)
        print(f"  wrote {file_path.name}: {len(rows)} scenarios")

    manifest_path = out_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  wrote MANIFEST.json — total {manifest['total_scenarios']} scenarios")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="SpotWeldPro AI Synthetic Dataset Factory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--profile", choices=["small", "medium", "stress"], default="small")
    parser.add_argument("--out", type=str, default="./datasets", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out)
    print(f"Generating {args.profile} profile, seed={args.seed} -> {out_dir}")
    manifest = generate(args.seed, args.profile, out_dir)
    print(f"\nDone. {manifest['total_scenarios']} scenarios generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
