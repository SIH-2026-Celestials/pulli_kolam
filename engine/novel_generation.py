"""M3.7: novel structural generation.

THE DISTINCTION THIS MODULE EXISTS TO ENFORCE (see docs/RECONSTRUCTION.md
and docs/MOTIF_SELECTION.md): `engine.reconstruction.reconstruct_kolam`
answers "can THIS SOURCE be rebuilt," and does so by copying the exact
source residual edges back in -- it can only ever reproduce something
that already exists. This module answers a genuinely different
question: given a MOTIF LIBRARY (a set of abstract, reusable relative-
edge shapes -- engine.motifs.Motif, NOT engine.motifs.MotifPlacement,
which is tied to specific source coordinates) and a NEW dot layout the
library was never discovered from, can the library alone produce a
valid structural candidate?

There is no source graph anywhere in this module's placement logic --
select_novel_placements never receives one, so there is structurally
nothing for it to copy a residual FROM. This is the strongest possible
guarantee of the source-reconstruction/novel-generation distinction: not
"we chose not to copy," but "there was never anything available to copy."

PIPELINE (matches the task's own diagram):
  motif library + new dot layout
        -> select_novel_placements   (motif placement + multiplicity cap)
        -> engine.generation.generate_kolam (UNCHANGED, reused as-is:
           MultiGraph construction, Eulerian validity, deterministic
           trace -- exactly the M3 pipeline, pointed at placements that
           happen to have no source provenance instead of induced ones)
        -> GeneratedKolam candidate

"Multiplicity constraints" here means something different from M3.6's
source-relative check (there is no per-edge source count to check
against on an unseen layout) -- it is a flat structural cap,
`max_multiplicity`, informed by the real, verified dataset-wide fact
(docs/DATA_FORMAT.md) that source patterns only ever exhibit strand
multiplicity 1 or 2 on any edge, never more. Default 2, the observed
real-data ceiling, not an arbitrary number.

CONNECTIVITY-AWARE SCORING (added alongside docs/M4_2_CONNECTIVITY_EVALUATION.md,
opt-in via `connectivity_aware=True`, default False): the ORIGINAL
scoring above (`_novel_score`) evaluates each candidate placement in
complete isolation -- it has no notion of which OTHER dots are already
part of the same connected structure, so a benchmark of 120 candidates
measured 0/120 valid, fragmenting into anywhere from 2 to 369 connected
components. `_connectivity_effect`/`_connectivity_score` add an
ADDITIVE term to the SAME per-candidate score, using an incremental
union-find (`_UnionFind`) to reward placements that merge two
already-real components or extend one into a fresh dot, without
changing `_novel_score` itself, the multiplicity cap, or the underlying
single-pass greedy search structure. See that document for the measured
effect (a real reduction in fragmentation; validity remains the honest,
harder bar -- read the document, do not assume from this docstring
alone).
"""

from __future__ import annotations

from collections import Counter

from engine.generated_kolam import GeneratedKolam
from engine.generation import generate_kolam
from engine.kolam_pattern import KolamPattern
from engine.motifs import PLACEMENT_COST, EDGE_UNIT_COST, Motif, MotifPlacement, Point, interior_points
from engine.symmetry import D4_TRANSFORMS, apply_transform

DEFAULT_MAX_MULTIPLICITY = 2  # verified dataset-wide ceiling, see docs/DATA_FORMAT.md
DEFAULT_MAX_PLACEMENTS = 3000  # safety ceiling only, not a target -- see docs/NOVEL_GENERATION.md

