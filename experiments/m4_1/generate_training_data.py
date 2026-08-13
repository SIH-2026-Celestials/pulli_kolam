"""M4.1 Phase 3: synthetic training data for the learned dot detector.

REUSES generate_synthetic_photos.py's rendering code UNCHANGED
(render_clean, lattice_to_pixel_transform) -- that module is NOT modified,
matching M4.1's "extend or reuse it, do not replace it" instruction, and
keeping the existing classical-baseline numbers (session 10/11,
experiments/m4_1/classical_baseline.py) reproducible and untouched.

What's NEW here is degrade_v2(): a richer degradation pipeline than the
original degrade() (which was tuned to look like "a normal phone photo").
degrade_v2 additionally varies:
  - scale (zoom, via getRotationMatrix2D's own scale param)
  - brightness/contrast, INCLUDING a deliberate low-light regime
  - background tint (simulates photographing on a colored floor)
  - stronger/more variable uneven illumination, noise, blur, JPEG quality
  - dot size / line thickness (monkeypatches gsp.DOT_RADIUS_FRAC etc. per
    image the same way generate_synthetic_photos_heldout.py already
    monkeypatches gsp.OUT_DIR -- an existing convention in this repo, not
    a new one)

The brightness/contrast ranges are NOT guessed -- they are calibrated
against the two real, measured low-contrast failure cases this project
has actually observed (PROJECT_STATE.md, M4.0 report Section 5):
  kolam2_tshrinivasan.jpg:              gray mean 62.5, std 21.6
  kolam_naduveetu_meenakshisundaram.jpg: gray mean 72.6, std 63.4
A fraction of generated images are deliberately pushed toward these
statistics; the rest span an easy-to-hard range so the dataset reflects
a genuine difficulty distribution, not an all-hard adversarial set
(mirroring the real-photo corpus's own "do not deliberately select only
difficult images" rule from M4.0 Phase 1).

SPLIT METHODOLOGY (documented, not just implemented):
  - Disjoint at the PATTERN level (kolam19/kolam29 pattern numbers never
    repeat across train/val/test), so no model can memorize a specific
    pattern's dot layout and "cheat" on held-out evaluation.
  - Also disjoint from every pattern number already used by
    generate_synthetic_photos.py (tuned set) and
    generate_synthetic_photos_heldout.py (classical held-out set):
      tuned:   kolam19 {1,2,3,27,50}      kolam29 {1,2}
      heldout: kolam19 {75,100,150,250,350} kolam29 {20,50,80}
    so M4.1's own test split stays meaningful as an independent check,
    not just a relabeling of images the classical detector was already
    tuned/validated against.
  - Disjoint seed ranges per split (train 20000+, val 30000+, test
    40000+) so no two splits share identical degradation instances even
    if they somehow shared a pattern (they don't).
  - Fully reproducible: every image's exact seed is recorded in
    split_manifest.json alongside its pattern source.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import generate_synthetic_photos as gsp  # noqa: E402
from engine import graph_io  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CSV19 = "kolam_data/Kolam CSV files/Kolam CSV files/kolam19.csv"
CSV29 = "kolam_data/Kolam CSV files/Kolam CSV files/kolam29.csv"

# Pattern numbers already used elsewhere (see module docstring) -- never
# reused here, at any split.
_USED_ELSEWHERE = {
    (CSV19, n) for n in [1, 2, 3, 27, 50, 75, 100, 150, 250, 350]
} | {(CSV29, n) for n in [1, 2, 20, 50, 80]}

SPLITS = {
    "train": {
        "patterns": [(CSV19, n) for n in [10, 15, 20, 30, 40, 60, 70, 90, 120, 160, 180, 200]]
        + [(CSV29, n) for n in [5, 10, 15, 25, 30, 35]],
        "variants_per_pattern": 6,
        "seed_base": 20000,
    },
    "val": {
        "patterns": [(CSV19, n) for n in [220, 240, 260]] + [(CSV29, n) for n in [40, 45]],
        "variants_per_pattern": 4,
        "seed_base": 30000,
    },
    "test": {
        "patterns": [(CSV19, n) for n in [280, 300, 320, 340, 360, 380]] + [(CSV29, n) for n in [55, 60, 65]],
        "variants_per_pattern": 4,
        "seed_base": 40000,
    },
}

# Sanity: no pattern reused across splits or against tuned/heldout sets.
_all_listed = [p for s in SPLITS.values() for p in s["patterns"]]
assert len(_all_listed) == len(set(_all_listed)), "pattern reused across splits"
assert not (set(_all_listed) & _USED_ELSEWHERE), "pattern collides with tuned/heldout set"

# Background tints roughly spanning real floor colors observed in
# real_photos/ (concrete gray, reddish dirt/tile, tan stone) -- not
# exhaustive, just enough variety that the model can't assume a pure
# off-white background.
BACKGROUND_TINTS = [
    (247, 245, 240),  # original off-white paper
    (150, 150, 155),  # gray concrete
    (120, 105, 95),   # reddish dirt/tile (kolam_naduveetu-like)
    (170, 160, 140),  # tan stone
    (100, 95, 90),    # dark worn concrete
]


def degrade_v2(img: np.ndarray, dot_pixels: dict, rng: random.Random) -> tuple[np.ndarray, dict, dict]:
    """Richer degradation than gsp.degrade(). Returns (image, new_dot_pixels,
    degradation_record) -- the record is saved to ground truth JSON so every
    image's exact degradation parameters are auditable, not hidden."""
    h, w = img.shape[:2]
    pts = np.array(list(dot_pixels.values()), dtype=np.float32).reshape(-1, 1, 2)
    keys = list(dot_pixels.keys())

    severity = rng.random()  # 0 = easy, 1 = hard; drives several axes together
    record = {"severity": severity}

    # 1. rotation + scale (wider range than the original ±8deg / scale=1.0)
    angle = rng.uniform(-15, 15)
    scale = rng.uniform(0.85, 1.15)
    M_rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    bg = BACKGROUND_TINTS[rng.randrange(len(BACKGROUND_TINTS))]
    img = cv2.warpAffine(img, M_rot, (w, h), borderValue=bg)
    pts = cv2.transform(pts, M_rot)
    record.update(rotation_deg=angle, scale=scale, background_tint=bg)

    # 2. mild perspective warp
    jitter = (0.02 + 0.03 * severity) * w
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)],
                       [w + rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)],
                       [w + rng.uniform(-jitter, jitter), h + rng.uniform(-jitter, jitter)],
                       [rng.uniform(-jitter, jitter), h + rng.uniform(-jitter, jitter)]])
    M_persp = cv2.getPerspectiveTransform(src, dst)
    img = cv2.warpPerspective(img, M_persp, (w, h), borderValue=bg)
    pts = cv2.perspectiveTransform(pts, M_persp)

    # 3. uneven illumination (stronger than the original)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (0.8 * math.hypot(w, h))
    vignette_strength = 0.2 + 0.35 * severity
    light = np.clip(1.0 - vignette_strength * dist, 0.35, 1.05)[..., None]
    img = np.clip(img.astype(np.float32) * light, 0, 255).astype(np.uint8)

    # 4. brightness/contrast -- calibrated toward the two measured real
    # low-contrast failures for a meaningful fraction of images (see
    # module docstring). contrast<1 + negative brightness together push
    # gray-mean/std toward the ~62-73 mean / ~20-60 std range observed on
    # kolam2_tshrinivasan.jpg / kolam_naduveetu_meenakshisundaram.jpg.
    contrast = 1.05 - 0.55 * severity  # 1.05 (easy) -> 0.50 (hard)
    brightness = 5 - 90 * severity  # +5 (easy) -> -85 (hard, underexposed)
    img = np.clip(img.astype(np.float32) * contrast + brightness, 0, 255).astype(np.uint8)
    record.update(contrast=contrast, brightness=brightness, vignette_strength=vignette_strength)

    # 5. blur (variable)
    blur_sigma = 0.4 + 1.6 * severity
    k = max(3, int(round(blur_sigma * 3)) | 1)  # odd kernel size
    img = cv2.GaussianBlur(img, (k, k), blur_sigma)

    # 6. Gaussian noise (variable, stronger than the original fixed std=6)
    noise_std = 4 + 22 * severity
    noise = np.random.normal(0, noise_std, img.shape).astype(np.float32)
    img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    record.update(blur_sigma=blur_sigma, noise_std=noise_std)

    # 7. real JPEG round-trip at variable quality (actual codec artifacts,
    # not just a final save-time setting)
    jpeg_quality = int(round(90 - 55 * severity))
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if ok:
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    record["jpeg_quality"] = jpeg_quality

    new_dot_pixels = {k: (float(p[0][0]), float(p[0][1])) for k, p in zip(keys, pts)}
    record["measured_gray_mean"] = float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean())
    record["measured_gray_std"] = float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std())
    return img, new_dot_pixels, record


