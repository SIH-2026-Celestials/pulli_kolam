from __future__ import annotations

import sys
import os
import uuid
import math
import networkx as nx

# Add project root to sys.path so engine can be imported seamlessly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine.image_io import preprocess, detect_lattice, trace_path, build_graph
from engine.validity import check_validity, is_valid_single_stroke
from engine.symmetry import analyze_symmetry
from engine.motifs import induce_motif_set_adaptive
from backend.models.schemas import (
    AnalysisResult,
    SymmetrySummary,
    MotifSummary,
    ValiditySummary,
)
from backend.related_ideas import get_related_ideas


def analyze_kolam_image(image_path: str, specifications: str | None = None, public_url: str | None = None) -> AnalysisResult:
    """Analyze a kolam image using the PULLI engine.
    
    1. Preprocess & detect lattice dots.
    2. Skeletonize & trace stroke paths -> MultiGraph.
    3. Run symmetry analysis (D4 group).
    4. Run motif induction.
    5. Run Eulerian single-stroke validity check.
    """
    analysis_id = uuid.uuid4().hex

    # Execute engine pipeline
    preprocessed = preprocess(image_path)
    lattice = detect_lattice(preprocessed)

    dot_count = len(lattice.lattice_coords)

    # Handle low contrast or line-only images where dot detection finds fewer than 3 dots
    if dot_count < 3:
        return AnalysisResult(
            analysis_id=analysis_id,
            image_url=public_url,
            dot_count=dot_count,
            grid_size="0×0",
            symmetry=SymmetrySummary(
                group="None",
                coverage=0.0,
                dominant_transform="none",
                is_symmetric=False,
            ),
            motifs=[],
            validity=ValiditySummary(
                is_valid=False,
                connected_components=0,
                is_eulerian_circuit=False,
                has_eulerian_path=False,
                largest_component_covers_all_nodes=False,
            ),
            bounding_box=(0.0, 0.0, 0.0, 0.0),
            related_ideas=get_related_ideas("5×5", "D4"),
            specifications=specifications,
            status="no_dots_detected",
            message=(
                "No visible dot lattice (Pulli) markers detected in the uploaded image. "
                "Ensure the photo has clear, well-lit dot markers."
            ),
        )

    # Calculate grid size estimation
    xs = [pt[0] for pt in lattice.lattice_coords]
    ys = [pt[1] for pt in lattice.lattice_coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width_dots = (max_x - min_x) + 1
    height_dots = (max_y - min_y) + 1
    grid_size = f"{width_dots}×{height_dots}"
    bounding_box = (float(min_x), float(min_y), float(max_x), float(max_y))

    # Trace strokes & build graph
    edges = trace_path(preprocessed, lattice)
    G = nx.MultiGraph()
    G.add_nodes_from(lattice.lattice_coords)
    for a, b in edges:
        G.add_edge(a, b)

    dots_set = set(lattice.lattice_coords)

    # Symmetry analysis
    try:
        motif_canon, cov_frac, transform_per_point = analyze_symmetry(G, dots=dots_set, radius=1)
        dom_transform = "identity"
        if transform_per_point:
            from collections import Counter
            dom_transform = Counter(transform_per_point.values()).most_common(1)[0][0]
        
        symmetry_info = SymmetrySummary(
            group="D4 Dihedral" if cov_frac > 0.3 else "D2 Bilateral",
            coverage=round(cov_frac, 4),
            dominant_transform=dom_transform,
            is_symmetric=cov_frac > 0.3,
        )
    except Exception:
        symmetry_info = SymmetrySummary(
            group="Unclassified",
            coverage=0.0,
            dominant_transform="identity",
            is_symmetric=False,
        )

    # Motif induction
    motifs_summary = []
    try:
        induced_motifs, _residual = induce_motif_set_adaptive(G, dots_set)
        for idx, (motif, placements) in enumerate(induced_motifs.items(), start=1):
            motifs_summary.append(
                MotifSummary(
                    id=idx,
                    edge_count=len(motif),
                    frequency=len(placements),
                    label=f"Motif Pattern #{idx} ({len(motif)} edges)",
                )
            )
    except Exception:
        pass

    # Validity checking
    try:
        val_dict = check_validity(G)
        is_valid = is_valid_single_stroke(G)
        validity_info = ValiditySummary(
            is_valid=is_valid,
            connected_components=val_dict.get("connected_components", 1),
            is_eulerian_circuit=val_dict.get("is_eulerian_circuit", False),
            has_eulerian_path=val_dict.get("has_eulerian_path", False),
            largest_component_covers_all_nodes=val_dict.get("largest_component_covers_all_nodes", False),
        )
    except Exception:
        validity_info = ValiditySummary(
            is_valid=False,
            connected_components=0,
            is_eulerian_circuit=False,
            has_eulerian_path=False,
            largest_component_covers_all_nodes=False,
        )

    related_ideas = get_related_ideas(grid_size, symmetry_info.group)

    return AnalysisResult(
        analysis_id=analysis_id,
        image_url=public_url,
        dot_count=dot_count,
        grid_size=grid_size,
        symmetry=symmetry_info,
        motifs=motifs_summary,
        validity=validity_info,
        bounding_box=bounding_box,
        related_ideas=related_ideas,
        specifications=specifications,
        status="ok",
    )
