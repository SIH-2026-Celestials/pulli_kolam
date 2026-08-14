"""M4.3 Phase 1 (V3-A): stronger synthetic domain randomization.

Versioned successor to experiments/m4_2/generate_training_data.py -- that
file and experiments/m4_2/data/ are untouched (own data dir under
experiments/m4_3/data/, own manifest). Reuses
generate_synthetic_photos.py's render_clean/lattice_to_pixel_transform
UNCHANGED, same pattern M4.2 used relative to M4.1.

WHY these specific additions (evidence, not guesswork): Phase 0
(experiments/m4_3/results/v2_baseline.json) measured V2's real no-dot
false-positive rate at 100% (18/18) -- worse than the classical
baseline's 33.3% -- while synthetic test F1 was 0.998. That gap is the
textbook signature of a detector that has only ever seen images
containing a kolam pattern: every training image had dots on it, so the
model never learned what "no dots present" looks like, and it also never
saw photographic effects (shadows, partial occlusion, crop framing) that
a real photograph has but a clean synthetic render doesn't easily
produce from geometry+degradation alone.

Two categories of change from M4.2's degrade_v3, applied with
independent per-effect probabilities (not stacked-to-maximum severity,
per the task's explicit "realistic randomized probabilities, not
maximized augmentation strength" instruction):

1. NEW POSITIVE-SAMPLE EFFECTS (dot coordinates preserved through every
   transform, exactly like M4.2's degrade_v3):
   - directional illumination gradient (in addition to M4.2's radial
     vignette -- a photograph lit from one side, not just center-bright)
   - soft cast shadow (a diagonal darkened band, simulating a hand/
     object/architectural shadow across part of the kolam)
   - partial rectangular occlusion (a foreign-object patch -- foot,
     leaf, stray object -- covering part of the frame; dots under it
     become genuinely unrecoverable, which is realistic, not a bug)
   - crop-then-resize (simulates a photographer not framing the full
     pattern; coordinates are re-derived from the crop+resize affine
     transform, not approximated)
   - mild multiplicative sensor-gain noise on top of M4.2's additive
     gaussian noise (closer to real camera sensor noise, which is
     signal-dependent, not purely additive)
   - wider background-tint pool (more surface variety: cement, tile,
     dark stone, sand)

2. NEW NEGATIVE SAMPLES (the direct fix for the measured FP problem):
   pure-background renders with NO kolam pattern drawn at all --
   textured/tinted/noisy surfaces run through the SAME photographic
   degradation pipeline (blur, noise, jpeg, lighting) as the positive
   samples, with an EMPTY ground-truth dot set. This is still 100%
   synthetic (no real photos used, no fabricated dot coordinates -- zero
   dots is not a fabricated label, it is the true label for an image
   with no kolam on it) and is exactly the training signal V2 never
   received. A configurable fraction of each split's images are
   negatives (NEGATIVE_FRACTION below).

Pattern-level train/val/test separation: reuses the identical disjoint-
pattern-sampling approach as M4.2 (same seeding strategy, different seed
constant so this run doesn't reproduce M4.2's own draw), isolated under
experiments/m4_3/data/ -- never writes into experiments/m4_2/data/.
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
# kolam109 excluded -- same documented reason as M4.2 (unvalidated
# density regime at 128x128, see experiments/m4_2/generate_training_data.py).

# Same pattern budget as M4.2 (100/15/20) so V3-A isn't just "more data,"
# it's evaluated on comparably-sized splits -- the variable under test is
# the DEGRADATION PIPELINE, not dataset scale.
N_TRAIN_PATTERNS = 100
N_VAL_PATTERNS = 15
N_TEST_PATTERNS = 20
SPLIT_SEED = 4343  # different from M4.2's 4242 -- independent draw, own data dir

VARIANTS_PER_PATTERN = {"train": 4, "val": 3, "test": 3}
SEED_BASE = {"train": 500000, "val": 600000, "test": 700000}

# Negative (no-pattern) fraction of each split's total images -- additive,
# not a replacement for positive variants (positives per pattern above are
# unchanged from M4.2 so synthetic detection performance is not sacrificed
# to make room for negatives).
NEGATIVE_FRACTION = {"train": 0.20, "val": 0.20, "test": 0.20}

# Same calibration reference as M4.2 (measured real-photo gray stats,
# real_photos/MANIFEST.md) -- ranges themselves widened slightly per-effect
# below via independent probabilities, not by shifting the base range.
CONTRAST_RANGE = (0.55, 1.0)
BRIGHTNESS_RANGE = (-55, 8)
BLUR_SIGMA_RANGE = (0.4, 1.6)
NOISE_STD_RANGE = (4, 20)
JPEG_QUALITY_RANGE = (50, 92)
ROTATION_RANGE_DEG = (-16, 16)
SCALE_RANGE = (0.82, 1.16)
TRANSLATION_FRAC_RANGE = (-0.05, 0.05)
DOT_RADIUS_FRAC_RANGE = (0.20, 0.34)
LINE_THICKNESS_FRAC_RANGE = (0.09, 0.15)

# Per-effect application probabilities (independent coin flips) -- "realistic
# randomized probabilities, not maximized augmentation strength."
P_SHADOW = 0.35
P_OCCLUSION = 0.25
P_CROP = 0.30
P_DIRECTIONAL_LIGHT = 0.40
P_SENSOR_GAIN_NOISE = 0.5

BACKGROUND_TINTS = [
    (247, 245, 240), (150, 150, 155), (120, 105, 95),
    (170, 160, 140), (100, 95, 90), (190, 180, 165),
    (205, 195, 175),  # sand/cement
    (80, 80, 85),      # dark stone
    (160, 140, 110),   # terracotta tile
    (60, 60, 60),       # deep shad
]


def _sample_disjoint_patterns() -> dict:
    rng = random.Random(SPLIT_SEED)
    all_ids = {CSV19: list(range(1, 401)), CSV29: list(range(1, 101))}
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


def _apply_shadow(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """Diagonal soft-edged darkened band -- simulates a cast shadow from
    an out-of-frame object, common in outdoor kolam photos."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    angle = rng.uniform(0, math.pi)
    band_center = rng.uniform(0.2, 0.8)
    band_width = rng.uniform(0.15, 0.4)
    proj = (xx / w) * math.cos(angle) + (yy / h) * math.sin(angle)
    dist = np.abs(proj - band_center) / band_width
    darkness = rng.uniform(0.25, 0.55)
    mult = 1.0 - darkness * np.clip(1.0 - dist, 0, 1)
    return np.clip(img.astype(np.float32) * mult[..., None], 0, 255).astype(np.uint8)


