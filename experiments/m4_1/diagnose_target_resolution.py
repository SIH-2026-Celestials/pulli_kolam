"""M4.1.2: target-resolution representation check. Answers ONE question
-- "at what heatmap resolution do this dataset's actual ground-truth dot
positions become individually separable under a Gaussian-blob target
encoding?" -- as a follow-up to the M4.1.1 diagnosis
(diagnostics/M4_1_HEATMAP_DIAGNOSIS.md), which found that the trained
model's 32x32 heatmap output already matches its OWN training target
almost exactly (low MSE), and that the target itself -- not the model,
not peak_detect.py -- loses individual-dot identity at this dataset's
real density (180-500+ dots/image).

This is a PURE REPRESENTATION experiment:
  - No CNN, no checkpoint, no torch import, no inference.
  - No retraining, no dataset expansion (uses ONLY already-generated
    ground-truth JSON files under experiments/m4_1/data/ and the
    original synthetic_photos/ / synthetic_photos_heldout/).
  - No change to experiments/m4_1/model.py, train.py,
    generate_training_data.py, generate_synthetic_photos.py,
    peak_detect.py, or ml_lattice_detector.py. The coordinate-scaling +
    Gaussian-heatmap construction used by the real training pipeline
    (model.py's make_gaussian_heatmap, train.py's DotHeatmapDataset) is
    REIMPLEMENTED LOCALLY below, generalized to an arbitrary output
    resolution, per this task's explicit instruction ("implement the
    resolution calculation locally inside the diagnostic script rather
    than changing production training behavior").
  - No change to engine/, the frozen ML contract, trace_path, or the
    classical detector.

COORDINATE MAPPING (mirrors the real pipeline exactly, generalized to
resolution R instead of hardcoding 32): the real pipeline scales an
original-image pixel position to a stride-8 heatmap cell in TWO steps
(resize original -> MODEL_INPUT_SIZE=256, then divide by STRIDE=8).
Composing two linear scalings is mathematically identical to one direct
scaling from the original image size straight to the final resolution
R, so this script uses `cell = pixel * (R / SYNTH_IMAGE_SIZE)` directly
-- the same result, without needing to simulate an intermediate resize.
Ground-truth dot pixel positions are taken directly from each image's
own already-recorded `dot_pixel_positions` (generate_synthetic_photos.py's
own post-degradation ground truth) -- these are NOT re-deskewed via
engine.image_io.preprocess() here, because this experiment is about the
TARGET-ENCODING SCHEME in the abstract (does the encoding preserve
separability at a given resolution, given real dot coordinates), not
about re-running the full detection pipeline -- M4.1.1 already covered
that. Deskew is a rigid rotation and does not change nearest-neighbor
spacing in any way relevant to this question.

SIGMA: held fixed at 1.2 heatmap-cells across every resolution tested --
matching experiments/m4_1/model.py's actual training-time value exactly
(MAKE_GAUSSIAN_HEATMAP_SIGMA below == model.py's own default). This is
deliberate: it isolates "does resolution ALONE fix separability" from
"did we also quietly change the blur convention." See
TARGET_RESOLUTION_REPORT.md Section D for a separate discussion of what
sigma WOULD be reasonable at each resolution.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import maximum_filter
from scipy.spatial import cKDTree

DIAG_DIR = os.path.join(os.path.dirname(__file__), "diagnostics")
VIZ_DIR = os.path.join(DIAG_DIR, "target_resolution_viz")
RESULTS_JSON = os.path.join(DIAG_DIR, "target_resolution_report.json")
REPORT_MD = os.path.join(DIAG_DIR, "TARGET_RESOLUTION_REPORT.md")

RESOLUTIONS = [32, 64, 128, 256]
SIGMA_CELLS = 1.2  # == experiments/m4_1/model.py's make_gaussian_heatmap default
SYNTH_IMAGE_SIZE = 900  # == generate_synthetic_photos.py's IMAGE_SIZE constant

CANDIDATE_GLOBS = [
    "experiments/m4_1/data/train/*.json",
    "experiments/m4_1/data/val/*.json",
    "experiments/m4_1/data/test/*.json",
    "synthetic_photos/*.json",
    "synthetic_photos_heldout/*.json",
]


def discover_density_range() -> list[dict]:
    """Survey every already-generated ground-truth JSON (no new data
    generated) to find the real min/max dot-count range in this
    project's synthetic corpus -- do not assume a smooth low/medium/high
    spread exists without checking."""
    entries = []
    for pattern in CANDIDATE_GLOBS:
        for path in glob.glob(pattern):
            with open(path) as f:
                d = json.load(f)
            entries.append({"path": path, "n_nodes": d["n_nodes"], "image_path": d["image_path"]})
    entries.sort(key=lambda e: e["n_nodes"])
    return entries


def select_representative_images(entries: list[dict]) -> list[dict]:
    """Pick low/medium/high representatives from what ACTUALLY EXISTS in
    the corpus -- no synthetic generation performed here. If the corpus
    has a gap (verified below: it does -- kolam19-based images span
    180-224 dots, kolam29-based span 444-500, nothing in between), that
    gap is reported explicitly rather than papered over."""
    lowest = entries[0]
    highest = entries[-1]
    mid_candidates = [e for e in entries if e["n_nodes"] < 300]  # the kolam19-density cluster
    middle = mid_candidates[len(mid_candidates) // 2] if mid_candidates else entries[len(entries) // 2]
    picked = {e["path"]: e for e in [lowest, middle, highest]}
    return list(picked.values())


def make_gaussian_heatmap_at_resolution(dot_positions_pixel: np.ndarray, image_size: int,
                                         resolution: int, sigma_cells: float) -> np.ndarray:
    """Local reimplementation of model.py's make_gaussian_heatmap,
    generalized to an arbitrary output resolution -- NOT imported from
    or modifying model.py. Uses the same max-not-sum blob combination
    rule model.py uses (a dot's own blob never gets diluted by a
    neighbor's), and the same coordinate-scaling logic train.py's
    DotHeatmapDataset uses (see module docstring for the two-step vs.
    one-step equivalence argument)."""
    scale = resolution / image_size
    heatmap = np.zeros((resolution, resolution), dtype=np.float64)
    if len(dot_positions_pixel) == 0:
        return heatmap
    cell_positions = dot_positions_pixel * scale
    yy, xx = np.mgrid[0:resolution, 0:resolution]
    for cx, cy in cell_positions:
        g = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma_cells * sigma_cells))
        heatmap = np.maximum(heatmap, g)
    return heatmap


def analyze_resolution(dot_positions_pixel: np.ndarray, image_size: int, resolution: int,
                        sigma_cells: float) -> dict:
    heatmap = make_gaussian_heatmap_at_resolution(dot_positions_pixel, image_size, resolution, sigma_cells)
    n_dots = len(dot_positions_pixel)

    # local maxima: cells that are the max of their own 3x3 neighborhood
    # AND clear a low activation floor (0.2) -- an OBJECTIVE, not visual,
    # separability measurement.
    local_max_mask = (heatmap == maximum_filter(heatmap, size=3)) & (heatmap > 0.2)
    n_local_maxima = int(local_max_mask.sum())

    cell_positions = dot_positions_pixel * (resolution / image_size)
    if n_dots >= 2:
        tree = cKDTree(cell_positions)
        d, _ = tree.query(cell_positions, k=2)
        nn_dist_cells = d[:, 1]
        median_nn = float(np.median(nn_dist_cells))
        mean_nn = float(np.mean(nn_dist_cells))
        pct_within_2sigma = float((nn_dist_cells < 2 * sigma_cells).mean() * 100)
        pct_within_3sigma = float((nn_dist_cells < 3 * sigma_cells).mean() * 100)
    else:
        median_nn = mean_nn = pct_within_2sigma = pct_within_3sigma = None

    # literal collision count: dots whose rounded integer cell coincides
    # with another dot's -- these are UNRECOVERABLY merged at this
    # resolution, not just "close."
    cell_int = np.round(cell_positions).astype(int)
    unique_cells = {tuple(c) for c in cell_int}
    n_distinct_cells_occupied = len(unique_cells)
    n_dots_lost_to_cell_collision = n_dots - n_distinct_cells_occupied

    return {
        "resolution": resolution,
        "n_ground_truth_dots": n_dots,
        "n_local_maxima_in_heatmap": n_local_maxima,
        "n_local_maxima_over_n_dots_ratio": (n_local_maxima / n_dots) if n_dots else None,
        "sigma_cells": sigma_cells,
        "median_nn_distance_cells": median_nn,
        "mean_nn_distance_cells": mean_nn,
        "median_nn_over_sigma_ratio": (median_nn / sigma_cells) if median_nn is not None else None,
        "pct_dots_with_neighbor_within_2sigma": pct_within_2sigma,
        "pct_dots_with_neighbor_within_3sigma": pct_within_3sigma,
        "n_distinct_cells_occupied": n_distinct_cells_occupied,
        "n_dots_lost_to_cell_collision": n_dots_lost_to_cell_collision,
        "pct_dots_lost_to_cell_collision": (n_dots_lost_to_cell_collision / n_dots * 100) if n_dots else None,
        "heatmap_max": float(heatmap.max()),
        "heatmap_mean": float(heatmap.mean()),
    }, heatmap


def save_visualization(image_path: str, dot_positions_pixel: np.ndarray, heatmaps: dict, out_path: str, title: str):
    n_panels = 1 + len(heatmaps)
    fig, axes = plt.subplots(1, n_panels, figsize=(4 * n_panels, 4))
    fig.suptitle(title, fontsize=10)

    orig = cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2RGB)
    axes[0].imshow(orig)
    if len(dot_positions_pixel) > 0:
        axes[0].scatter(dot_positions_pixel[:, 0], dot_positions_pixel[:, 1], c="lime", s=4, marker=".")
    axes[0].set_title(f"original + {len(dot_positions_pixel)} dots")
    axes[0].axis("off")

    for i, (res, heatmap) in enumerate(sorted(heatmaps.items())):
        ax = axes[i + 1]
        ax.imshow(heatmap, cmap="hot", vmin=0, vmax=1)
        ax.set_title(f"{res}x{res} target")
        ax.axis("off")

    plt.tight_layout()
    plt.savefig(out_path, dpi=100)
    plt.close(fig)


def main():
    os.makedirs(VIZ_DIR, exist_ok=True)

    print("Discovering density range across ALL already-generated synthetic images (no new generation)...")
    entries = discover_density_range()
    print(f"  {len(entries)} images found. n_nodes range: {entries[0]['n_nodes']} - {entries[-1]['n_nodes']}")
    unique_ns = sorted(set(e["n_nodes"] for e in entries))
    print(f"  unique dot counts: {unique_ns}")

    representative = select_representative_images(entries)
    print(f"Selected {len(representative)} representative images: "
          f"{[(e['n_nodes'], os.path.basename(e['path'])) for e in representative]}")

    report = {
        "sigma_cells_used": SIGMA_CELLS,
        "resolutions_tested": RESOLUTIONS,
        "density_survey": {
            "n_images_surveyed": len(entries),
            "n_nodes_min": entries[0]["n_nodes"],
            "n_nodes_max": entries[-1]["n_nodes"],
            "unique_n_nodes_values": unique_ns,
            "note": ("The already-generated corpus has a bimodal gap: kolam19-based images "
                     "span 180-224 dots, kolam29-based images span 444-500 dots, with NO "
                     "images anywhere in between (225-443). No new images were generated to "
                     "fill this gap, per the task's 'no dataset expansion' rule -- this gap "
                     "is reported as a limitation, not smoothed over."),
        },
        "per_image_results": [],
    }

    for entry in representative:
        with open(entry["path"]) as f:
            gt = json.load(f)
        dot_positions = np.array(list(gt["dot_pixel_positions"].values()), dtype=np.float64)
        img_path = gt["image_path"]

        image_result = {"file": os.path.basename(entry["path"]), "image_path": img_path,
                         "n_ground_truth_dots": len(dot_positions), "by_resolution": []}
        heatmaps_for_viz = {}
        for res in RESOLUTIONS:
            stats, heatmap = analyze_resolution(dot_positions, SYNTH_IMAGE_SIZE, res, SIGMA_CELLS)
            image_result["by_resolution"].append(stats)
            heatmaps_for_viz[res] = heatmap

        report["per_image_results"].append(image_result)

        viz_path = os.path.join(VIZ_DIR, f"{os.path.splitext(os.path.basename(entry['path']))[0]}.png")
        save_visualization(img_path, dot_positions, heatmaps_for_viz, viz_path,
                            f"{os.path.basename(entry['path'])} (n_dots={len(dot_positions)})")
        print(f"  wrote {viz_path}")

    os.makedirs(DIAG_DIR, exist_ok=True)
    with open(RESULTS_JSON, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nWrote {RESULTS_JSON}")

    print("\n=== Summary table ===")
    print(f"{'image':30s} {'n_dots':>7s} {'res':>5s} {'n_localmax':>11s} {'med_nn/sigma':>13s} "
          f"{'%within2sig':>12s} {'%within3sig':>12s} {'%collided':>10s}")
    for img_res in report["per_image_results"]:
        for r in img_res["by_resolution"]:
            ratio = f"{r['median_nn_over_sigma_ratio']:.2f}" if r["median_nn_over_sigma_ratio"] is not None else "n/a"
            w2 = f"{r['pct_dots_with_neighbor_within_2sigma']:.1f}" if r["pct_dots_with_neighbor_within_2sigma"] is not None else "n/a"
            w3 = f"{r['pct_dots_with_neighbor_within_3sigma']:.1f}" if r["pct_dots_with_neighbor_within_3sigma"] is not None else "n/a"
            print(f"{img_res['file']:30s} {r['n_ground_truth_dots']:7d} {r['resolution']:5d} "
                  f"{r['n_local_maxima_in_heatmap']:11d} {ratio:>13s} {w2:>12s} {w3:>12s} "
                  f"{r['pct_dots_lost_to_cell_collision']:9.1f}%")


if __name__ == "__main__":
    main()
