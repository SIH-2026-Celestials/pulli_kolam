"""API-safe serialization helpers. Nothing here returns a NetworkX
object, a MotifPlacement, or any other Python-specific engine type
directly -- every function returns plain dict/list/str/int/float,
JSON-serializable as-is. Kept separate from api/main.py so the
"no NetworkX leaks" rule has one obvious place to audit.
"""

from __future__ import annotations

import networkx as nx


def graph_to_json(G: nx.MultiGraph) -> dict:
    """Counts only, matching the task's specified /analyze response
    shape exactly ({"nodes": ..., "edges": ..., "distinct_edges": ...})
    -- node/edge coordinate lists are NOT included here since the dots
    are already returned in the response's top-level `dots`/`detections`
    field, and a dense kolam29-scale pattern's full edge list (hundreds
    of entries) would needlessly bloat every /analyze response."""
    distinct = {frozenset(e) for e in G.edges()}
    return {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "distinct_edges": len(distinct)}


def validity_to_json(validity_result: dict) -> dict:
    # engine.validity.check_validity's own return value is already a
    # plain dict of primitives -- pass through explicitly (not **kwargs
    # blind-forward) so any future non-primitive field added there is
    # caught here, not silently leaked to the API.
    return {
        "is_eulerian_circuit": bool(validity_result.get("is_eulerian_circuit")),
        "has_eulerian_path": bool(validity_result.get("has_eulerian_path")),
        "connected_components": int(validity_result.get("connected_components", 0)),
        "largest_component_covers_all_nodes": bool(validity_result.get("largest_component_covers_all_nodes")),
    }


def motif_placements_to_json(placements: list) -> dict:
    return {
        "motif_count": len(placements),
        "placements": [
            {"n_points": len(p.points), "motif_edge_count": len(p.motif)}
            for p in placements
        ],
    }


def reconstruction_to_json(result) -> dict:
    return {
        "is_valid": bool(result.is_valid),
        "motif_edges": len(result.motif_edges),
        "residual_edges": len(result.residual_edges),
        "capped_excess_pairs": len(result.capped_excess),
        "connectivity": {
            "connected_components": result.connectivity["connected_components"],
            "largest_component_covers_all_nodes": result.connectivity["largest_component_covers_all_nodes"],
        },
        "validity": validity_to_json(result.validity_result),
    }
