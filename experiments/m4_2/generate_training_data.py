"""M4.2 Phase C: scaled-up, better-calibrated synthetic training data.

Versioned successor to experiments/m4_1/generate_training_data.py --
NOT a patch to it (that file is untouched, and M4.1's own dataset under
experiments/m4_1/data/ is untouched). Two concrete changes from M4.1,
both directly motivated by evidence, not guesswork:

1. SCALE: M4.1 used 18 source patterns (kolam19 + kolam29 only). This
   version uses 135 patterns (100 train / 15 val / 20 test) drawn from
   kolam19 (400 available) and kolam29 (100 available) -- "use the
   available corpus responsibly," not just a token increase.
   **kolam109 is deliberately EXCLUDED**, checked not assumed: a direct
   measurement (same local-maxima methodology as
   experiments/m4_1/diagnose_target_resolution.py) found kolam109
   patterns average ~6800-7000 dots -- 15-35x denser than kolam19/29 --
   and recover only 2.1% of dots as distinct local maxima at 128x128
   (40.5% even at 256x256). The entire 128x128 target-resolution
   justification for M4.2 (TARGET_RESOLUTION_REPORT.md) was validated
   only up to 500 dots; including kolam109 here would train against a
   density regime this project has no evidence 128x128 can represent,
   and was excluded rather than silently included and hoped to work out.

2. REALISTIC DEGRADATION CALIBRATION: M4.1's degrade_v2 pushed
   brightness/contrast toward the two WORST real low-contrast failures
   it knew about, which (per M4.1's own Session 13 Section 3 caveat)
   overshot into harsher-than-realistic difficulty -- even the
   classical detector's recall collapsed on that set. This version is
   calibrated instead against the FULL real-photo corpus's actual
   measured gray-statistics distribution (all 22 real photos, not just
   the 2 hardest): gray mean range [62.5, 154.6], median 121.4; gray
   std range [21.6, 63.4], median 45.9 (measured directly from
   real_photos/*.jpg, excluding the confirmed-synthetic exclusion, see
   real_photos/MANIFEST.md). Degradation parameters below are chosen so
   the GENERATED distribution's mean/std lands in this measured real
   range, not below it.

SYNTHETIC-TO-REAL VALIDATION STRATEGY (documented per the task's
explicit requirement, not just implemented): this dataset's realism is
checked, not assumed, by comparing the DISTRIBUTION of generated images'
gray mean/std (reported by this script's own summary) against the real-
photo distribution above -- both are logged to
experiments/m4_2/data/split_manifest.json for direct comparison. If a
future revision's generated distribution drifts outside the measured
real range, that is a script bug to fix, not something to calibrate the
evaluation around. The model's actual real-photo evaluation (Phase D,
experiments/m4_2/evaluate_m4_2.py) remains the final word on synthetic-
to-real transfer -- this calibration step reduces, but does not by
itself prove away, the M4.1 domain-gap finding.

Reuses generate_synthetic_photos.py's render_clean /
lattice_to_pixel_transform UNCHANGED (that module is never modified).
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
# kolam109 deliberately excluded -- see module docstring point 1
# (measured ~6800-7000 dots/pattern, only 2.1% local-maxima recovery
# at 128x128; a density regime never validated at this resolution).

# 400 / 100 patterns available per collection (verified,
# engine.dataset.list_pattern_ids). Sampled with a fixed seed for
# reproducibility -- not the full corpus (compute-budget decision,
# documented, not hidden -- see docs/M4_2_IMPLEMENTATION_PLAN.md
# Scope decision 3).
N_TRAIN_PATTERNS = 100
N_VAL_PATTERNS = 15
N_TEST_PATTERNS = 20
SPLIT_SEED = 4242

VARIANTS_PER_PATTERN = {"train": 4, "val": 3, "test": 3}
SEED_BASE = {"train": 100000, "val": 200000, "test": 300000}

# Calibrated against the REAL photo corpus's measured distribution
# (module docstring) -- narrower/gentler than M4.1's degrade_v2.
CONTRAST_RANGE = (0.55, 1.0)      # was (0.50, 1.05) in M4.1 -- capped below 1.0, floor raised slightly
BRIGHTNESS_RANGE = (-50, 5)       # was (-90, 5) in M4.1 -- much less extreme underexposure
BLUR_SIGMA_RANGE = (0.4, 1.4)     # was (0.4, 2.0) in M4.1
NOISE_STD_RANGE = (4, 18)         # was (4, 26) in M4.1
JPEG_QUALITY_RANGE = (55, 92)     # was (35, 90) in M4.1
ROTATION_RANGE_DEG = (-15, 15)
SCALE_RANGE = (0.85, 1.15)
TRANSLATION_FRAC_RANGE = (-0.04, 0.04)  # NEW axis not in M4.1: pure translation, as fraction of image size
DOT_RADIUS_FRAC_RANGE = (0.20, 0.34)
LINE_THICKNESS_FRAC_RANGE = (0.09, 0.15)

BACKGROUND_TINTS = [
    (247, 245, 240), (150, 150, 155), (120, 105, 95),
    (170, 160, 140), (100, 95, 90), (190, 180, 165),
]


def _sample_disjoint_patterns() -> dict:
    rng = random.Random(SPLIT_SEED)
    all_ids = {
        CSV19: list(range(1, 401)),
        CSV29: list(range(1, 101)),
    }
    # proportional sampling across collections, then split into disjoint train/val/test
    pool = []
    for csv_path, ids in all_ids.items():
        pool.extend((csv_path, i) for i in ids)
    rng.shuffle(pool)

    total_needed = N_TRAIN_PATTERNS + N_VAL_PATTERNS + N_TEST_PATTERNS
    assert len(pool) >= total_needed
    selected = pool[:total_needed]
    train = selected[:N_TRAIN_PATTERNS]
    val = selected[N_TRAIN_PATTERNS:N_TRAIN_PATTERNS + N_VAL_PATTERNS]
    test = selected[N_TRAIN_PATTERNS + N_VAL_PATTERNS:total_needed]
    return {"train": train, "val": val, "test": test}


def degrade_v3(img: np.ndarray, dot_pixels: dict, rng: random.Random) -> tuple[np.ndarray, dict, dict]:
    h, w = img.shape[:2]
    pts = np.array(list(dot_pixels.values()), dtype=np.float32).reshape(-1, 1, 2)
    keys = list(dot_pixels.keys())

    severity = rng.random()
    record = {"severity": severity}

    angle = rng.uniform(*ROTATION_RANGE_DEG)
    scale = rng.uniform(*SCALE_RANGE)
    tx = rng.uniform(*TRANSLATION_FRAC_RANGE) * w
    ty = rng.uniform(*TRANSLATION_FRAC_RANGE) * h
    bg = BACKGROUND_TINTS[rng.randrange(len(BACKGROUND_TINTS))]

    M_rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    M_rot[0, 2] += tx
    M_rot[1, 2] += ty
    img = cv2.warpAffine(img, M_rot, (w, h), borderValue=bg)
    pts = cv2.transform(pts, M_rot)
    record.update(rotation_deg=angle, scale=scale, translation_px=[tx, ty], background_tint=bg)

    jitter = (0.015 + 0.025 * severity) * w  # gentler perspective than M4.1
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)],
                       [w + rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)],
                       [w + rng.uniform(-jitter, jitter), h + rng.uniform(-jitter, jitter)],
                       [rng.uniform(-jitter, jitter), h + rng.uniform(-jitter, jitter)]])
    M_persp = cv2.getPerspectiveTransform(src, dst)
    img = cv2.warpPerspective(img, M_persp, (w, h), borderValue=bg)
    pts = cv2.perspectiveTransform(pts, M_persp)

    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = rng.uniform(0.25, 0.75) * w, rng.uniform(0.25, 0.75) * h
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (0.8 * math.hypot(w, h))
    vignette_strength = 0.15 + 0.25 * severity
    light = np.clip(1.0 - vignette_strength * dist, 0.5, 1.05)[..., None]
    img = np.clip(img.astype(np.float32) * light, 0, 255).astype(np.uint8)

    contrast = CONTRAST_RANGE[1] - (CONTRAST_RANGE[1] - CONTRAST_RANGE[0]) * severity
    brightness = BRIGHTNESS_RANGE[1] - (BRIGHTNESS_RANGE[1] - BRIGHTNESS_RANGE[0]) * severity
    img = np.clip(img.astype(np.float32) * contrast + brightness, 0, 255).astype(np.uint8)
    record.update(contrast=contrast, brightness=brightness, vignette_strength=vignette_strength)

    blur_sigma = BLUR_SIGMA_RANGE[0] + (BLUR_SIGMA_RANGE[1] - BLUR_SIGMA_RANGE[0]) * severity
    k = max(3, int(round(blur_sigma * 3)) | 1)
    img = cv2.GaussianBlur(img, (k, k), blur_sigma)

    noise_std = NOISE_STD_RANGE[0] + (NOISE_STD_RANGE[1] - NOISE_STD_RANGE[0]) * severity
    noise = np.random.normal(0, noise_std, img.shape).astype(np.float32)
    img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    record.update(blur_sigma=blur_sigma, noise_std=noise_std)

    jpeg_quality = int(round(JPEG_QUALITY_RANGE[1] - (JPEG_QUALITY_RANGE[1] - JPEG_QUALITY_RANGE[0]) * severity))
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if ok:
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    record["jpeg_quality"] = jpeg_quality

    new_dot_pixels = {k: (float(p[0][0]), float(p[0][1])) for k, p in zip(keys, pts)}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    record["measured_gray_mean"] = float(gray.mean())
    record["measured_gray_std"] = float(gray.std())
    return img, new_dot_pixels, record


def generate_one(csv_path: str, kolam_number: int, seed: int, out_dir: str, out_stem: str) -> dict:
    G = graph_io.load_kolam(csv_path, kolam_number)
    dots = graph_io.dots_set(G)
    scale, offset_x, offset_y = gsp.lattice_to_pixel_transform(dots)

    rng = random.Random(seed)
    orig_dot_frac, orig_line_frac = gsp.DOT_RADIUS_FRAC, gsp.LINE_THICKNESS_FRAC
    gsp.DOT_RADIUS_FRAC = rng.uniform(*DOT_RADIUS_FRAC_RANGE)
    gsp.LINE_THICKNESS_FRAC = rng.uniform(*LINE_THICKNESS_FRAC_RANGE)
    try:
        img, dot_pixels = gsp.render_clean(G, dots, scale, offset_x, offset_y)
    finally:
        gsp.DOT_RADIUS_FRAC, gsp.LINE_THICKNESS_FRAC = orig_dot_frac, orig_line_frac

    img, dot_pixels, degradation_record = degrade_v3(img, dot_pixels, rng)

    os.makedirs(out_dir, exist_ok=True)
    img_path = os.path.join(out_dir, f"{out_stem}.jpg")
    cv2.imwrite(img_path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    ground_truth = {
        "csv_path": csv_path, "kolam_number": kolam_number, "image_path": img_path,
        "seed": seed, "n_nodes": G.number_of_nodes(), "n_edges": G.number_of_edges(),
        "render_scale_px_per_lattice_unit": scale,
        "dot_pixel_positions": {f"{k[0]},{k[1]}": v for k, v in dot_pixels.items()},
        "degradation": degradation_record,
    }
    with open(os.path.join(out_dir, f"{out_stem}.json"), "w") as f:
        json.dump(ground_truth, f)
    return ground_truth


def main():
    splits = _sample_disjoint_patterns()
    train_set, val_set, test_set = set(splits["train"]), set(splits["val"]), set(splits["test"])
    assert not (train_set & val_set) and not (train_set & test_set) and not (val_set & test_set), \
        "pattern overlap across splits"

    manifest = {"splits": {}, "generation_config": {
        "contrast_range": CONTRAST_RANGE, "brightness_range": BRIGHTNESS_RANGE,
        "blur_sigma_range": BLUR_SIGMA_RANGE, "noise_std_range": NOISE_STD_RANGE,
        "jpeg_quality_range": JPEG_QUALITY_RANGE, "rotation_range_deg": ROTATION_RANGE_DEG,
        "scale_range": SCALE_RANGE, "translation_frac_range": TRANSLATION_FRAC_RANGE,
        "calibration_reference": {
            "real_photo_gray_mean_range": [62.5, 154.6], "real_photo_gray_mean_median": 121.4,
            "real_photo_gray_std_range": [21.6, 63.4], "real_photo_gray_std_median": 45.9,
        },
    }}
    all_gray_means, all_gray_stds = [], []

    for split_name, patterns in splits.items():
        out_dir = os.path.join(DATA_DIR, split_name)
        entries = []
        img_idx = 0
        n_variants = VARIANTS_PER_PATTERN[split_name]
        for csv_path, kolam_number in patterns:
            fname = csv_path.split("/")[-1].replace(".csv", "")
            for v in range(n_variants):
                seed = SEED_BASE[split_name] + img_idx
                stem = f"{fname}_k{kolam_number}_v{v}"
                gt = generate_one(csv_path, kolam_number, seed, out_dir, stem)
                entries.append({
                    "stem": stem, "csv_path": csv_path, "kolam_number": kolam_number, "seed": seed,
                    "n_nodes": gt["n_nodes"], "gray_mean": gt["degradation"]["measured_gray_mean"],
                    "gray_std": gt["degradation"]["measured_gray_std"], "severity": gt["degradation"]["severity"],
                })
                all_gray_means.append(gt["degradation"]["measured_gray_mean"])
                all_gray_stds.append(gt["degradation"]["measured_gray_std"])
                img_idx += 1
        manifest["splits"][split_name] = {
            "n_patterns": len(patterns), "n_images": len(entries),
            "pattern_ids": [f"{c.split('/')[-1]}#{n}" for c, n in patterns],
            "images": entries,
        }
        print(f"{split_name}: {len(patterns)} patterns x {n_variants} variants = {len(entries)} images -> {out_dir}")

    manifest["generated_distribution_check"] = {
        "n_images": len(all_gray_means),
        "gray_mean_range": [float(np.min(all_gray_means)), float(np.max(all_gray_means))],
        "gray_mean_median": float(np.median(all_gray_means)),
        "gray_std_range": [float(np.min(all_gray_stds)), float(np.max(all_gray_stds))],
        "gray_std_median": float(np.median(all_gray_stds)),
        "note": ("Compare against generation_config.calibration_reference -- generated median "
                 "should land within (not below) the measured real-photo range, per this script's "
                 "documented synthetic-to-real calibration strategy."),
    }

    manifest_path = os.path.join(DATA_DIR, "split_manifest.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote {manifest_path}")
    print("Generated distribution:", manifest["generated_distribution_check"])


if __name__ == "__main__":
    main()
