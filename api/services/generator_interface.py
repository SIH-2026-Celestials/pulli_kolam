"""M7 platform integration (follow-up): a framework-independent
Generator interface, so `api/services/generation.py` depends on an
ABSTRACTION rather than importing `engine.learned_generation` (M5)
directly -- the explicit architectural requirement: "the application
must depend on the interface rather than directly importing M5
internals everywhere," so M5 can later be SUPPLEMENTED or replaced by
an M6 V2 implementation of this same Protocol without touching any
caller.

`M5Generator` is the ONLY concrete implementation registered today.
There is deliberately no `M6Generator` in this file -- per this task's
explicit "do NOT implement M6 V2 yet" rule, only the SEAM this
interface creates is built now, not a second implementation to plug
into it. A future M6Generator needs to satisfy exactly the
`Generator` Protocol below and be registered in
`api/services/generation.py`'s `_resolve_production_generator`
(itself unchanged by this file -- it already looks up the ModelVersion
with `status == "production"` from the registry, which is where a
future swap would happen, not here).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class GenerationCandidate:
    """What ANY Generator implementation must produce for one
    candidate -- deliberately the smallest common shape: a real
    `nx.MultiGraph`-backed structural object (`.graph`, `.dot_points`,
    `.is_valid`, `.diagnosis`, `.edge_multiplicity`) plus the seed that
    produced it. `api/services/generation.py` builds everything else
    (representation, analysis, verification, artifacts) FROM this, so a
    future M6Generator only needs to satisfy this shape, not
    reimplement persistence/analysis itself."""

    seed: int
    structural_object: object  # duck-typed GeneratedKolam-shaped object; see module docstring
    restarts_used: int
    repair_edges_applied: int


class Generator(Protocol):
    """The interface `api/services/generation.py` depends on. Any
    implementation must be able to report its own name/version (for
    the ModelVersion this run gets attributed to) and produce candidates
    for a given seed."""

    name: str

    def generate_one(self, seed: int) -> GenerationCandidate: ...


class M5Generator:
    """Wraps `api.generation_service` (the EXISTING lazy M5 loader,
    UNMODIFIED) + `engine.learned_generation.generate_novel_kolam_learned`
    (M5's OWN algorithm, UNMODIFIED) behind the `Generator` Protocol.
    This class adds no new generation logic -- it is purely an adapter."""

    name = "M5"

    def __init__(self):
        from api.generation_service import get_generation_service

        self._m5_service = get_generation_service()

    @property
    def available(self) -> bool:
        return self._m5_service.available

    @property
    def load_error(self) -> "str | None":
        return self._m5_service.load_error

    def generate_one(self, seed: int) -> GenerationCandidate:
        from engine.learned_generation import generate_novel_kolam_learned

        _layout_name, dots = self._m5_service.layout_for_seed(seed)
        run_result = generate_novel_kolam_learned(
            self._m5_service.motif_library, dots, scorer=self._m5_service.scorer, seed=seed,
        )
        return GenerationCandidate(
            seed=seed, structural_object=run_result.candidate,
            restarts_used=len(run_result.restarts), repair_edges_applied=len(run_result.repair_applied),
        )