def generate_one(csv_path: str, kolam_number: int, seed: int, out_dir: str, out_stem: str) -> dict:
    G = graph_io.load_kolam(csv_path, kolam_number)
    dots = graph_io.dots_set(G)
    scale, offset_x, offset_y = gsp.lattice_to_pixel_transform(dots)

    rng = random.Random(seed)
    # vary dot size / line thickness per image -- monkeypatch gsp's module
    # constants the same way generate_synthetic_photos_heldout.py already
    # monkeypatches gsp.OUT_DIR (an existing convention, not a new one).
    orig_dot_frac, orig_line_frac = gsp.DOT_RADIUS_FRAC, gsp.LINE_THICKNESS_FRAC
    gsp.DOT_RADIUS_FRAC = rng.uniform(0.20, 0.34)
    gsp.LINE_THICKNESS_FRAC = rng.uniform(0.09, 0.15)
    try:
        img, dot_pixels = gsp.render_clean(G, dots, scale, offset_x, offset_y)
    finally:
        gsp.DOT_RADIUS_FRAC, gsp.LINE_THICKNESS_FRAC = orig_dot_frac, orig_line_frac

    img, dot_pixels, degradation_record = degrade_v2(img, dot_pixels, rng)

    os.makedirs(out_dir, exist_ok=True)
    img_path = os.path.join(out_dir, f"{out_stem}.jpg")
    cv2.imwrite(img_path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    ground_truth = {
        "csv_path": csv_path,
        "kolam_number": kolam_number,
        "image_path": img_path,
        "seed": seed,
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "render_scale_px_per_lattice_unit": scale,
        "dot_pixel_positions": {f"{k[0]},{k[1]}": v for k, v in dot_pixels.items()},
        "degradation": degradation_record,
    }
    gt_path = os.path.join(out_dir, f"{out_stem}.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f)

    return ground_truth


def main():
    manifest = {"splits": {}}
    for split_name, cfg in SPLITS.items():
        out_dir = os.path.join(DATA_DIR, split_name)
        split_entries = []
        img_idx = 0
        for csv_path, kolam_number in cfg["patterns"]:
            fname = csv_path.split("/")[-1].replace(".csv", "")
            for v in range(cfg["variants_per_pattern"]):
                seed = cfg["seed_base"] + img_idx
                stem = f"{fname}_k{kolam_number}_v{v}"
                gt = generate_one(csv_path, kolam_number, seed, out_dir, stem)
                split_entries.append({
                    "stem": stem, "csv_path": csv_path, "kolam_number": kolam_number,
                    "seed": seed, "n_nodes": gt["n_nodes"],
                    "gray_mean": gt["degradation"]["measured_gray_mean"],
                    "gray_std": gt["degradation"]["measured_gray_std"],
                    "severity": gt["degradation"]["severity"],
                })
                img_idx += 1
        manifest["splits"][split_name] = {
            "n_patterns": len(cfg["patterns"]),
            "n_images": len(split_entries),
            "pattern_ids": [f"{c.split('/')[-1]}#{n}" for c, n in cfg["patterns"]],
            "images": split_entries,
        }
        print(f"{split_name}: {len(cfg['patterns'])} patterns x "
              f"{cfg['variants_per_pattern']} variants = {len(split_entries)} images -> {out_dir}")

    manifest_path = os.path.join(DATA_DIR, "split_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote {manifest_path}")


if __name__ == "__main__":
    main()