# Connectivity-aware scoring constants (see docs/M4_2_CONNECTIVITY_EVALUATION.md
# for the experiment this was built for, its measured effect, and how
# these specific weights were chosen -- not guessed). Same EDGE_UNIT_COST
# currency _novel_score already uses, so the two terms are additive on a
# common scale, not two incompatible objectives bolted together.
#
# MERGE_REAL_REWARD is the largest: joining two components that ALREADY
# have real structure is the single biggest lever toward eventually
# covering the whole layout in one component, which is exactly what
# check_validity's hard gate requires.
#
# NEW_ISOLATED_PENALTY is deliberately SMALL, not symmetric with the
# rewards -- a light sensitivity check (see docs/M4_2_CONNECTIVITY_EVALUATION.md
# section 4) found that a penalty anywhere near the reward's own scale
# makes the single-pass greedy search collapse to near-zero placements
# or far WORSE fragmentation than the unweighted baseline: a fresh
# isolated fragment is not pure waste in a single forward pass -- it is
# the ONLY raw material a later candidate can ever merge into something
# real (`_connectivity_effect`'s "n_merge_real" case requires two
# already-existing size>1 components to merge; nothing to merge if
# fragment creation is suppressed). This small weight still lets the
# mechanism the task asked for do something measurable (see
# tests/test_connectivity_scoring.py) without starving the merge
# mechanism of the fragments it depends on.
CONNECTIVITY_MERGE_REAL_REWARD = 8 * EDGE_UNIT_COST
CONNECTIVITY_EXTEND_REWARD = 4 * EDGE_UNIT_COST
CONNECTIVITY_NEW_ISOLATED_PENALTY = 0.05 * EDGE_UNIT_COST

# Parity-aware scoring constant (see docs/M4_2_PARITY_EVALUATION.md).
# Same EDGE_UNIT_COST currency as every other term: one net odd-degree
# node removed is worth exactly one PARITY_IMPROVEMENT_WEIGHT, symmetric
# in both directions (a placement that removes 2 odd nodes is rewarded
# 2x; one that adds 2 is penalized 2x) -- unlike the connectivity
# isolation penalty, no sensitivity collapse was found at this scale
# (see docs/M4_2_PARITY_EVALUATION.md Section 4 for the calibration
# check performed before settling on this value), so this uses a plain,
# symmetric 1x weight rather than a deliberately small one.
PARITY_IMPROVEMENT_WEIGHT = 1 * EDGE_UNIT_COST


class _UnionFind:
    """Minimal union-find (disjoint-set) over a fixed universe of dot
    points. Used ONLY as an efficient INCREMENTAL view of which dots are
    already connected as select_novel_placements accepts placements one
    at a time -- NOT a replacement for engine.validity.check_validity's
    authoritative connectivity check on the final assembled graph (that
    still runs, unmodified, on the graph engine.generation.generate_kolam
    builds). Recomputing nx.connected_components from scratch for every
    one of potentially tens of thousands of candidate evaluations would
    be needlessly expensive; find()/union() here are near-O(1) amortized."""

    def __init__(self, points):
        self._parent = {p: p for p in points}
        self._size = {p: 1 for p in points}

    def find(self, x: Point) -> Point:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:  # path compression
            self._parent[x], x = root, self._parent[x]
        return root

    def size(self, node: Point) -> int:
        return self._size[self.find(node)]

    def union(self, a: Point, b: Point) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        self._size[ra] += self._size[rb]


def _stamp_contribution(motif: Motif, point: Point, transform: str, dots: set[Point]) -> Counter:
    """Same computation as engine.motif_selection.simulate_placement_contribution,
    duplicated here at module scope only to avoid a cross-module private
    import for something this small; identical semantics (edges landing
    outside `dots` are dropped, multiplicity within one stamp is counted
    exactly)."""
    rel_edges = motif if transform == "identity" else apply_transform(transform, motif)
    contribution: Counter = Counter()
    cx, cy = point
    for (dx1, dy1), (dx2, dy2) in rel_edges:
        a = (cx + dx1, cy + dy1)
        b = (cx + dx2, cy + dy2)
        if a in dots and b in dots:
            contribution[frozenset({a, b})] += 1
    return contribution


def extract_motif_library(placements: list[MotifPlacement]) -> list[Motif]:
    """The abstraction step: strips MotifPlacement objects (motif shape +
    SPECIFIC source coordinates + transforms) down to just the distinct
    motif SHAPES -- the reusable, source-independent part. This is what
    makes a "motif library": rules with no memory of where they came
    from, safe to hand to a layout that never produced them."""
    seen: dict[Motif, None] = {}
    for p in placements:
        seen.setdefault(p.motif, None)
    return list(seen.keys())


