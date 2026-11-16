"""
SpotWeldPro AI — Synthetic Weld Surface PNG Generator
Version: 1.0.0

Generates controlled geometric PNG images for vision module testing.
Uses ONLY Python stdlib (struct, zlib, math, random) — no external dependencies.

DISCLAIMER: These images represent synthetic geometric patterns only.
They are NOT metallographic evidence, NOT industrial inspection data,
NOT destructive-test cross-sections, and MUST NOT be used to clear
E1-E4 annotation quality gates or claim physical validation.

Each PNG contains a tEXt metadata chunk:
    SYNTHETIC_TEST_DATA: SpotWeldPro AI Synthetic Vision Test
    Not real weld data. Not validated for industrial inspection.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import zlib
from pathlib import Path
from typing import NamedTuple


VERSION = "1.0.0"
SPEC_DATE = "2026-11-16"
IMAGE_SIZE = 200  # pixels, square


class BoundingBox(NamedTuple):
    x: int
    y: int
    w: int
    h: int


class ImageMeta(NamedTuple):
    filename: str
    scenario: str
    description: str
    width: int
    height: int
    bbox: BoundingBox | None
    expected_defect: str
    sha256: str


# ── PNG stdlib encoder ───────────────────────────────────────────────────────

def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", _crc32(chunk_type + data))
    return length + chunk_type + data + crc


def _make_png(pixels: list[list[tuple[int, int, int]]], text_meta: dict[str, str] = {}) -> bytes:
    h = len(pixels)
    w = len(pixels[0]) if h > 0 else 0

    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)

    # tEXt chunks
    text_chunks = b""
    for key, val in text_meta.items():
        kv = key.encode("latin-1") + b"\x00" + val.encode("latin-1")
        text_chunks += _png_chunk(b"tEXt", kv)

    # IDAT
    raw = b""
    for row in pixels:
        raw += b"\x00"  # filter type None
        for r, g, b in row:
            raw += bytes([r, g, b])
    compressed = zlib.compress(raw, 9)
    idat = _png_chunk(b"IDAT", compressed)

    # IEND
    iend = _png_chunk(b"IEND", b"")

    return sig + ihdr + text_chunks + idat + iend


# ── Canvas helpers ──────────────────────────────────────────────────────────

def _blank(w: int, h: int, bg: tuple[int, int, int] = (220, 215, 210)) -> list[list[tuple[int, int, int]]]:
    return [[bg for _ in range(w)] for _ in range(h)]


def _set_pixel(px, x: int, y: int, color: tuple[int, int, int], w: int, h: int):
    if 0 <= x < w and 0 <= y < h:
        px[y][x] = color


def _draw_circle(px, cx: int, cy: int, r: int, color: tuple[int, int, int], w: int, h: int, fill=True):
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            dist = math.sqrt(dx * dx + dy * dy)
            if fill and dist <= r:
                _set_pixel(px, cx + dx, cy + dy, color, w, h)
            elif not fill and abs(dist - r) <= 1.0:
                _set_pixel(px, cx + dx, cy + dy, color, w, h)


def _draw_ellipse(px, cx: int, cy: int, rx: int, ry: int, color: tuple[int, int, int], w: int, h: int, fill=True):
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            d = (dx / rx) ** 2 + (dy / ry) ** 2
            if fill and d <= 1.0:
                _set_pixel(px, cx + dx, cy + dy, color, w, h)
            elif not fill and abs(d - 1.0) <= 0.08:
                _set_pixel(px, cx + dx, cy + dy, color, w, h)


def _draw_line(px, x0, y0, x1, y1, color, w, h, thickness=2):
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        for t in range(-thickness // 2, thickness // 2 + 1):
            _set_pixel(px, x + t, y, color, w, h)
            _set_pixel(px, x, y + t, color, w, h)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy; x += sx
        if e2 < dx:
            err += dx; y += sy


def _add_noise(px, rng: random.Random, h: int, w: int, strength: int = 15):
    for y in range(h):
        for x in range(w):
            r, g, b = px[y][x]
            d = rng.randint(-strength, strength)
            px[y][x] = (max(0, min(255, r + d)),
                        max(0, min(255, g + d)),
                        max(0, min(255, b + d)))


def _add_watermark(px, h: int, w: int):
    text_color = (180, 60, 60)
    # Simple X pattern at corners as watermark indicator
    for i in range(0, 10):
        _set_pixel(px, i, i, text_color, w, h)
        _set_pixel(px, w - 1 - i, i, text_color, w, h)
        _set_pixel(px, i, h - 1 - i, text_color, w, h)
        _set_pixel(px, w - 1 - i, h - 1 - i, text_color, w, h)


# ── Scenario Generators ─────────────────────────────────────────────────────

SCENARIOS: list[tuple[str, str, callable]] = []


def scenario(name: str, description: str):
    def deco(fn):
        SCENARIOS.append((name, description, fn))
        return fn
    return deco


@scenario("normal_circular", "Normal circular spot weld impression")
def gen_normal_circular(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    cx, cy = W // 2, H // 2
    r = int(W * 0.25)
    # Outer ring (heat affected zone)
    _draw_circle(px, cx, cy, int(r * 1.4), (170, 155, 140), W, H, fill=True)
    # Weld nugget impression (darker)
    _draw_circle(px, cx, cy, r, (100, 90, 80), W, H, fill=True)
    # Center highlight
    _draw_circle(px, cx, cy, int(r * 0.3), (140, 130, 120), W, H, fill=True)
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - r, cy - r, 2 * r, 2 * r)
    return px, bbox, "none"


@scenario("elliptical_indentation", "Elliptical weld indentation (asymmetric force)")
def gen_elliptical(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    cx, cy = W // 2, H // 2
    rx, ry = int(W * 0.30), int(H * 0.18)
    _draw_ellipse(px, cx, cy, int(rx * 1.3), int(ry * 1.3), (175, 160, 145), W, H)
    _draw_ellipse(px, cx, cy, rx, ry, (95, 85, 75), W, H)
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - rx, cy - ry, 2 * rx, 2 * ry)
    return px, bbox, "elliptical_indentation"


@scenario("misalignment", "Electrode misalignment — off-center impression")
def gen_misalignment(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    offset_x = int(W * 0.15)
    cx, cy = W // 2 + offset_x, H // 2
    r = int(W * 0.22)
    _draw_circle(px, cx, cy, int(r * 1.3), (175, 160, 145), W, H)
    _draw_circle(px, cx, cy, r, (100, 90, 80), W, H)
    # Mark center cross
    _draw_line(px, W // 2, 0, W // 2, H - 1, (220, 50, 50), W, H, 1)
    _draw_line(px, 0, H // 2, W - 1, H // 2, (220, 50, 50), W, H, 1)
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - r, cy - r, 2 * r, 2 * r)
    return px, bbox, "misalignment"


@scenario("surface_cracks", "Artificial surface crack pattern")
def gen_surface_cracks(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (190, 185, 180))
    cx, cy = W // 2, H // 2
    r = int(W * 0.25)
    _draw_circle(px, cx, cy, int(r * 1.3), (165, 150, 135), W, H)
    _draw_circle(px, cx, cy, r, (100, 90, 80), W, H)
    # Crack lines radiating from edge
    crack_color = (50, 40, 30)
    for angle_deg in [15, 75, 150, 210, 300]:
        angle = math.radians(angle_deg)
        x1 = int(cx + r * math.cos(angle))
        y1 = int(cy + r * math.sin(angle))
        x2 = int(cx + (r + 25) * math.cos(angle + 0.2))
        y2 = int(cy + (r + 25) * math.sin(angle + 0.2))
        _draw_line(px, x1, y1, x2, y2, crack_color, W, H, 1)
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - r - 25, cy - r - 25, 2 * r + 50, 2 * r + 50)
    return px, bbox, "surface_crack"


@scenario("spatter", "Artificial spatter particles around weld")
def gen_spatter(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    cx, cy = W // 2, H // 2
    r = int(W * 0.22)
    _draw_circle(px, cx, cy, int(r * 1.2), (170, 155, 140), W, H)
    _draw_circle(px, cx, cy, r, (105, 95, 85), W, H)
    # Spatter dots
    spatter_color = (60, 50, 40)
    for _ in range(12):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(r * 1.3, r * 2.0)
        sx = int(cx + dist * math.cos(angle))
        sy = int(cy + dist * math.sin(angle))
        sr = rng.randint(2, 5)
        _draw_circle(px, sx, sy, sr, spatter_color, W, H)
    _add_watermark(px, H, W)
    bbox = BoundingBox(max(0, cx - int(r * 2)), max(0, cy - int(r * 2)),
                       min(W, int(r * 4)), min(H, int(r * 4)))
    return px, bbox, "spatter"


@scenario("discoloration", "Surface discoloration / heat tint ring")
def gen_discoloration(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    cx, cy = W // 2, H // 2
    r_base = int(W * 0.20)
    # Gradient heat zones (blue → straw → grey)
    _draw_circle(px, cx, cy, int(r_base * 2.0), (160, 150, 110), W, H)  # straw
    _draw_circle(px, cx, cy, int(r_base * 1.5), (130, 140, 160), W, H)  # blue
    _draw_circle(px, cx, cy, r_base, (100, 90, 80), W, H)
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - int(r_base * 2), cy - int(r_base * 2),
                       int(r_base * 4), int(r_base * 4))
    return px, bbox, "discoloration"


@scenario("missing_weld", "No visible weld impression — missing weld")
def gen_missing_weld(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (205, 200, 198))
    # Slight electrode contact ring only, no nugget
    cx, cy = W // 2, H // 2
    r = int(W * 0.20)
    _draw_circle(px, cx, cy, r, (195, 192, 188), W, H, fill=False)
    _add_noise(px, rng, H, W, strength=5)
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - r, cy - r, 2 * r, 2 * r)
    return px, bbox, "missing_weld"


@scenario("multi_spot_pattern", "Three adjacent spot welds in a line")
def gen_multi_spot(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    r = int(W * 0.13)
    centers = [(W // 4, H // 2), (W // 2, H // 2), (3 * W // 4, H // 2)]
    bboxes = []
    for cx, cy in centers:
        _draw_circle(px, cx, cy, int(r * 1.3), (175, 160, 145), W, H)
        _draw_circle(px, cx, cy, r, (105, 95, 85), W, H)
        bboxes.append(BoundingBox(cx - r, cy - r, 2 * r, 2 * r))
    _add_watermark(px, H, W)
    # Return combined bbox
    bbox = BoundingBox(bboxes[0].x, min(b.y for b in bboxes),
                       bboxes[-1].x + bboxes[-1].w - bboxes[0].x,
                       max(b.h for b in bboxes))
    return px, bbox, "none"


@scenario("blur_variation", "Simulated camera blur / defocus")
def gen_blur(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    cx, cy = W // 2, H // 2
    r = int(W * 0.25)
    _draw_circle(px, cx, cy, int(r * 1.3), (175, 160, 145), W, H)
    _draw_circle(px, cx, cy, r, (100, 90, 80), W, H)
    # Simulate blur by averaging each pixel with neighbors (simple box filter)
    px2 = [row[:] for row in px]
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            neighbors = [px[ny][nx] for ny in range(y-1, y+2) for nx in range(x-1, x+2)]
            avg = tuple(sum(c[i] for c in neighbors) // 9 for i in range(3))
            px2[y][x] = avg  # type: ignore
    _add_watermark(px2, H, W)
    bbox = BoundingBox(cx - r, cy - r, 2 * r, 2 * r)
    return px2, bbox, "blur"


@scenario("illumination_variation", "Uneven illumination gradient")
def gen_illumination(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    cx, cy = W // 2, H // 2
    r = int(W * 0.25)
    _draw_circle(px, cx, cy, int(r * 1.3), (170, 155, 140), W, H)
    _draw_circle(px, cx, cy, r, (100, 90, 80), W, H)
    # Apply horizontal gradient
    for y in range(H):
        for x in range(W):
            grad = int(60 * x / W)
            rv, gv, bv = px[y][x]
            px[y][x] = (min(255, rv + grad), min(255, gv + grad), min(255, bv + grad))
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - r, cy - r, 2 * r, 2 * r)
    return px, bbox, "illumination_variation"


@scenario("noise_heavy", "Heavy sensor noise overlay")
def gen_noise(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    cx, cy = W // 2, H // 2
    r = int(W * 0.25)
    _draw_circle(px, cx, cy, int(r * 1.3), (170, 155, 140), W, H)
    _draw_circle(px, cx, cy, r, (100, 90, 80), W, H)
    _add_noise(px, rng, H, W, strength=40)
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - r, cy - r, 2 * r, 2 * r)
    return px, bbox, "noise"


@scenario("rotation_45deg", "Rotated 45-degree view (perspective change simulation)")
def gen_rotated(rng: random.Random, W: int, H: int):
    px = _blank(W, H, (200, 195, 190))
    cx, cy = W // 2, H // 2
    # Draw diamond (rotated square) to simulate rotation artifact
    r = int(W * 0.22)
    for t in range(360):
        angle = math.radians(t)
        x = cx + int(r * math.cos(angle))
        y = cy + int(r * 0.6 * math.sin(angle))
        _set_pixel(px, x, y, (100, 90, 80), W, H)
    _draw_circle(px, cx, cy, int(r * 0.5), (100, 90, 80), W, H)
    _add_watermark(px, H, W)
    bbox = BoundingBox(cx - r, cy - int(r * 0.6), 2 * r, int(r * 1.2))
    return px, bbox, "perspective_distortion"


# ── Mask generator ─────────────────────────────────────────────────────────

def generate_mask(bbox: BoundingBox | None, W: int, H: int) -> list[list[int]]:
    mask = [[0] * W for _ in range(H)]
    if bbox is None:
        return mask
    for y in range(bbox.y, min(H, bbox.y + bbox.h)):
        for x in range(bbox.x, min(W, bbox.x + bbox.w)):
            mask[y][x] = 1
    return mask


# ── Main ─────────────────────────────────────────────────────────────────────

def generate_all(out_dir: Path, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = []

    text_meta = {
        "SYNTHETIC_TEST_DATA": "SpotWeldPro AI Synthetic Vision Test",
        "Warning": "Not real weld data. Not validated for industrial inspection.",
        "Generator": f"generate_images.py v{VERSION}",
        "Seed": str(seed),
    }

    for name, description, fn in SCENARIOS:
        fn_rng = random.Random(seed + hash(name) % 1000)
        pixels, bbox, expected_defect = fn(fn_rng, IMAGE_SIZE, IMAGE_SIZE)
        png_bytes = _make_png(pixels, text_meta)
        sha = hashlib.sha256(png_bytes).hexdigest()

        fname = f"synth_{name}.png"
        (out_dir / fname).write_bytes(png_bytes)

        # Write pixel mask JSON
        mask = generate_mask(bbox, IMAGE_SIZE, IMAGE_SIZE)
        mask_path = out_dir / f"synth_{name}_mask.json"
        mask_path.write_text(json.dumps({
            "image": fname,
            "width": IMAGE_SIZE,
            "height": IMAGE_SIZE,
            "bbox": bbox._asdict() if bbox else None,
            "mask_sum": sum(sum(row) for row in mask),
        }), encoding="utf-8")

        metadata.append({
            "filename": fname,
            "scenario": name,
            "description": description,
            "width": IMAGE_SIZE,
            "height": IMAGE_SIZE,
            "bbox": bbox._asdict() if bbox else None,
            "expected_defect": expected_defect,
            "sha256": sha,
            "size_bytes": len(png_bytes),
        })
        print(f"  {fname}: {len(png_bytes)} bytes sha256={sha[:12]}...")

    manifest = {
        "version": VERSION,
        "spec_date": SPEC_DATE,
        "seed": seed,
        "total_images": len(metadata),
        "image_size_px": IMAGE_SIZE,
        "disclaimer": (
            "SYNTHETIC TEST DATA ONLY. These images are generated geometric patterns. "
            "They are NOT real weld images, NOT metallographic cross-sections, "
            "and MUST NOT be used as ground truth for annotation quality gates."
        ),
        "images": metadata,
    }
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n  MANIFEST.json: {len(metadata)} images")
    return metadata


if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="./images")
    args = parser.parse_args()
    print(f"Generating synthetic images -> {args.out}")
    generate_all(Path(args.out), args.seed)
    print("Done.")
    sys.exit(0)
