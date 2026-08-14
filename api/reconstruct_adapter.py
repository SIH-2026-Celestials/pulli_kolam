"""Builds a minimal engine.kolam_pattern.KolamPattern from a freshly
detected graph (image -> detector -> graph), so
engine.reconstruction.reconstruct_kolam (which requires a KolamPattern
source, per engine/reconstruction.py's own signature) can run against
an uploaded photo's detection result.

HONESTY NOTE: a real KolamPattern's `trace_points`/`raw_trace` come from
an actual dense CSV polyline (docs/DATA_FORMAT.md). A detected photo has
no such trace -- only the dot positions and inferred edges. This adapter
uses the dot positions themselves as a minimal stand-in trace (one point
per dot, in graph node order) so KolamPattern's own internal consistency
check (`raw_trace.shape[0] == len(trace_points)`) is satisfied, WITHOUT
claiming this is a real polyline trace. `collection="uploaded"` and
`pattern_id=0` mark it as synthetic/non-dataset provenance, not a real
catalog entry -- callers must not present this as if it were a CSV-
backed pattern.
"""

from __future__ import annotations

from collections import Counter

import networkx as nx
import numpy as np

from engine.kolam_pattern import KolamPattern


def build_kolam_pattern_from_graph(G: nx.MultiGraph, dots: set[tuple[int, int]]) -> KolamPattern:
    dot_list = sorted(dots)
    raw_trace = np.array(dot_list, dtype=float) if dot_list else np.empty((0, 2))
    trace_points = tuple((float(x), float(y)) for x, y in dot_list)

    edges = tuple(G.edges())
    edge_multiplicity = dict(Counter(frozenset(e) for e in edges))

    if dot_list:
        xs = [p[0] for p in dot_list]
        ys = [p[1] for p in dot_list]
        bounding_box = (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))
    else:
        bounding_box = (0.0, 0.0, 0.0, 0.0)

    return KolamPattern(
        pattern_id=0,
        collection="uploaded",
        raw_trace=raw_trace,
        trace_points=trace_points,
        dot_points=set(dots),
        edges=edges,
        edge_multiplicity=edge_multiplicity,
        graph=G,
        bounding_box=bounding_box,
    )