def _novel_score(motif: Motif, contribution: Counter, degree_before: Counter) -> float:
    """Scoring for placement onto an UNSEEN layout, deliberately NOT a
    reuse of engine.motif_selection._parity_delta as-is: that function
    treats every touched node's PRE-EXISTING degree as a baseline to
    protect, which is correct when there is already a partial
    reconstruction in progress (M3.6), but wrong here -- on a brand-new
    layout every node starts at degree 0, and _parity_delta would score
    the very FIRST edge ever placed as "breaking" two nodes from even
    (0) to odd (1), permanently blocking any placement from ever
    bootstrapping a structure at all (found by direct testing, not
    theorized: the naive reuse produced zero placements on every input).

    Fix: a node touched for the first time (degree_before == 0) has no
    parity state to protect -- giving it any structure at all is pure
    growth, not a tradeoff. Only nodes that already have degree > 0
    (touched by a PREVIOUS accepted placement) get the parity
    reward/penalty treatment."""
    touched: set[Point] = set()
    for edge in contribution:
        a, b = tuple(edge)
        touched.add(a)
        touched.add(b)

    growth = 0
    parity = 0
    for node in touched:
        deg_before = degree_before.get(node, 0)
        if deg_before == 0:
            growth += 1
            continue
        deg_change = sum(count for edge, count in contribution.items() if node in edge)
        before_odd = deg_before % 2 == 1
        after_odd = (deg_before + deg_change) % 2 == 1
        if before_odd and not after_odd:
            parity += 1
        elif not before_odd and after_odd:
            parity -= 1

    complexity_cost = len(motif) * EDGE_UNIT_COST + PLACEMENT_COST
    return EDGE_UNIT_COST * (growth + parity) - complexity_cost


def _connectivity_effect(uf: _UnionFind, contribution: Counter) -> dict:
    """Classify the connectivity effect ONE candidate's `contribution`
    (its stamped edges, from _stamp_contribution) would have on the
    CURRENT global `uf` state, WITHOUT mutating it -- a pure trial. A
    placement's motif can contain several edges spanning several
    component pairs at once (explicitly required: "do not assume a
    placement corresponds to one edge"); each DISTINCT pair of
    components an edge would newly bridge is counted once via a small
    local (this-call-only) merge map -- a second edge between the same
    two components in the same placement is redundant for connectivity
    purposes (though it still matters for multiplicity elsewhere, which
    this function does not touch).

    Every edge crossing two different existing components is classified
    by the ORIGINAL (pre-this-placement) size of each side:
      n_merge_real        : both sides already belong to a component of
                             size > 1 -- joining two REAL structures,
                             the single biggest lever toward eventual
                             full connectivity.
      n_extend             : one side is an untouched singleton, the
                             other already belongs to a component of
                             size > 1 -- growing an existing structure
                             by one dot.
      n_new_isolated_pair   : both sides are untouched singletons --
                             this creates a brand-new, small, isolated
                             2+-node fragment: it does NOT reduce the
                             total number of fragments the eventual
                             candidate needs to merge into one, so it is
                             treated as a cost, not a gain.
    `same_component_edges` counts edges that land entirely inside a
    component that is (after any earlier edges in this same placement
    are accounted for) already unified -- these have zero connectivity
    effect either way; they are reported for completeness/debugging,
    not scored.
    """
    local_root: dict = {}

    def eff_root(root):
        while root in local_root:
            root = local_root[root]
        return root

    n_merge_real = n_extend = n_new_isolated_pair = same_component_edges = 0

    for edge in contribution:
        a, b = tuple(edge)
        ra, rb = uf.find(a), uf.find(b)
        era, erb = eff_root(ra), eff_root(rb)
        if era == erb:
            same_component_edges += 1
            continue
        sa, sb = uf.size(a), uf.size(b)
        if sa > 1 and sb > 1:
            n_merge_real += 1
        elif sa == 1 and sb == 1:
            n_new_isolated_pair += 1
        else:
            n_extend += 1
        local_root[erb] = era

    return {
        "n_merge_real": n_merge_real,
        "n_extend": n_extend,
        "n_new_isolated_pair": n_new_isolated_pair,
        "same_component_edges": same_component_edges,
    }


