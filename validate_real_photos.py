"""M4.0 Phase 7: run the EXISTING deterministic detector
(engine.image_io.preprocess + detect_lattice + trace_path) against every
real photograph in real_photos/, and report the three levels defined in
docs/M4_EVALUATION_PROTOCOL.md separately:

  Level 1 -- dot detection (raw counts + basic image statistics; real
             photos mostly lack pixel-exact ground truth, see
             docs/M4_EVALUATION_PROTOCOL.md Section 1 Tier B, so this is
             NOT a precision/recall table for real photos -- that table
             already exists for the synthetic corpus via the pytest
             suite, e.g. tests/test_image_io.py)
  Level 2 -- does trace_path / graph construction complete without
             crashing, and is the result connected?
  Level 3 -- does the full downstream pipeline (validity, motif
             induction) run to completion?

This is the M4.0 baseline measurement. It does NOT modify
engine/image_io.py, trace_path, or graph analysis -- pure read-only
probing, matching the "characterize, do not fix" instruction this
session repeats from the prior M4 Readiness Report.

Images explicitly excluded from this baseline (documented in
real_photos/MANIFEST.md, not silently skipped):
  - ithayakkamalam_pulli_mayooranathan.jpg: confirmed digital rendering,
    not a photograph (see MANIFEST.md's exclusion note).
"""

from __future__ import annotations

import glob
import os

import cv2
import numpy as np

from engine import image_io, motifs, validity

EXCLUDED = {"ithayakkamalam_pulli_mayooranathan.jpg"}


def probe_one(path: str) -> dict:
    fname = os.path.basename(path)
    img = cv2.imread(path)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    otsu_thresh, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    fg_fraction = float((binary > 0).mean())

    row = {
        "file": fname,
        "width": w,
        "height": h,
        "gray_mean": float(gray.mean()),
        "gray_std": float(gray.std()),
        "otsu_thresh": float(otsu_thresh),
        "fg_fraction": fg_fraction,
        "n_pixel_detections": None,
        "n_lattice_coords": None,
        "dot_radius_est": None,
        "level2_crash": None,
        "level2_crash_type": None,
        "level2_n_edges": None,
        "level2_connected": None,
        "level3_crash": None,
        "level3_n_placements": None,
    }

    try:
        preprocessed = image_io.preprocess(path)
        lattice = image_io.detect_lattice(preprocessed)
        row["n_pixel_detections"] = len(lattice.pixel_positions)
        row["n_lattice_coords"] = len(lattice.lattice_coords)
        row["dot_radius_est"] = lattice.dot_radius
    except Exception as e:  # noqa: BLE001 -- probing script, report don't crash
        row["level2_crash"] = True
        row["level2_crash_type"] = f"{type(e).__name__} (during preprocess/detect_lattice)"
        return row

    try:
        edges = image_io.trace_path(preprocessed, lattice)
        row["level2_n_edges"] = len(edges)
        row["level2_crash"] = False

        import networkx as nx

        G = nx.MultiGraph()
        G.add_nodes_from(lattice.lattice_coords)
        for a, b in edges:
            G.add_edge(a, b)

        if G.number_of_nodes() > 0:
            vres = validity.check_validity(G)
            row["level2_connected"] = vres["largest_component_covers_all_nodes"]
        else:
            row["level2_connected"] = None
    except Exception as e:  # noqa: BLE001
        row["level2_crash"] = True
        row["level2_crash_type"] = f"{type(e).__name__} (during trace_path/graph construction)"
        return row

    try:
        dots = set(G.nodes())
        if len(dots) >= 1:
            interior = motifs.interior_points(dots, radius=1)
            placements, _residual, _fully_covered = motifs.induce_motif_set_adaptive(
                G, interior, dots, max_radius=2, max_motifs_per_radius=50
            )
            row["level3_n_placements"] = len(placements)
        row["level3_crash"] = False
    except Exception as e:  # noqa: BLE001
        row["level3_crash"] = True
        row["level3_crash_type"] = f"{type(e).__name__} (during motif induction)"

    return row


def main():
    paths = sorted(glob.glob(os.path.join("real_photos", "*.jpg")))
    paths = [p for p in paths if os.path.basename(p) not in EXCLUDED]

    rows = [probe_one(p) for p in paths]

    header = (
        f"{'file':45s} {'dims':>10s} {'g_mean':>7s} {'g_std':>6s} {'otsu':>6s} "
        f"{'fg%':>6s} {'px_det':>7s} {'lat_ok':>7s} {'L2crash':>8s} {'L2conn':>7s} {'L3crash':>8s}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        dims = f"{r['width']}x{r['height']}"
        fg_pct = f"{r['fg_fraction'] * 100:.1f}" if r["fg_fraction"] is not None else "?"
        px_det = r["n_pixel_detections"] if r["n_pixel_detections"] is not None else "?"
        lat_ok = r["n_lattice_coords"] if r["n_lattice_coords"] is not None else "?"
        print(
            f"{r['file']:45s} {dims:>10s} {r['gray_mean']:7.1f} {r['gray_std']:6.1f} "
            f"{r['otsu_thresh']:6.1f} {fg_pct:>6s} {str(px_det):>7s} {str(lat_ok):>7s} "
            f"{str(r['level2_crash']):>8s} {str(r['level2_connected']):>7s} {str(r['level3_crash']):>8s}"
        )
        if r["level2_crash"]:
            print(f"    -> Level 2 crash: {r['level2_crash_type']}")
        if r.get("level3_crash"):
            print(f"    -> Level 3 crash: {r.get('level3_crash_type')}")

    n_total = len(rows)
    n_zero_detections = sum(1 for r in rows if r["n_pixel_detections"] == 0)
    n_crashed = sum(1 for r in rows if r["level2_crash"])
    n_lattice_fit = sum(1 for r in rows if (r["n_lattice_coords"] or 0) > 0)
    print()
    print(f"Total probed: {n_total}")
    print(f"Zero dot-pixel detections: {n_zero_detections}")
    print(f"Level-2 crashes: {n_crashed}")
    print(f"Successful lattice fit (>=3 points): {n_lattice_fit}")


if __name__ == "__main__":
    main()
