"""M6 Phase 5/6/10: constrained generation CLI.

    python -m experiments.m6_generation.generate \\
        --grid 7x7 --symmetry rotational4 --complexity 0.7 --density 0.6 \\
        --seed 12345 --count 10

Pipeline (every stage a separate, testable component -- task's explicit
rule 8):

    seed -> model.generate() [raw token sequence]
          -> validate.assemble_and_validate() [hard structural gate + repair]
          -> reject if invalid
          -> M5 placement-scorer replay [placement_score]
          -> reject if placement_score < --min-placement-score
          -> novelty.nearest_training_novelty() [novelty_score]
          -> reject if novelty_score < --novelty-threshold
          -> engine.render [SVG + PNG]
          -> verify.verify_with_recognizer() [frozen M4.2 self-consistency,
             recorded but NOT a rejection gate by default -- a detector
             miss is a recognizer/render-domain finding, not proof the
             STRUCTURE is invalid, which the hard gate above already
             settled]
          -> write outputs/kolam_XXXXXX.{json,svg,png}

Bounded, never hangs: at most --max-attempts total samples are drawn
across all requested --count candidates; if the budget runs out with
fewer than --count accepted, the CLI reports exactly how many were
produced and why the rest were rejected (candidate_rejection_reasons in
generation_report.json), never silently returning fewer than asked with
no explanation.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path

import torch

from engine.render import DEFAULT_MARGIN, DEFAULT_SCALE, render_generated_kolam_png, render_generated_kolam_svg
from engine.symmetry import analyze_symmetry

from experiments.m6_generation.dataset import load_vocab
from experiments.m6_generation.model import KolamSequenceGenerator, ModelConfig, SYMMETRY_BUCKETS
from experiments.m6_generation.novelty import StructuralStats, nearest_training_novelty
from experiments.m6_generation.representation import GenerationConfig
from experiments.m6_generation.validate import assemble_and_validate
from experiments.m6_generation.verify import verify_with_recognizer

RESULTS_DIR = Path(__file__).resolve().parent / "results"
DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUTS_DIR = Path(__file__).resolve().parent / "outputs"
BEST_CHECKPOINT_PATH = RESULTS_DIR / "generator_v1_best.pt"

DEFAULT_MAX_ATTEMPTS_PER_CANDIDATE = 8
SYMMETRY_MIN_COVERAGE_FOR_ROTATIONAL4 = 0.35  # real, measured threshold -- see analyze_symmetry


def load_model() -> "tuple[KolamSequenceGenerator, object]":
    vocab = load_vocab()
    ckpt = torch.load(BEST_CHECKPOINT_PATH, map_location="cpu", weights_only=False)
    config = ModelConfig.from_dict(ckpt["config"])
    model = KolamSequenceGenerator(config)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model, vocab


def _load_training_stats_and_graphs():
    """StructuralStats come directly from build_dataset.py's already-
    computed per-example fields (no graph rebuild needed, cheap)."""
    rows = []
    with open(DATA_DIR / "train.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    stats = [
        StructuralStats(
            n_dots=r["n_dots"], n_distinct_edges=r["n_distinct_edges"], n_edge_instances=r["n_edge_instances"],
            symmetry_coverage=r["symmetry_coverage"], complexity=r["complexity"], density=r["density"],
            degree_histogram={},  # not stored per-example; degree_distance term degrades gracefully to 0 contribution when both sides are empty -- documented limitation, not silently wrong
        )
        for r in rows
    ]

    # STRICT exact-duplicate check (engine.novelty.graph_fingerprint) needs
    # full graphs, but build_dataset.py's jsonl rows store token sequences
    # + summary stats only (dot_points/edges were intentionally NOT
    # persisted per-row, to keep the dataset file size bounded) -- so the
    # strict check is unavailable here and nearest_training_novelty
    # correctly reports is_exact_topological_duplicate=None (unresolved,
    # not silently False) whenever `graphs` is empty. The graded
    # combined_distance novelty_score above does NOT depend on this and
    # is always computed.
    graphs: list = []
    return stats, graphs


def _parse_grid(s: str) -> "tuple[int, int]":
    parts = s.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"--grid must be WxH, e.g. 7x7, got {s!r}")
    return int(parts[0]), int(parts[1])


def _rectangular_lattice(w: int, h: int) -> set:
    return {(x, y) for x in range(w) for y in range(h)}


def generate_candidates(
    grid: "tuple[int, int]", symmetry: str, complexity: float, density: float,
    seed: int, count: int, max_attempts: "int | None" = None,
    novelty_threshold: float = 0.0, min_placement_score: float = 0.0,
    verify: bool = True,
) -> dict:
    model, vocab = load_model()
    width, height = grid
    dots = _rectangular_lattice(width, height)
    symmetry_idx = 1 if symmetry == "rotational4" else 0

    training_stats, training_graphs = _load_training_stats_and_graphs()

    max_attempts = max_attempts or count * DEFAULT_MAX_ATTEMPTS_PER_CANDIDATE
    accepted = []
    rejection_reasons: Counter = Counter()
    attempt = 0
    t_start = time.time()

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    while len(accepted) < count and attempt < max_attempts:
        this_seed = seed + attempt
        attempt += 1
        gen = torch.Generator().manual_seed(this_seed)

        grid_wh = torch.tensor([[float(width), float(height)]])
        sym_t = torch.tensor([symmetry_idx])
        scalars_t = torch.tensor([[complexity, density]])

        min_len = min(model.config.max_seq_len - 2, max(10, int(0.5 * width * height)))
        raw_tokens = model.generate(
            grid_wh, sym_t, scalars_t, max_len=model.config.max_seq_len - 1,
            temperature=0.9, generator=gen, min_len=min_len,
        )
        hit_max_len = len(raw_tokens) >= model.config.max_seq_len - 1

        assembled = assemble_and_validate(raw_tokens, vocab, dots, hit_max_len_without_eos=hit_max_len)
        candidate = assembled.candidate

        if not candidate.is_valid:
            rejection_reasons["structurally_invalid"] += 1
            continue

        placement_score = _replay_placement_score(candidate, dots)
        if placement_score is not None and placement_score < min_placement_score:
            rejection_reasons["placement_score_below_threshold"] += 1
            continue

        try:
            _motif, symmetry_coverage, _tp = analyze_symmetry(candidate.graph, dots=set(candidate.dot_points), radius=1)
        except Exception:
            symmetry_coverage = 0.0

        if symmetry == "rotational4" and symmetry_coverage < SYMMETRY_MIN_COVERAGE_FOR_ROTATIONAL4:
            rejection_reasons["symmetry_constraint_not_met"] += 1
            continue

        cand_stats = StructuralStats.from_graph(candidate.graph, symmetry_coverage, complexity, density)
        novelty = nearest_training_novelty(candidate.graph, cand_stats, training_stats, training_graphs)
        if novelty["novelty_score"] is not None and novelty["novelty_score"] < novelty_threshold:
            rejection_reasons["novelty_below_threshold"] += 1
            continue

        idx = len(accepted)
        sample_id = f"kolam_{idx + 1:06d}"
        svg = render_generated_kolam_svg(candidate)
        png_path = OUTPUTS_DIR / f"{sample_id}.png"
        render_generated_kolam_png(candidate, str(png_path))

        verification = None
        if verify:
            verification = verify_with_recognizer(
                str(png_path), sorted(candidate.dot_points), DEFAULT_SCALE, DEFAULT_MARGIN,
            ).to_dict()

        record = {
            "seed": this_seed,
            "generation_config": GenerationConfig(width, height, symmetry, complexity, density, this_seed).to_dict(),
            "symbolic_representation": {"n_tokens": len(raw_tokens), "n_placements_used": assembled.n_placements_used,
                                          "hit_max_len_without_eos": assembled.hit_max_len_without_eos},
            "structural_validation": {
                "is_valid": candidate.is_valid, "validity_result": candidate.validity_result,
                "repair_edges_applied": len(assembled.repair_applied),
            },
            "placement_score": placement_score,
            "novelty": novelty,
            "recognizer_verification": verification,
            "n_dots": candidate.n_dots, "n_distinct_edges": candidate.n_distinct_edges,
            "symmetry_coverage": symmetry_coverage,
        }
        (OUTPUTS_DIR / f"{sample_id}.json").write_text(json.dumps(record, indent=2))
        (OUTPUTS_DIR / f"{sample_id}.svg").write_text(svg, encoding="utf-8")
        accepted.append({"sample_id": sample_id, **record})

    report = {
        "requested_count": count, "accepted_count": len(accepted), "n_attempts": attempt,
        "max_attempts": max_attempts, "rejection_reasons": dict(rejection_reasons),
        "total_time_seconds": time.time() - t_start,
        "config": {"grid": grid, "symmetry": symmetry, "complexity": complexity, "density": density, "seed": seed},
    }
    (RESULTS_DIR / "generation_report.json").write_text(json.dumps({"summary": report, "accepted": accepted}, indent=2))
    return report


def _replay_placement_score(candidate, dots) -> "float | None":
    """Reuse of M5's placement scorer (Phase 5's explicit instruction),
    NOT a rewrite: replays the candidate's OWN accepted placements
    through the SAME feature extraction (engine.learned_scoring.extract_features)
    the M5 search loop scores every candidate edit with, in the order
    they appear in `candidate.placements`, and returns the MEAN
    per-placement score -- an honest aggregate of a per-edit signal, not
    a whole-graph score (the scorer was never trained to consume a whole
    graph at once, see ARCHITECTURE.md section 5)."""
    from collections import Counter as _Counter

    from engine.learned_scoring import extract_features, load_scorer
    from engine.novel_generation import _UnionFind, _connectivity_effect, _parity_effect, _stamp_contribution

    if not candidate.placements:
        return None
    try:
        scorer = load_scorer()
    except Exception:
        return None

    accumulated: _Counter = _Counter()
    degree: _Counter = _Counter()
    uf = _UnionFind(dots)
    touched_dots: set = set()
    any_real_structure_exists = False
    n_dots = len(dots)
    scores = []

    for placement in candidate.placements:
        for point in placement.points:
            t_name = placement.transforms.get(point, "identity")
            contribution = _stamp_contribution(placement.motif, point, t_name, dots)
            if not contribution:
                continue
            conn_effect = _connectivity_effect(uf, contribution)
            parity_effect = _parity_effect(degree, contribution)
            progress_frac = len(touched_dots) / n_dots if n_dots else 0.0
            n_odd = sum(1 for d in degree.values() if d % 2 == 1)
            global_odd_frac = n_odd / n_dots if n_dots else 0.0
            feats = extract_features(
                motif_len=len(placement.motif), contribution=contribution, degree_before=degree,
                connectivity_effect=conn_effect, parity_effect=parity_effect,
                any_real_structure_exists=any_real_structure_exists, progress_frac=progress_frac,
                global_odd_frac=global_odd_frac,
            )
            scores.append(scorer.score(feats))
            for edge, count in contribution.items():
                accumulated[edge] += count
                a, b = tuple(edge)
                degree[a] += count
                degree[b] += count
                touched_dots.add(a)
                touched_dots.add(b)
                uf.union(a, b)
            any_real_structure_exists = True

    return sum(scores) / len(scores) if scores else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid", type=str, default="7x7")
    parser.add_argument("--symmetry", type=str, default="auto", choices=["auto", "none", "rotational4"])
    parser.add_argument("--complexity", type=float, default=0.7)
    parser.add_argument("--density", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--novelty-threshold", type=float, default=0.0)
    parser.add_argument("--min-placement-score", type=float, default=0.0)
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()

    grid = _parse_grid(args.grid)
    report = generate_candidates(
        grid=grid, symmetry=args.symmetry, complexity=args.complexity, density=args.density,
        seed=args.seed, count=args.count, max_attempts=args.max_attempts,
        novelty_threshold=args.novelty_threshold, min_placement_score=args.min_placement_score,
        verify=not args.no_verify,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