def _connectivity_score(effect: dict, penalize_new_isolated: bool) -> float:
    """Combine _connectivity_effect's classification into one additive
    score term, same EDGE_UNIT_COST-scaled currency _novel_score uses.
    Positive = net good for eventual full connectivity; negative = net
    bad (creates more fragmentation than it resolves).

    `penalize_new_isolated` MUST be False while no real (size > 1)
    component exists anywhere yet -- otherwise the very first placement
    ever accepted on a fresh layout (which, by definition of an
    all-singleton union-find, always "creates a new isolated pair") gets
    penalized for the one thing every candidate must eventually do:
    seed the first component. This is the exact bootstrap problem
    `_novel_score`'s own docstring already documents and fixes for the
    parity term (see that function's "Fix" paragraph) -- reproduced
    here for connectivity if this guard is dropped (verified directly:
    without it, select_novel_placements returns ZERO placements on every
    input, identical failure signature to the original bootstrap bug).
    Once real structure exists ELSEWHERE, a placement that starts yet
    another disconnected island IS a genuine cost (more fragments
    competing for the same merge budget), so the penalty applies from
    then on."""
    score = CONNECTIVITY_MERGE_REAL_REWARD * effect["n_merge_real"] + CONNECTIVITY_EXTEND_REWARD * effect["n_extend"]
    if penalize_new_isolated:
        score -= CONNECTIVITY_NEW_ISOLATED_PENALTY * effect["n_new_isolated_pair"]
    return score


def _parity_effect(degree_before: Counter, contribution: Counter) -> dict:
    """Classify ONE candidate's `contribution` effect on the GLOBAL count
    of odd-degree nodes in the CURRENT accumulated graph state
    (`degree_before`) -- NOT a count of the candidate's own edges (see
    docs/M4_2_PARITY_EVALUATION.md's explicit warning against that
    mistake). Parity is a per-node property; a node's parity can only
    change if THIS placement changes its degree, so it is mathematically
    exact (not an approximation) to scan only the nodes `contribution`
    touches -- every untouched node's degree, and therefore its parity,
    is provably unchanged.

    `deg_change` sums ALL of this placement's edge counts touching a
    node, exactly like `_novel_score`'s own `deg_change` computation --
    this is what makes repeated-strand / multi-edge placements handled
    correctly for free: an odd number of new parallel strands toggles
    the endpoint's parity (deg_change odd -> deg_before/deg_after have
    different parity), an even number preserves it (deg_change even ->
    same parity), which is exactly the arithmetic `(deg_before +
    deg_change) % 2` already performs -- no separate strand-parity
    special case is needed.

    Returns:
      odd_before  : count of touched nodes that were ALREADY odd-degree
                    before this placement.
      odd_after   : count of those same nodes that WOULD be odd-degree
                    after this placement.
      delta_odd   : odd_after - odd_before -- the GLOBAL change in
                    odd-degree-node count this placement would cause.
                    Negative = fewer odd nodes (moves toward Eulerian
                    validity); zero = neutral; positive = worse.
    """
    touched: set[Point] = set()
    for edge in contribution:
        a, b = tuple(edge)
        touched.add(a)
        touched.add(b)

    odd_before = odd_after = 0
    for node in touched:
        deg_before = degree_before.get(node, 0)
        deg_change = sum(count for edge, count in contribution.items() if node in edge)
        deg_after = deg_before + deg_change
        if deg_before % 2 == 1:
            odd_before += 1
        if deg_after % 2 == 1:
            odd_after += 1

    return {"odd_before": odd_before, "odd_after": odd_after, "delta_odd": odd_after - odd_before}


