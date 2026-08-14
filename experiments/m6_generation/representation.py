"""M6 Phase 2: the sequence-of-placements representation the generator
model predicts and the dataset/rendering pipeline both consume.

Per ARCHITECTURE.md section 10: this is NOT a parallel representation --
it is exactly the ORDER `engine.motifs.induce_motif_set_adaptive` already
produces on a real pattern, flattened to one token per (point, motif,
transform) triple. A M6 "structural sequence" for a pattern is what you
get by running that existing function and recording its output order;
generation is the reverse: sample a plausible such order, then hand it
to the SAME assembly path M5 uses (`engine.generation.build_candidate_graph`)
to get back a real graph.

VOCABULARY: motif shapes are pattern-specific in principle, but a
learnable model needs a FIXED, finite vocabulary. `MotifVocabulary` is
built once (`build_dataset.py`) from the union of D4-canonical motif
shapes seen across the TRAIN split only (never val/test -- leakage
discipline matches split_manifest.json's own pattern-level split), and
frozen for training + generation. An unseen shape at generation time
cannot occur (the model can only emit vocabulary ids), but a real
pattern's motif during dataset-building CAN fall outside a capped
vocabulary (see `build_dataset.py`'s MAX_VOCAB_SIZE) -- that case maps
to UNK_MOTIF_ID, explicitly, not silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.motifs import Motif, MotifPlacement
from engine.symmetry import D4_TRANSFORMS

Point = tuple[int, int]

MAX_GRID = 64  # max lattice coordinate (0..63) any token's x/y can reference -- verified against every real kolam19/kolam29 pattern (largest bounding-box span measured is 55, see build_dataset.py) plus headroom for every `size` preset M6's CLI exposes
TRANSFORM_NAMES: list[str] = sorted(D4_TRANSFORMS)  # deterministic order, index IS the transform_id
N_TRANSFORMS = len(TRANSFORM_NAMES)

# Reserved vocabulary ids -- real motif ids start at FIRST_REAL_MOTIF_ID.
EOS_MOTIF_ID = 0
PAD_MOTIF_ID = 1
UNK_MOTIF_ID = 2
FIRST_REAL_MOTIF_ID = 3


@dataclass
class PlacementToken:
    """One step of the sequence: stamp `motif_id`'s shape at lattice
    point (x, y) under D4 transform `transform_id`. EOS is represented
    by motif_id == EOS_MOTIF_ID (x/y/transform_id are then ignored --
    conventionally 0)."""

    motif_id: int
    x: int
    y: int
    transform_id: int

    def to_dict(self) -> dict:
        return {"motif_id": self.motif_id, "x": self.x, "y": self.y, "transform_id": self.transform_id}

    @staticmethod
    def from_dict(d: dict) -> "PlacementToken":
        return PlacementToken(d["motif_id"], d["x"], d["y"], d["transform_id"])

    @staticmethod
    def eos() -> "PlacementToken":
        return PlacementToken(EOS_MOTIF_ID, 0, 0, 0)


@dataclass
class MotifVocabulary:
    """Frozen, finite motif-shape vocabulary. `id_to_motif[0..2]` are
    reserved (None) for EOS/PAD/UNK; real shapes start at index 3."""

    id_to_motif: "list[Motif | None]"
    motif_to_id: "dict[Motif, int]"

    @property
    def size(self) -> int:
        return len(self.id_to_motif)

    def encode(self, motif: Motif) -> int:
        return self.motif_to_id.get(motif, UNK_MOTIF_ID)

    def decode(self, motif_id: int) -> "Motif | None":
        if 0 <= motif_id < len(self.id_to_motif):
            return self.id_to_motif[motif_id]
        return None

    def to_dict(self) -> dict:
        # Motif = tuple[RelEdge, ...] = tuple[tuple[tuple[int,int],tuple[int,int]], ...]
        # -- JSON needs lists, not tuples; reconstructed on load.
        return {
            "id_to_motif": [
                None if m is None else [[list(a), list(b)] for a, b in m] for m in self.id_to_motif
            ]
        }

    @staticmethod
    def from_dict(d: dict) -> "MotifVocabulary":
        id_to_motif: "list[Motif | None]" = []
        motif_to_id: "dict[Motif, int]" = {}
        for i, entry in enumerate(d["id_to_motif"]):
            if entry is None:
                id_to_motif.append(None)
            else:
                motif = tuple(tuple(tuple(pt) for pt in edge) for edge in entry)
                id_to_motif.append(motif)
                motif_to_id[motif] = i
        return MotifVocabulary(id_to_motif=id_to_motif, motif_to_id=motif_to_id)

    @staticmethod
    def build(motifs: "list[Motif]", max_size: "int | None" = None) -> "MotifVocabulary":
        """`motifs` should already be deduplicated-by-frequency-order
        (most common first) by the caller if `max_size` truncation is to
        keep the most useful shapes -- this function does not itself
        rank by frequency, it just assigns ids in the given order."""
        id_to_motif: "list[Motif | None]" = [None, None, None]  # EOS, PAD, UNK
        motif_to_id: "dict[Motif, int]" = {}
        for m in motifs:
            if m in motif_to_id:
                continue
            if max_size is not None and len(id_to_motif) >= max_size:
                break
            motif_to_id[m] = len(id_to_motif)
            id_to_motif.append(m)
        return MotifVocabulary(id_to_motif=id_to_motif, motif_to_id=motif_to_id)


def sequence_from_placements(placements: "list[MotifPlacement]", vocab: MotifVocabulary) -> "list[PlacementToken]":
    """Flatten an ordered MotifPlacement list (as returned by
    engine.motifs.induce_motif_set_adaptive, selection order preserved)
    into one PlacementToken per (point, motif, transform) triple. Points
    outside [0, MAX_GRID) are skipped -- CALLER'S RESPONSIBILITY to pass
    an already ORIGIN-NORMALIZED graph/placements first (real
    KolamPattern.dot_points are centered near (0, 0) with NEGATIVE
    coordinates, e.g. kolam19#2 spans -17..17 -- build_dataset.py's
    `_normalize_to_origin` does this shift before calling this function;
    calling this directly on a raw, un-normalized pattern will silently
    drop most points, which is why build_dataset.py always normalizes
    first)."""
    tokens: "list[PlacementToken]" = []
    for placement in placements:
        motif_id = vocab.encode(placement.motif)
        for point in placement.points:
            x, y = point
            if not (0 <= x < MAX_GRID and 0 <= y < MAX_GRID):
                continue
            t_name = placement.transforms.get(point, "identity")
            transform_id = TRANSFORM_NAMES.index(t_name)
            tokens.append(PlacementToken(motif_id, x, y, transform_id))
    return tokens


def placements_from_sequence(tokens: "list[PlacementToken]", vocab: MotifVocabulary) -> "list[MotifPlacement]":
    """Inverse of sequence_from_placements: one MotifPlacement per token
    (single-point placements -- engine.generation.build_candidate_graph
    accepts this the same way it accepts multi-point placements, since
    it stamps each placement's points independently). UNK/EOS/PAD tokens
    (motif_id < FIRST_REAL_MOTIF_ID, or a motif_id whose vocabulary
    entry is None) are skipped, not silently converted into a
    placement -- a generated sequence that emits UNK contributes nothing
    structural at that step, which is the honest behavior (never invent
    a shape the vocabulary doesn't have)."""
    placements: "list[MotifPlacement]" = []
    for tok in tokens:
        if tok.motif_id == EOS_MOTIF_ID:
            break
        motif = vocab.decode(tok.motif_id)
        if motif is None:  # PAD or UNK or out-of-range id
            continue
        point = (tok.x, tok.y)
        t_name = TRANSFORM_NAMES[tok.transform_id] if 0 <= tok.transform_id < N_TRANSFORMS else "identity"
        transforms = {} if t_name == "identity" else {point: t_name}
        placements.append(MotifPlacement(motif=motif, points=[point], transforms=transforms))
    return placements


@dataclass
class GenerationConfig:
    """The conditioning surface the generator model is trained to
    respect (Phase 4's explicit requirement: grid size, symmetry,
    complexity, density, seed). Plain dataclass, JSON-serializable,
    shared between train.py (as a per-example condition vector) and
    generate.py (as the CLI's parsed arguments)."""

    grid_width: int
    grid_height: int
    symmetry: str  # "none" | "rotational4" | "auto" -- see model.py's conditioning embedding
    complexity: float  # in [0, 1]
    density: float  # in [0, 1]
    seed: "int | None" = None

    def to_dict(self) -> dict:
        return {
            "grid_width": self.grid_width, "grid_height": self.grid_height,
            "symmetry": self.symmetry, "complexity": self.complexity,
            "density": self.density, "seed": self.seed,
        }

    @staticmethod
    def from_dict(d: dict) -> "GenerationConfig":
        return GenerationConfig(**d)
