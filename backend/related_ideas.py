from __future__ import annotations
from backend.models.schemas import RelatedIdea

SAMPLE_RELATED_IDEAS = [
    RelatedIdea(
        id="idea_1",
        title="D4 Symmetrical 7x7 Loop Kolam",
        description="Classic central loop design with four-fold rotational symmetry and smooth continuous curves.",
        thumbnail_url="/static/sample_ideas/kolam19-0.jpg",
        grid_size="7×7",
        symmetry="D4 Dihedral",
    ),
    RelatedIdea(
        id="idea_2",
        title="Double-Stranded Star Pattern",
        description="Complex interlocking kambi strokes forming an 8-pointed motif around a dense grid.",
        thumbnail_url="/static/sample_ideas/kolam19-1.jpg",
        grid_size="9×9",
        symmetry="D4 Dihedral",
    ),
    RelatedIdea(
        id="idea_3",
        title="Corner-Anchored Brahma Granthi",
        description="Traditional continuous single-stroke knot pattern preserving Eulerian circuit rules.",
        thumbnail_url="/static/sample_ideas/kolam19-2.jpg",
        grid_size="5×5",
        symmetry="D2 Radial",
    ),
    RelatedIdea(
        id="idea_4",
        title="Rhombic Pulli Lattice Variant",
        description="Diamond-grid dot layout featuring floral crossing motifs at all interior nodes.",
        thumbnail_url="/static/sample_ideas/kolam19-3.jpg",
        grid_size="7×7",
        symmetry="D4 Dihedral",
    ),
]


def get_related_ideas(grid_size: str, symmetry_group: str) -> list[RelatedIdea]:
    """Return 3-4 curated related Kolam ideas for a given grid size and symmetry group."""
    # In full implementation, filter/rank ideas matching grid size & symmetry
    return SAMPLE_RELATED_IDEAS