def _parity_score(effect: dict, neutral: bool) -> float:
    """Additive score term, same EDGE_UNIT_COST currency every other
    term in this module uses. delta_odd < 0 (fewer odd nodes) scores
    positive; delta_odd == 0 scores exactly 0 (neutral, per the task's
    explicit requirement); delta_odd > 0 scores negative.

    `neutral` MUST be True while no real (size > 1) structure exists
    anywhere yet -- verified empirically to be NECESSARY, not merely
    precautionary (see docs/M4_2_PARITY_EVALUATION.md Section 4): an
    unconditional parity penalty reproduces a total-collapse bootstrap
    failure (select_novel_placements returns ZERO placements on every
    tested input), the same failure SHAPE `_connectivity_score`'s own
    bootstrap guard already had to solve, via a different mechanism.
    Reason: on an empty graph, EVERY touched node has `degree_before ==
    0` (even), so `odd_before` is always 0 for the very first placement
    -- but many real motifs leave at least one touched node at ODD
    degree after just one stamp (e.g. an open path's two endpoints), so
    `delta_odd > 0` for the FIRST candidate of many real motif shapes,
    and an unconditional penalty rejects it. Since nothing is ever
    accepted, no structure ever exists, so EVERY subsequent candidate is
    also evaluated from the same all-singleton state -- the collapse is
    total, not just a slow start. `neutral=True` (this task's own
    literal instruction: "for an empty/initial state, parity scoring
    should be neutral") makes the term contribute exactly 0 -- neither
    reward nor penalty -- until real structure exists to protect."""
    if neutral:
        return 0.0
    return -PARITY_IMPROVEMENT_WEIGHT * effect["delta_odd"]


def select_novel_placements(
    motif_library: list[Motif],
    dot_points: set[Point],
    max_multiplicity: int = DEFAULT_MAX_MULTIPLICITY,
    max_placements: int = DEFAULT_MAX_PLACEMENTS,
    connectivity_aware: bool = False,
    parity_aware: bool = False,
) -> list[MotifPlacement]:
    """Greedy placement of `motif_library`'s shapes onto `dot_points`,
    with NO source graph involved anywhere -- see module docstring.

    Every (motif, point, D4 transform) combination is a candidate.
    Scoring (_novel_score) rewards growing the structure into untouched
    dots and improving parity at already-touched ones -- moving the
    CANDIDATE toward a valid Eulerian structure is the only meaningful
    goal when there is no source recall to optimize for -- minus the
    same EDGE_UNIT_COST/PLACEMENT_COST complexity currency used
    everywhere else in this project. A candidate is rejected outright
    (never clipped) if it would push any touched edge's strand count
    above `max_multiplicity` -- the flat, source-independent
    multiplicity constraint this module uses instead of M3.6's per-edge
    source count.

    `max_placements` is a hard safety ceiling (there is no natural
    "fully covered" stopping condition on a new layout the way there is
    against a known source), not a target -- matches the same "ceiling,
    not target" convention engine.motifs.induce_motif_set_adaptive
    already established.

    `connectivity_aware` (default False, preserving the exact original
    M3.7 behavior for every existing caller/test): when True, each
    candidate's score additionally includes `_connectivity_score`, which
    rewards a placement for MERGING two already-real (size > 1)
    components or extending an existing one into an untouched dot, and
    PENALIZES a placement that creates a brand-new isolated 2+-node
    fragment (see `_connectivity_effect`'s docstring). This is an
    ADDITIVE term on top of the existing growth/parity objective, not a
    replacement for it -- both still gate the SAME single accept/reject
    decision (`score <= 0: continue`), and nothing about which
    candidates are physically eligible (the multiplicity-cap rejection
    above) changes. See docs/M4_2_CONNECTIVITY_EVALUATION.md for the
    experiment this was built for and its measured effect on validity.

    `parity_aware` (default False): when True, each candidate's score
    ADDITIONALLY includes `_parity_score`, which rewards a placement for
    reducing the GLOBAL count of odd-degree nodes in the accumulated
    graph and penalizes one that increases it (see `_parity_effect`'s
    docstring -- this is a distinct, more complete signal than
    `_novel_score`'s own local per-node parity term, which deliberately
    ignores the parity of a node touched for the first time; see
    docs/M4_2_PARITY_EVALUATION.md). Fully independent of
    `connectivity_aware` -- either flag may be used alone or combined;
    both are purely additive terms on the same `score`.
    """
    dots = set(dot_points)
    interior = interior_points(dots, radius=1)

    accumulated: Counter = Counter()
    degree: Counter = Counter()
    selected: dict[tuple[Motif, str], dict] = {}  # (motif, transform) -> {"points": [...], "edges": set}
    n_placed = 0
    uf = _UnionFind(dots) if connectivity_aware else None
    any_real_structure_exists = False  # see _connectivity_score's bootstrap-guard docstring

    # Fixed, deterministic candidate order (sorted points x library
    # motifs x D4 transforms) so results are reproducible across runs.
    candidate_keys = [
        (point, motif, transform)
        for point in sorted(interior)
        for motif in motif_library
        for transform in sorted(D4_TRANSFORMS)
    ]

    for point, motif, transform in candidate_keys:
        if n_placed >= max_placements:
            break
        contribution = _stamp_contribution(motif, point, transform, dots)
        if not contribution:
            continue
        if any(accumulated.get(e, 0) + c > max_multiplicity for e, c in contribution.items()):
            continue  # reject outright -- never clip, same discipline as M3.6

        score = _novel_score(motif, contribution, degree)
        # Unlike M3.6, there is no "recall against a known source" term
        # at all here -- growth + parity improvement net of complexity is the
        # WHOLE objective, since there is nothing else to optimize for
        # on a layout with no ground truth. connectivity_aware adds ONE
        # more additive term to that same objective (see docstring above).
        if connectivity_aware:
            effect = _connectivity_effect(uf, contribution)
            score += _connectivity_score(effect, penalize_new_isolated=any_real_structure_exists)
        if parity_aware:
            score += _parity_score(_parity_effect(degree, contribution), neutral=not any_real_structure_exists)
        if score <= 0:
            continue

        for edge, count in contribution.items():
            accumulated[edge] += count
            a, b = tuple(edge)
            degree[a] += count
            degree[b] += count
            if connectivity_aware:
                uf.union(a, b)
        key = (motif, transform)
        entry = selected.setdefault(key, {"points": [], "edges": set()})
        entry["points"].append(point)
        entry["edges"] |= set(contribution.keys())
        n_placed += 1
        any_real_structure_exists = True  # at least one edge now exists somewhere

    placements = []
    for (motif, transform), entry in selected.items():
        transforms = {} if transform == "identity" else {p: transform for p in entry["points"]}
        placements.append(
            MotifPlacement(motif=motif, points=entry["points"], transforms=transforms, new_edges=entry["edges"])
        )
    return placements