def _apply_occlusion(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """One or two opaque rectangular patches (foreign object over part
    of the frame). Dots under the patch become genuinely unrecoverable --
    ground truth positions are NOT altered (they still "exist" at their
    true coordinates; the model simply won't be rewarded for guessing
    through opaque occlusion, which is the honest training signal)."""
    h, w = img.shape[:2]
    out = img.copy()
    n_patches = rng.choice([1, 1, 2])
    for _ in range(n_patches):
        pw, ph = rng.uniform(0.1, 0.3) * w, rng.uniform(0.1, 0.3) * h
        x0 = rng.uniform(0, w - pw)
        y0 = rng.uniform(0, h - ph)
        color = tuple(rng.randint(20, 200) for _ in range(3))
        cv2.rectangle(out, (int(x0), int(y0)), (int(x0 + pw), int(y0 + ph)), color, -1)
    return out


def _apply_crop_resize(img: np.ndarray, pts: np.ndarray, rng: random.Random) -> tuple[np.ndarray, np.ndarray]:
    """Crop a random sub-region then resize back to original size --
    simulates imperfect framing. Point coordinates are re-derived exactly
    (affine crop+scale), not approximated."""
    h, w = img.shape[:2]
    keep_frac = rng.uniform(0.75, 0.96)
    cw, ch = keep_frac * w, keep_frac * h
    x0 = rng.uniform(0, w - cw)
    y0 = rng.uniform(0, h - ch)
    cropped = img[int(y0):int(y0 + ch), int(x0):int(x0 + cw)]
    if cropped.shape[0] < 4 or cropped.shape[1] < 4:
        return img, pts
    resized = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
    sx, sy = w / cropped.shape[1], h / cropped.shape[0]
    new_pts = pts.copy()
    new_pts[..., 0] = (pts[..., 0] - x0) * sx
    new_pts[..., 1] = (pts[..., 1] - y0) * sy
    return resized, new_pts


def degrade_v3a(img: np.ndarray, dot_pixels: dict, rng: random.Random) -> tuple[np.ndarray, dict, dict]:
    h, w = img.shape[:2]
    has_pts = len(dot_pixels) > 0
    pts = np.array(list(dot_pixels.values()), dtype=np.float32).reshape(-1, 1, 2) if has_pts else None
    keys = list(dot_pixels.keys())

    severity = rng.random()
    record = {"severity": severity, "effects_applied": []}

    angle = rng.uniform(*ROTATION_RANGE_DEG)
    scale = rng.uniform(*SCALE_RANGE)
    tx = rng.uniform(*TRANSLATION_FRAC_RANGE) * w
    ty = rng.uniform(*TRANSLATION_FRAC_RANGE) * h
    bg = BACKGROUND_TINTS[rng.randrange(len(BACKGROUND_TINTS))]

    M_rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    M_rot[0, 2] += tx
    M_rot[1, 2] += ty
    img = cv2.warpAffine(img, M_rot, (w, h), borderValue=bg)
    if has_pts:
        pts = cv2.transform(pts, M_rot)
    record.update(rotation_deg=angle, scale=scale, translation_px=[tx, ty], background_tint=bg)

    jitter = (0.02 + 0.03 * severity) * w  # slightly stronger than M4.2's (still gentle, not maxed)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)],
                       [w + rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)],
                       [w + rng.uniform(-jitter, jitter), h + rng.uniform(-jitter, jitter)],
                       [rng.uniform(-jitter, jitter), h + rng.uniform(-jitter, jitter)]])
    M_persp = cv2.getPerspectiveTransform(src, dst)
    img = cv2.warpPerspective(img, M_persp, (w, h), borderValue=bg)
    if has_pts:
        pts = cv2.perspectiveTransform(pts, M_persp)

    if rng.random() < P_CROP:
        if has_pts:
            img, pts = _apply_crop_resize(img, pts, rng)
        else:
            img, _ = _apply_crop_resize(img, np.zeros((0, 1, 2), dtype=np.float32), rng)
        record["effects_applied"].append("crop_resize")

    # radial vignette (M4.2 baseline effect, kept)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = rng.uniform(0.25, 0.75) * w, rng.uniform(0.25, 0.75) * h
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (0.8 * math.hypot(w, h))
    vignette_strength = 0.15 + 0.25 * severity
    light = np.clip(1.0 - vignette_strength * dist, 0.5, 1.05)[..., None]
    img = np.clip(img.astype(np.float32) * light, 0, 255).astype(np.uint8)

    if rng.random() < P_DIRECTIONAL_LIGHT:
        ang = rng.uniform(0, 2 * math.pi)
        grad = (xx / w) * math.cos(ang) + (yy / h) * math.sin(ang)
        grad = (grad - grad.min()) / (grad.max() - grad.min() + 1e-6)
        strength = rng.uniform(0.15, 0.4)
        dlight = (1.0 - strength) + strength * grad
        img = np.clip(img.astype(np.float32) * dlight[..., None], 0, 255).astype(np.uint8)
        record["effects_applied"].append("directional_light")

    if rng.random() < P_SHADOW:
        img = _apply_shadow(img, rng)
        record["effects_applied"].append("shadow")

    contrast = CONTRAST_RANGE[1] - (CONTRAST_RANGE[1] - CONTRAST_RANGE[0]) * severity
    brightness = BRIGHTNESS_RANGE[1] - (BRIGHTNESS_RANGE[1] - BRIGHTNESS_RANGE[0]) * severity
    img = np.clip(img.astype(np.float32) * contrast + brightness, 0, 255).astype(np.uint8)
    record.update(contrast=contrast, brightness=brightness, vignette_strength=vignette_strength)

    if rng.random() < P_OCCLUSION:
        img = _apply_occlusion(img, rng)
        record["effects_applied"].append("occlusion")

    blur_sigma = BLUR_SIGMA_RANGE[0] + (BLUR_SIGMA_RANGE[1] - BLUR_SIGMA_RANGE[0]) * severity
    k = max(3, int(round(blur_sigma * 3)) | 1)
    img = cv2.GaussianBlur(img, (k, k), blur_sigma)

    noise_std = NOISE_STD_RANGE[0] + (NOISE_STD_RANGE[1] - NOISE_STD_RANGE[0]) * severity
    noise = np.random.normal(0, noise_std, img.shape).astype(np.float32)
    img_f = img.astype(np.float32) + noise
    if rng.random() < P_SENSOR_GAIN_NOISE:
        gain = 1.0 + np.random.normal(0, 0.03, img.shape[:2]).astype(np.float32)
        img_f = img_f * gain[..., None]
        record["effects_applied"].append("sensor_gain_noise")
    img = np.clip(img_f, 0, 255).astype(np.uint8)
    record.update(blur_sigma=blur_sigma, noise_std=noise_std)

    jpeg_quality = int(round(JPEG_QUALITY_RANGE[1] - (JPEG_QUALITY_RANGE[1] - JPEG_QUALITY_RANGE[0]) * severity))
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if ok:
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    record["jpeg_quality"] = jpeg_quality

    new_dot_pixels = {k: (float(p[0][0]), float(p[0][1])) for k, p in zip(keys, pts)} if has_pts else {}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    record["measured_gray_mean"] = float(gray.mean())
    record["measured_gray_std"] = float(gray.std())
    return img, new_dot_pixels, record


