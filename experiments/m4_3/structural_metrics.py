"""M4.3 shared helper: turn a detector's Lattice output into the
structural/graph metrics the M4.3 task requires everywhere (Phase 0
baseline, Phase 2/4 decision matrix, Phase 5 diagnostics, Phase 9
generation check) -- one implementation, not copy-pasted five times.

Builds an nx.MultiGraph from `image_io.trace_path`'s (dot_a, dot_b)
lattice-coordinate pairs (duplicated entries per genuine double-strand,
matching engine/validity.py's own MultiGraph expectation), then reports
the same fields `engine.validity.check_validity` / `diagnose_validity`
compute -- reused unmodified, not reimplemented.

Never fabricates ground truth: for real photos there is no GT graph to
compare against, only the graph induced by the DETECTOR's own output.
That is labeled `source: "real_photo_prediction_only"` by every caller
that touches real_photos/, so nothing downstream can mistake it for a
verified match.
"""

from __future__ import annotations

import time

import networkx as nx
import numpy as np

from engine import image_io, validity


def lattice_to_graph_metrics(preprocessed: image_io.Preprocessed, lattice: "image_io.Lattice") -> dict:
    """Runs trace_path on `lattice`, builds a MultiGraph, and reports the
    validity.check_validity() fields plus edge/node counts. If lattice is
    empty (detector found nothing / collapsed to empty) or trace_path
    crashes (documented pre-existing blocker, see
    experiments/m4_2/ml_lattice_detector.py's module docstring), reports
    that explicitly rather than fabricating a graph."""
    out = {
        "n_dots": len(lattice.pixel_positions) if lattice.pixel_positions else 0,
        "trace_path_crashed": False,
        "n_edges": None, "connected_components": None, "is_eulerian_circuit": None,
        "has_eulerian_path": None, "largest_component_covers_all_nodes": None,
        "n_odd_degree_nodes": None, "reconstruction_valid": None,
    }
    if not lattice.pixel_positions or len(lattice.lattice_coords) < 2:
        out["note"] = "empty or near-empty detection -- no graph to build"
        return out

    try:
        edges = image_io.trace_path(preprocessed, lattice)
    except Exception as e:  # noqa: BLE001
        out["trace_path_crashed"] = True
        out["trace_path_crash_type"] = type(e).__name__
        return out

    G = nx.MultiGraph()
    G.add_nodes_from(range(len(lattice.lattice_coords)))
    id_of = {tuple(c): i for i, c in enumerate(lattice.lattice_coords)}
    for a, b in edges:
        ia, ib = id_of.get(tuple(a)), id_of.get(tuple(b))
        if ia is not None and ib is not None and ia != ib:
            G.add_edge(ia, ib)

    out["n_edges"] = G.number_of_edges()
    if G.number_of_nodes() == 0 or G.number_of_edges() == 0:
        out["note"] = "no edges traced"
        return out

    v = validity.check_validity(G)
    out.update({
        "connected_components": v["connected_components"],
        "is_eulerian_circuit": v["is_eulerian_circuit"],
        "has_eulerian_path": v["has_eulerian_path"],
        "largest_component_covers_all_nodes": v["largest_component_covers_all_nodes"],
        "reconstruction_valid": bool(
            v["largest_component_covers_all_nodes"] and (v["is_eulerian_circuit"] or v["has_eulerian_path"])
        ),
    })
    largest = max(nx.connected_components(G), key=len)
    Gc = G.subgraph(largest)
    out["n_odd_degree_nodes"] = sum(1 for _n, d in Gc.degree() if d % 2 == 1)
    return out


def run_detector_with_structural_metrics(image_path: str, detector_fn) -> dict:
    """detector_fn(preprocessed) -> Lattice, e.g. image_io.detect_lattice
    or an ml_lattice_detector instance. Times inference and folds in
    lattice_to_graph_metrics(). Never labeled with ground truth."""
    preprocessed = image_io.preprocess(image_path)
    t0 = time.monotonic()
    try:
        lattice = detector_fn(preprocessed)
        latency_ms = (time.monotonic() - t0) * 1000
    except Exception as e:  # noqa: BLE001
        return {"detector_crashed": True, "crash_type": type(e).__name__, "latency_ms": None}
    m = lattice_to_graph_metrics(preprocessed, lattice)
    m["latency_ms"] = latency_ms
    m["detector_crashed"] = False
    return m


def aggregate_structural(rows: list[dict]) -> dict:
    def _mean(key, rows=rows):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    n_valid_recon = sum(1 for r in rows if r.get("reconstruction_valid"))
    return {
        "n_images": len(rows),
        "mean_n_dots": _mean("n_dots"),
        "mean_connected_components": _mean("connected_components"),
        "mean_odd_degree_nodes": _mean("n_odd_degree_nodes"),
        "mean_edges": _mean("n_edges"),
        "n_reconstruction_valid": n_valid_recon,
        "reconstruction_valid_rate": n_valid_recon / len(rows) if rows else None,
        "mean_latency_ms": _mean("latency_ms"),
    }