def generate_novel_kolam(
    motif_library: list[Motif],
    dot_points: set[Point],
    max_multiplicity: int = DEFAULT_MAX_MULTIPLICITY,
    connectivity_aware: bool = False,
    parity_aware: bool = False,
) -> GeneratedKolam:
    """The full M3.7 pipeline: motif library + new dot layout ->
    select_novel_placements -> engine.generation.generate_kolam
    (unmodified). No source pattern is ever passed in or referenced --
    there is nothing for this to reconstruct FROM, only a rule set and a
    target lattice. See module docstring for why this is the strongest
    available guarantee of the source-reconstruction/novel-generation
    distinction.

    `connectivity_aware`/`parity_aware` (both default False) are passed
    straight through to select_novel_placements -- see that function's
    docstring, docs/M4_2_CONNECTIVITY_EVALUATION.md, and
    docs/M4_2_PARITY_EVALUATION.md."""
    placements = select_novel_placements(
        motif_library,
        dot_points,
        max_multiplicity,
        connectivity_aware=connectivity_aware,
        parity_aware=parity_aware,
    )
    return generate_kolam(placements, dot_points)


def duplicates_source(candidate_graph, source: KolamPattern) -> bool | None:
    """Does `candidate_graph`'s edge multiset exactly reproduce `source`?
    Returns None (not a meaningful comparison) if the candidate's node
    set isn't even the same as source's dot layout -- a candidate on a
    genuinely different layout cannot be a "duplicate" in any literal
    sense, and reporting False there would misleadingly suggest a close
    call that was actually never possible."""
    if set(candidate_graph.nodes()) != source.dot_points:
        return None
    candidate_mult = Counter(frozenset(e) for e in candidate_graph.edges())
    source_mult = Counter(frozenset(e) for e in source.graph.edges())
    return candidate_mult == source_mult