def generate_negative(seed: int, out_dir: str, out_stem: str, size: int = 600) -> dict:
    """Pure-background image, NO kolam drawn -- zero dots is the TRUE
    label here, not a fabricated one. Run through the same photographic
    degradation pipeline (minus dot-position bookkeeping, since there
    are none)."""
    rng = random.Random(seed)
    bg = BACKGROUND_TINTS[rng.randrange(len(BACKGROUND_TINTS))]
    img = np.full((size, size, 3), bg, dtype=np.uint8)
    # mild procedural texture so it isn't a flat color plane (real
    # surfaces -- floor, cement, cloth -- have texture)
    texture = np.random.normal(0, rng.uniform(3, 15), img.shape).astype(np.float32)
    img = np.clip(img.astype(np.float32) + texture, 0, 255).astype(np.uint8)
    # occasional stray straight lines/marks (non-kolam clutter -- tile
    # grout lines, floor cracks -- so the model can't just learn
    # "any line = kolam")
    if rng.random() < 0.3:
        for _ in range(rng.randint(1, 3)):
            p1 = (rng.randrange(size), rng.randrange(size))
            p2 = (rng.randrange(size), rng.randrange(size))
            cv2.line(img, p1, p2, tuple(int(c * 0.8) for c in bg), rng.randint(1, 3))

    img, _empty_pts, record = degrade_v3a(img, {}, rng)

    os.makedirs(out_dir, exist_ok=True)
    img_path = os.path.join(out_dir, f"{out_stem}.jpg")
    cv2.imwrite(img_path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    ground_truth = {
        "csv_path": None, "kolam_number": None, "image_path": img_path, "seed": seed,
        "n_nodes": 0, "n_edges": 0, "render_scale_px_per_lattice_unit": None,
        "dot_pixel_positions": {}, "degradation": record, "is_negative": True,
    }
    with open(os.path.join(out_dir, f"{out_stem}.json"), "w") as f:
        json.dump(ground_truth, f)
    return ground_truth


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

    img, dot_pixels, degradation_record = degrade_v3a(img, dot_pixels, rng)

    os.makedirs(out_dir, exist_ok=True)
    img_path = os.path.join(out_dir, f"{out_stem}.jpg")
    cv2.imwrite(img_path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    ground_truth = {
        "csv_path": csv_path, "kolam_number": kolam_number, "image_path": img_path,
        "seed": seed, "n_nodes": G.number_of_nodes(), "n_edges": G.number_of_edges(),
        "render_scale_px_per_lattice_unit": scale,
        "dot_pixel_positions": {f"{k[0]},{k[1]}": v for k, v in dot_pixels.items()},
        "degradation": degradation_record, "is_negative": False,
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
        "negative_fraction": NEGATIVE_FRACTION,
        "effect_probabilities": {
            "shadow": P_SHADOW, "occlusion": P_OCCLUSION, "crop_resize": P_CROP,
            "directional_light": P_DIRECTIONAL_LIGHT, "sensor_gain_noise": P_SENSOR_GAIN_NOISE,
        },
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
                    "is_negative": False,
                })
                all_gray_means.append(gt["degradation"]["measured_gray_mean"])
                all_gray_stds.append(gt["degradation"]["measured_gray_std"])
                img_idx += 1

        n_positive = len(entries)
        n_negative = int(round(n_positive * NEGATIVE_FRACTION[split_name] / (1 - NEGATIVE_FRACTION[split_name])))
        neg_seed_base = SEED_BASE[split_name] + 90000
        for i in range(n_negative):
            seed = neg_seed_base + i
            stem = f"negative_{split_name}_{i}"
            gt = generate_negative(seed, out_dir, stem)
            entries.append({
                "stem": stem, "csv_path": None, "kolam_number": None, "seed": seed,
                "n_nodes": 0, "gray_mean": gt["degradation"]["measured_gray_mean"],
                "gray_std": gt["degradation"]["measured_gray_std"], "severity": gt["degradation"]["severity"],
                "is_negative": True,
            })
            all_gray_means.append(gt["degradation"]["measured_gray_mean"])
            all_gray_stds.append(gt["degradation"]["measured_gray_std"])

        manifest["splits"][split_name] = {
            "n_patterns": len(patterns), "n_positive_images": n_positive, "n_negative_images": n_negative,
            "n_images": len(entries),
            "pattern_ids": [f"{c.split('/')[-1]}#{n}" for c, n in patterns],
            "images": entries,
        }
        print(f"{split_name}: {len(patterns)} patterns x {n_variants} variants = {n_positive} positive "
              f"+ {n_negative} negative = {len(entries)} images -> {out_dir}")

    manifest["generated_distribution_check"] = {
        "n_images": len(all_gray_means),
        "gray_mean_range": [float(np.min(all_gray_means)), float(np.max(all_gray_means))],
        "gray_mean_median": float(np.median(all_gray_means)),
        "gray_std_range": [float(np.min(all_gray_stds)), float(np.max(all_gray_stds))],
        "gray_std_median": float(np.median(all_gray_stds)),
    }

    manifest_path = os.path.join(DATA_DIR, "split_manifest_v3a.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote {manifest_path}")
    print("Generated distribution:", manifest["generated_distribution_check"])


if __name__ == "__main__":
    main()
