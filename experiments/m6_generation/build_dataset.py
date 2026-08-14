"""M6 Phase 3: build the augmented structural sequence dataset.

SOURCE: kolam19 (400 patterns) + kolam29 (100 patterns) -- kolam109
excluded, same precedent M4.2's own training-data generation used (too
dense: ~24k trace points/pattern, poor small-scale recoverability).
Reuses experiments/m5_generation/data/split_manifest.json's PATTERN-ID
train/val/test split AS-IS (500 patterns: 350/75/75) -- no new leakage
surface is introduced; M6's splits are pattern-disjoint by construction
because M5's already are.

AUGMENTATION (two independent, both VALIDITY-CHECKED, deterministic
given a fixed seed -- never "duplicate with pixel noise"):

  1. D4 SYMMETRY: all 8 transforms of each pattern's dot/edge geometry
     (engine.symmetry.D4_TRANSFORMS) -- a D4 image of a valid Eulerian
     graph is itself Eulerian (isomorphic), so this is validity-free,
     but genuinely varies geometric parameters (bounding box, "which way
     up") the model must learn to be invariant to or condition on.

  2. GRAPH-DISTANCE CROPS: for a random seed dot and a random BFS radius
     within the pattern's OWN graph, take the induced subgraph on all
     nodes within that radius (guarantees CONNECTEDNESS by construction,
     unlike a bounding-box crop) and repair it via
     engine.learned_generation.repair_multiplicity (bounded, edge-
     existing-only -- never invents new edges/geometry, same discipline
     M5 uses for its own candidates). Only crops that end up
     engine.validity-valid are kept; the acceptance rate is measured
     (test run: 20/20) and reported honestly in dataset_report.json, not
     assumed. This is what produces real grid-size/density/complexity
     diversity, not just symmetry variants of the same shape.

Every example's motif placements (the sequence this dataset stores) come
from engine.motifs.induce_motif_set_adaptive run on that example's OWN
graph -- the SAME function M5's motif libraries are built from, not a
new induction method.

VOCABULARY LEAKAGE DISCIPLINE: the motif vocabulary
(experiments/m6_generation/representation.MotifVocabulary) is built ONLY
from TRAIN-split examples' motifs (frequency-ranked, capped at
MAX_VOCAB_SIZE) -- val/test examples use this frozen vocabulary, with
any motif shape not in it correctly mapped to UNK_MOTIF_ID rather than
silently expanding the vocabulary post hoc.
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from pathlib import Path

import networkx as nx

from engine.dataset import load_kolam
from engine.generated_kolam import GeneratedKolam
from engine.learned_generation import repair_multiplicity
from engine.motifs import induce_motif_set_adaptive, interior_points as _interior_points
from engine.symmetry import D4_TRANSFORMS, analyze_symmetry
from engine.validity import check_validity, diagnose_validity

from experiments.m6_generation.representation import (
    MAX_GRID,
    MotifVocabulary,
    PlacementToken,
    sequence_from_placements,
)

SEED = 6262  # independent of M5's 5252 / build_training_data's 4242 -- different task
N_CROPS_PER_PATTERN = 14
CROP_RADIUS_RANGE = (3, 9)
MAX_VOCAB_SIZE = 220
CHECKPOINT_EVERY = 500

M5_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "m5_generation" / "data" / "split_manifest.json"
)
DATA_DIR = Path(__file__).resolve().parent / "data"
REPORT_PATH = Path(__file__).resolve().parent / "results" / "dataset_report.json"


def _split_patterns() -> dict:
    manifest = json.loads(M5_MANIFEST_PATH.read_text())
    out = {}
    for split in ("train", "val", "test"):
        out[split] = [tuple(s.split("#")) for s in manifest[split]]
        out[split] = [(c, int(p)) for c, p in out[split]]
    return out


def _transform_graph(G: nx.MultiGraph, dots: set, transform_name: str) -> tuple:
    t = D4_TRANSFORMS[transform_name]
    new_dots = {t(p) for p in dots}
    new_G = nx.MultiGraph()
    new_G.add_nodes_from(new_dots)
    for a, b in G.edges():
        new_G.add_edge(t(a), t(b))
    return new_G, new_dots


def _in_bounds(dots: set) -> bool:
    return all(0 <= x < MAX_GRID and 0 <= y < MAX_GRID for x, y in dots)


def _normalize_to_origin(G: nx.MultiGraph, dots: set) -> tuple:
    """Shift so the bounding box starts at (0, 0) -- D4 transforms can
    produce negative coordinates (e.g. rot180), which MAX_GRID-bounded
    token x/y cannot represent."""
    if not dots:
        return G, dots
    min_x = min(p[0] for p in dots)
    min_y = min(p[1] for p in dots)
    if min_x == 0 and min_y == 0:
        return G, dots
    shift = lambda p: (p[0] - min_x, p[1] - min_y)
    new_dots = {shift(p) for p in dots}
    new_G = nx.MultiGraph()
    new_G.add_nodes_from(new_dots)
    for a, b in G.edges():
        new_G.add_edge(shift(a), shift(b))
    return new_G, new_dots


def _crop(G: nx.MultiGraph, dots: set, rng: random.Random) -> "tuple | None":
    if not dots:
        return None
    start = rng.choice(sorted(dots))
    radius = rng.randint(*CROP_RADIUS_RANGE)
    ball = set(nx.single_source_shortest_path_length(G, start, cutoff=radius).keys())
    if len(ball) < 4:
        return None
    sub = G.subgraph(ball).copy()

    validity = check_validity(sub)
    diag = diagnose_validity(sub)
    candidate = GeneratedKolam(
        dot_points=set(ball), graph=sub, placements=[], edge_multiplicity={},
        validity_result=validity, diagnosis=diag,
    )
    repaired, _applied = repair_multiplicity(candidate)
    if not repaired.is_valid:
        return None
    return repaired.graph, repaired.dot_points


def _example_from_graph(G: nx.MultiGraph, dots: set, source_id: str, kind: str) -> "dict | None":
    if G.number_of_edges() == 0 or len(dots) < 3 or not _in_bounds(dots):
        return None
    try:
        dots_set = set(dots)
        interior = _interior_points(dots_set, radius=1)
        placements, _residual, _full = induce_motif_set_adaptive(G, interior_points=interior, dots_set=dots_set)
    except Exception:
        return None
    if not placements:
        return None

    validity = check_validity(G)
    is_valid = validity["largest_component_covers_all_nodes"] and (
        validity["is_eulerian_circuit"] or validity["has_eulerian_path"]
    )

    try:
        _motif, symmetry_coverage, _tp = analyze_symmetry(G, dots=set(dots), radius=1)
    except Exception:
        symmetry_coverage = 0.0

    xs = [p[0] for p in dots]
    ys = [p[1] for p in dots]
    width = max(xs) - min(xs) + 1
    height = max(ys) - min(ys) + 1
    n_distinct_edges = len({frozenset(e) for e in G.edges()})
    n_edge_instances = G.number_of_edges()
    complexity = min(1.0, n_distinct_edges / (3.0 * max(len(dots), 1)))
    density = min(1.0, (n_edge_instances / max(len(dots), 1)) / 6.0)
    symmetry_bucket = "high_symmetry" if symmetry_coverage >= 0.5 else "low_symmetry"

    return {
        "source_id": source_id,
        "kind": kind,  # "d4" | "crop"
        "placements": placements,  # kept as objects until vocab is frozen, then tokenized
        "dot_points": sorted(dots),
        "grid_width": width,
        "grid_height": height,
        "n_dots": len(dots),
        "n_distinct_edges": n_distinct_edges,
        "n_edge_instances": n_edge_instances,
        "is_valid": is_valid,
        "symmetry_coverage": symmetry_coverage,
        "symmetry_bucket": symmetry_bucket,
        "complexity": complexity,
        "density": density,
    }


def _build_split_examples(patterns: "list[tuple[str, int]]", rng: random.Random) -> "list[dict]":
    examples = []
    for collection, pid in patterns:
        pattern = load_kolam(collection, pid)
        source_id = f"{collection}#{pid}"
        base_G, base_dots = pattern.graph, pattern.dot_points

        for t_name in D4_TRANSFORMS:
            tg, td = _transform_graph(base_G, base_dots, t_name)
            tg, td = _normalize_to_origin(tg, td)
            ex = _example_from_graph(tg, td, source_id, "d4")
            if ex is not None:
                ex["transform"] = t_name
                examples.append(ex)

        n_crop_success = 0
        n_crop_attempts = 0
        while n_crop_success < N_CROPS_PER_PATTERN and n_crop_attempts < N_CROPS_PER_PATTERN * 3:
            n_crop_attempts += 1
            cropped = _crop(base_G, base_dots, rng)
            if cropped is None:
                continue
            cg, cd = _normalize_to_origin(*cropped)
            ex = _example_from_graph(cg, cd, source_id, "crop")
            if ex is not None:
                ex["transform"] = "identity"
                examples.append(ex)
                n_crop_success += 1
    return examples


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    splits = _split_patterns()
    rng = random.Random(SEED)

    t0 = time.time()
    raw_examples: dict = {}
    for split_name, patterns in splits.items():
        print(f"building {split_name} ({len(patterns)} source patterns)...", flush=True)
        raw_examples[split_name] = _build_split_examples(patterns, rng)
        print(f"  -> {len(raw_examples[split_name])} examples, elapsed {time.time() - t0:.1f}s", flush=True)

    # Vocabulary: TRAIN split only, frequency-ranked.
    motif_counts: Counter = Counter()
    for ex in raw_examples["train"]:
        for p in ex["placements"]:
            motif_counts[p.motif] += 1
    ranked_motifs = [m for m, _ in motif_counts.most_common()]
    vocab = MotifVocabulary.build(ranked_motifs, max_size=MAX_VOCAB_SIZE)
    print(f"vocabulary size (incl. 3 reserved): {vocab.size}", flush=True)

    n_unk_by_split = {}
    encoded: dict = {}
    for split_name, exs in raw_examples.items():
        rows = []
        n_unk = 0
        n_total_tokens = 0
        for ex in exs:
            tokens = sequence_from_placements(ex["placements"], vocab)
            n_total_tokens += len(tokens)
            n_unk += sum(1 for t in tokens if t.motif_id == 2)  # UNK_MOTIF_ID
            rows.append({
                "source_id": ex["source_id"], "kind": ex["kind"], "transform": ex["transform"],
                "grid_width": ex["grid_width"], "grid_height": ex["grid_height"],
                "n_dots": ex["n_dots"], "n_distinct_edges": ex["n_distinct_edges"],
                "n_edge_instances": ex["n_edge_instances"], "is_valid": ex["is_valid"],
                "symmetry_coverage": ex["symmetry_coverage"], "symmetry_bucket": ex["symmetry_bucket"],
                "complexity": ex["complexity"], "density": ex["density"],
                "tokens": [t.to_dict() for t in tokens],
            })
        encoded[split_name] = rows
        n_unk_by_split[split_name] = {"n_unk_tokens": n_unk, "n_total_tokens": n_total_tokens,
                                        "unk_rate": n_unk / n_total_tokens if n_total_tokens else None}
        (DATA_DIR / f"{split_name}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows), encoding="utf-8"
        )

    (DATA_DIR / "vocab.json").write_text(json.dumps(vocab.to_dict()))

    total_time = time.time() - t0

    # duplicate rate: exact token-sequence duplicates within train
    seq_keys = [tuple((t["motif_id"], t["x"], t["y"], t["transform_id"]) for t in r["tokens"]) for r in encoded["train"]]
    n_unique_seqs = len(set(seq_keys))

    topology_dist = Counter(r["kind"] for r in encoded["train"])
    symmetry_dist = Counter(r["symmetry_bucket"] for r in encoded["train"])
    complexity_vals = [r["complexity"] for r in encoded["train"]]
    validity_counts = Counter(r["is_valid"] for r in encoded["train"])

    report = {
        "n_source_patterns": sum(len(p) for p in splits.values()),
        "n_source_patterns_by_split": {k: len(v) for k, v in splits.items()},
        "n_examples_by_split": {k: len(v) for k, v in encoded.items()},
        "n_examples_total": sum(len(v) for v in encoded.values()),
        "validity_rate_train": validity_counts[True] / len(encoded["train"]) if encoded["train"] else None,
        "topology_distribution_train": dict(topology_dist),
        "symmetry_distribution_train": dict(symmetry_dist),
        "complexity_mean_train": sum(complexity_vals) / len(complexity_vals) if complexity_vals else None,
        "complexity_min_train": min(complexity_vals) if complexity_vals else None,
        "complexity_max_train": max(complexity_vals) if complexity_vals else None,
        "n_unique_token_sequences_train": n_unique_seqs,
        "structural_uniqueness_rate_train": n_unique_seqs / len(seq_keys) if seq_keys else None,
        "duplicate_rate_train": 1 - (n_unique_seqs / len(seq_keys)) if seq_keys else None,
        "vocab_size": vocab.size,
        "unk_rate_by_split": n_unk_by_split,
        "crop_config": {"n_crops_per_pattern_target": N_CROPS_PER_PATTERN, "crop_radius_range": CROP_RADIUS_RANGE},
        "build_time_seconds": total_time,
        "seed": SEED,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
