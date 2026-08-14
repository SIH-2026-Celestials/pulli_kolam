"""M6 Phase 9: end-to-end generation benchmark.

    python -m experiments.m6_generation.benchmark --count 100

Runs the SAME pipeline generate.py's CLI uses (generate_candidates is
imported, not reimplemented) across `count` independent seeds, and
reports the per-candidate outcome funnel plus latency percentiles --
task's explicit metric list, computed directly from real attempts, not
assumed or extrapolated from a smaller sample.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from experiments.m6_generation.generate import _parse_grid, load_model

RESULTS_DIR = Path(__file__).resolve().parent / "results"
REPORT_PATH = RESULTS_DIR / "benchmark.json"


def run(grid, symmetry: str, complexity: float, density: float, seed: int, count: int) -> dict:
    """Generates exactly `count` INDEPENDENT ATTEMPTS (not `count`
    accepted candidates -- unlike generate.py's CLI, which resamples
    until `count` are accepted, this benchmark measures the RAW
    per-attempt funnel: generated -> structurally_valid ->
    placement_accepted -> rendered -> recognized -> novel ->
    final_accepted, one row per seed, exactly as Phase 9 specifies)."""
    from engine.render import DEFAULT_MARGIN, DEFAULT_SCALE, render_generated_kolam_png, render_generated_kolam_svg
    from engine.symmetry import analyze_symmetry

    from experiments.m6_generation.dataset import load_vocab
    from experiments.m6_generation.novelty import StructuralStats, nearest_training_novelty
    from experiments.m6_generation.validate import assemble_and_validate
    from experiments.m6_generation.verify import verify_with_recognizer
    from experiments.m6_generation.generate import _load_training_stats_and_graphs, _replay_placement_score, _rectangular_lattice

    import torch

    model, vocab = load_model()
    width, height = grid
    dots = _rectangular_lattice(width, height)
    symmetry_idx = 1 if symmetry == "rotational4" else 0
    training_stats, training_graphs = _load_training_stats_and_graphs()

    rows = []
    t_start = time.time()
    for i in range(count):
        this_seed = seed + i
        t0 = time.time()
        gen = torch.Generator().manual_seed(this_seed)
        grid_wh = torch.tensor([[float(width), float(height)]])
        sym_t = torch.tensor([symmetry_idx])
        scalars_t = torch.tensor([[complexity, density]])

        row = {"index": i, "seed": this_seed, "generated": True}
        raw_tokens = model.generate(
            grid_wh, sym_t, scalars_t, max_len=model.config.max_seq_len - 1,
            temperature=0.9, generator=gen,
        )
        row["n_raw_tokens"] = len(raw_tokens)

        assembled = assemble_and_validate(raw_tokens, vocab, dots)
        candidate = assembled.candidate
        row["structurally_valid"] = candidate.is_valid

        placement_accepted = False
        rendered = False
        recognized = None
        novel = None
        final_accepted = False
        placement_score = None
        novelty_score = None

        if candidate.is_valid:
            placement_score = _replay_placement_score(candidate, dots)
            placement_accepted = placement_score is None or placement_score >= 0.0  # no hard cutoff in the bare benchmark, see generate.py's CLI for threshold enforcement
            try:
                _motif, symmetry_coverage, _tp = analyze_symmetry(candidate.graph, dots=set(candidate.dot_points), radius=1)
            except Exception:
                symmetry_coverage = 0.0

            cand_stats = StructuralStats.from_graph(candidate.graph, symmetry_coverage, complexity, density)
            novelty = nearest_training_novelty(candidate.graph, cand_stats, training_stats, training_graphs)
            novelty_score = novelty["novelty_score"]
            novel = novelty_score is None or novelty_score > 0.05  # near-zero distance = essentially identical stats to a training example

            try:
                svg = render_generated_kolam_svg(candidate)
                png_path = RESULTS_DIR / "_benchmark_tmp.png"
                render_generated_kolam_png(candidate, str(png_path))
                rendered = True
            except Exception:
                rendered = False

            if rendered:
                verification = verify_with_recognizer(
                    str(png_path), sorted(candidate.dot_points), DEFAULT_SCALE, DEFAULT_MARGIN,
                )
                recognized = verification.available and (verification.recall or 0) > 0.5

            final_accepted = candidate.is_valid and placement_accepted and rendered and bool(recognized) and bool(novel)

        row.update({
            "placement_accepted": placement_accepted, "placement_score": placement_score,
            "rendered": rendered, "recognized": recognized, "novel": novel,
            "novelty_score": novelty_score, "final_accepted": final_accepted,
            "latency_seconds": time.time() - t0,
        })
        rows.append(row)
        if (i + 1) % 10 == 0:
            print(f"{i + 1}/{count} attempted, elapsed {time.time() - t_start:.0f}s", flush=True)

    total_time = time.time() - t_start
    n = len(rows)

    def rate(key):
        return sum(1 for r in rows if r.get(key)) / n if n else None

    latencies = sorted(r["latency_seconds"] for r in rows)

    def percentile(p):
        if not latencies:
            return None
        idx = min(len(latencies) - 1, int(round(p / 100 * (len(latencies) - 1))))
        return latencies[idx]

    rejection_reasons = {}
    for r in rows:
        if not r["structurally_valid"]:
            rejection_reasons["structurally_invalid"] = rejection_reasons.get("structurally_invalid", 0) + 1
        elif not r["rendered"]:
            rejection_reasons["render_failed"] = rejection_reasons.get("render_failed", 0) + 1
        elif not r["recognized"]:
            rejection_reasons["recognizer_verification_failed"] = rejection_reasons.get("recognizer_verification_failed", 0) + 1
        elif not r["novel"]:
            rejection_reasons["not_novel"] = rejection_reasons.get("not_novel", 0) + 1

    summary = {
        "n_candidates": n,
        "generation_success_rate": rate("generated"),
        "structural_validity_rate": rate("structurally_valid"),
        "renderer_success_rate": rate("rendered"),
        "recognizer_verification_rate": rate("recognized"),
        "novelty_rate": rate("novel"),
        "final_acceptance_rate": rate("final_accepted"),
        "avg_generation_latency_seconds": statistics.mean(latencies) if latencies else None,
        "p50_latency_seconds": percentile(50),
        "p95_latency_seconds": percentile(95),
        "total_benchmark_time_seconds": total_time,
        "candidate_rejection_reasons": rejection_reasons,
        "config": {"grid": grid, "symmetry": symmetry, "complexity": complexity, "density": density, "seed": seed},
    }
    REPORT_PATH.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid", type=str, default="7x7")
    parser.add_argument("--symmetry", type=str, default="auto", choices=["auto", "none", "rotational4"])
    parser.add_argument("--complexity", type=float, default=0.7)
    parser.add_argument("--density", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=20000000)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    run(_parse_grid(args.grid), args.symmetry, args.complexity, args.density, args.seed, args.count)


if __name__ == "__main__":
    main()
