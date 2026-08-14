"""M4.0 Phase 7 (extended): run the EXISTING deterministic detector
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
engine/image_io.py's DETECTION algorithms (detect_lattice, trace_path
itself) -- pure read-only probing, matching the "characterize, do not
fix" instruction this session repeats from the prior M4 Readiness
Report. It DOES use engine.image_io.is_traceable -- a boundary GATE
added alongside this script, not a change to trace_path's own body --
to avoid calling trace_path on the one documented, reproduced malformed
Lattice shape (nonzero pixel_positions, zero lattice_coords) that
crashes it with IndexError. That gate makes the SCRIPT robust to the
known crash; it does not hide it -- a probe that hits this shape is
still explicitly classified as INSUFFICIENT_LATTICE_POINTS, not
silently reported as SUCCESS. If any *other*, not-yet-documented
exception is raised, it is still caught, classified, and reported by
outcome/stage/exception type -- nothing is swallowed.

Images explicitly excluded from this baseline (documented in
real_photos/MANIFEST.md, not silently skipped):
  - ithayakkamalam_pulli_mayooranathan.jpg: confirmed digital rendering,
    not a photograph (see MANIFEST.md's exclusion note).

Outcome taxonomy (mutually exclusive, one per image):
  NO_DOT_DETECTION            -- preprocess/detect_lattice completed;
                                  zero candidate dot pixels found.
  INSUFFICIENT_LATTICE_POINTS -- >=1 candidate dot pixel found, but not
                                  enough (or not well-placed enough) to
                                  fit a lattice -- image_io.is_traceable
                                  is False. trace_path is NOT called on
                                  these (see gate above); this is the
                                  outcome that replaces what used to be
                                  an uncaught IndexError for
                                  kolam_india12_mckaysavage.jpg.
  LATTICE_FIT_FAILED          -- an unexpected exception during
                                  preprocess() or detect_lattice()
                                  itself (not the known asymmetric-shape
                                  case above, which is gated, not an
                                  exception).
  TRACE_FAILED                -- an unexpected exception from
                                  trace_path() on a lattice that WAS
                                  traceable per the gate above (i.e. a
                                  genuinely new failure mode, not the
                                  known one).
  GRAPH_FAILED                -- an unexpected exception during
                                  MultiGraph construction, validity
                                  checking, or motif induction.
  SUCCESS                     -- every stage above completed without
                                  exception. Does NOT imply the
                                  resulting graph is fully connected or
                                  structurally valid -- see the
                                  separate `connected` field for that;
                                  "SUCCESS" here means "did not crash
                                  and reached the end of the pipeline",
                                  matching the previous script's own
                                  level2_crash/level3_crash distinction.

Usage:
    python validate_real_photos.py
    python validate_real_photos.py --json results.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter

import cv2
import networkx as nx

from engine import image_io, motifs, validity

EXCLUDED = {"ithayakkamalam_pulli_mayooranathan.jpg"}

OUTCOMES = [
    "SUCCESS",
    "NO_DOT_DETECTION",
    "INSUFFICIENT_LATTICE_POINTS",
    "LATTICE_FIT_FAILED",
    "TRACE_FAILED",
    "GRAPH_FAILED",
]


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
        "traceable": None,
        "n_edges": None,
        "connected": None,
        "n_motif_placements": None,
        "outcome": None,
        "failure_stage": None,
        "exception_type": None,
        "exception_message": None,
    }

    try:
        preprocessed = image_io.preprocess(path)
        lattice = image_io.detect_lattice(preprocessed)
    except Exception as e:  # noqa: BLE001 -- probing script: classify, don't crash
        row["outcome"] = "LATTICE_FIT_FAILED"
        row["failure_stage"] = "preprocess/detect_lattice"
        row["exception_type"] = type(e).__name__
        row["exception_message"] = str(e)
        return row

    row["n_pixel_detections"] = len(lattice.pixel_positions)
    row["n_lattice_coords"] = len(lattice.lattice_coords)
    row["dot_radius_est"] = lattice.dot_radius
    row["traceable"] = image_io.is_traceable(lattice)

    if row["n_pixel_detections"] == 0:
        row["outcome"] = "NO_DOT_DETECTION"
        return row

    if not row["traceable"]:
        row["outcome"] = "INSUFFICIENT_LATTICE_POINTS"
        row["failure_stage"] = (
            "detect_lattice produced pixel detections with no fittable "
            "lattice (< 3 non-collinear points) -- gated before trace_path, "
            "see engine.image_io.is_traceable"
        )
        return row

    try:
        edges = image_io.trace_path(preprocessed, lattice)
        row["n_edges"] = len(edges)
    except Exception as e:  # noqa: BLE001
        row["outcome"] = "TRACE_FAILED"
        row["failure_stage"] = "trace_path"
        row["exception_type"] = type(e).__name__
        row["exception_message"] = str(e)
        return row

    try:
        G = nx.MultiGraph()
        G.add_nodes_from(lattice.lattice_coords)
        for a, b in edges:
            G.add_edge(a, b)

        if G.number_of_nodes() > 0:
            vres = validity.check_validity(G)
            row["connected"] = vres["largest_component_covers_all_nodes"]

        dots = set(G.nodes())
        if len(dots) >= 1:
            interior = motifs.interior_points(dots, radius=1)
            placements, _residual, _fully_covered = motifs.induce_motif_set_adaptive(
                G, interior, dots, max_radius=2, max_motifs_per_radius=50
            )
            row["n_motif_placements"] = len(placements)
    except Exception as e:  # noqa: BLE001
        row["outcome"] = "GRAPH_FAILED"
        row["failure_stage"] = "graph construction / validity / motif induction"
        row["exception_type"] = type(e).__name__
        row["exception_message"] = str(e)
        return row

    row["outcome"] = "SUCCESS"
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--json",
        metavar="PATH",
        default=None,
        help="Also write full machine-readable per-image results to PATH as JSON.",
    )
    args = parser.parse_args()

    paths = sorted(glob.glob(os.path.join("real_photos", "*.jpg")))
    paths = [p for p in paths if os.path.basename(p) not in EXCLUDED]

    rows = [probe_one(p) for p in paths]

    header = (
        f"{'file':45s} {'dims':>10s} {'g_mean':>7s} {'g_std':>6s} {'otsu':>6s} "
        f"{'fg%':>6s} {'px_det':>7s} {'lat_ok':>7s} {'conn':>6s} {'outcome':>28s}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        dims = f"{r['width']}x{r['height']}"
        fg_pct = f"{r['fg_fraction'] * 100:.1f}" if r["fg_fraction"] is not None else "?"
        px_det = r["n_pixel_detections"] if r["n_pixel_detections"] is not None else "?"
        lat_ok = r["n_lattice_coords"] if r["n_lattice_coords"] is not None else "?"
        conn = str(r["connected"])
        print(
            f"{r['file']:45s} {dims:>10s} {r['gray_mean']:7.1f} {r['gray_std']:6.1f} "
            f"{r['otsu_thresh']:6.1f} {fg_pct:>6s} {str(px_det):>7s} {str(lat_ok):>7s} "
            f"{conn:>6s} {r['outcome']:>28s}"
        )
        if r["failure_stage"]:
            print(f"    -> stage: {r['failure_stage']}")
        if r["exception_type"]:
            print(f"    -> exception: {r['exception_type']}: {r['exception_message']}")

    outcome_counts = Counter(r["outcome"] for r in rows)
    n_total = len(rows)
    print()
    print(f"Total probed: {n_total}")
    for outcome in OUTCOMES:
        print(f"  {outcome}: {outcome_counts.get(outcome, 0)}")

    # Legacy summary lines, preserved for continuity with prior sessions'
    # reports (PROJECT_STATE.md M4.0/M4.1-M4.2 sections quote these).
    # "Level-2 crashes" previously meant ANY exception/crash reaching
    # trace_path or graph construction, INCLUDING the asymmetric-lattice
    # IndexError. That specific case is now gated (INSUFFICIENT_LATTICE_
    # POINTS, not a crash) -- so this line reports genuinely-unexpected
    # crashes only, and is expected to read 0 unless a NEW failure mode
    # has appeared.
    n_zero_detections = outcome_counts.get("NO_DOT_DETECTION", 0)
    n_crashed = (
        outcome_counts.get("LATTICE_FIT_FAILED", 0)
        + outcome_counts.get("TRACE_FAILED", 0)
        + outcome_counts.get("GRAPH_FAILED", 0)
    )
    n_lattice_fit = sum(1 for r in rows if (r["n_lattice_coords"] or 0) > 0)
    print()
    print(f"Zero dot-pixel detections: {n_zero_detections}")
    print(f"Unexpected crashes (excludes the gated known blocker): {n_crashed}")
    print(f"Successful lattice fit (>=3 points): {n_lattice_fit}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, indent=2)
        print(f"\nWrote machine-readable results to {args.json}")


if __name__ == "__main__":
    main()
