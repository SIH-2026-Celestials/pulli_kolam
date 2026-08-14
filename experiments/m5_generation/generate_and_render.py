"""M5: produce ACTUAL rendered novel Kolam images (SVG) from the trained
placement scorer, via engine.generation_contract.generate_kolam -- the
same production-facing entry point a future API would call, not a
separate one-off rendering path.

Iterates seeds against held-out TEST-split layouts (never train/val --
experiments/m5_generation/data/split_manifest.json) until
TARGET_N_VALID successful (is_valid) candidates are collected or
MAX_ATTEMPTS is reached, whichever first. Every attempt (valid or not)
is logged; failed candidates are recorded separately for debugging, not
discarded silently, and nothing is manually curated into the metrics --
this script does not retouch or hand-pick which successes count.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from engine.dataset import load_kolam
from engine.generation_api import motif_library_from_sources
from engine.generation_contract import generate_kolam
from engine.learned_scoring import load_scorer

DATA_DIR = Path(__file__).resolve().parent / "data"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
RESULTS_PATH = Path(__file__).resolve().parent / "results" / "generation_artifacts_report.json"

TARGET_N_VALID = 20
MAX_ATTEMPTS = 90
N_RESTARTS = 10
# N_RESTARTS reduced from a nominal 16 -- measured cost is ~24s/candidate
# at n_restarts=16 on a 200-dot real layout; at n_restarts=10 this script's
# budget (MAX_ATTEMPTS=90) fits the session's remaining time. Documented,
# not hidden -- see experiments/m5_generation/run_benchmark_lite.py's
# module docstring for the same measurement.


def _test_sources() -> list[tuple[str, int]]:
    manifest = json.loads((DATA_DIR / "split_manifest.json").read_text())
    return [tuple(s.split("#")) for s in manifest["test"]]


def main():
    test_sources = [(c, int(p)) for c, p in _test_sources()]
    scorer = load_scorer()

    layouts = []
    real_sources = []
    for collection, pid in test_sources:
        pattern = load_kolam(collection, pid)
        layouts.append((f"{collection}#{pid}", pattern.dot_points))
        real_sources.append(pattern)

    library_sources = test_sources[: min(5, len(test_sources))]
    motif_library = motif_library_from_sources([(c, p) for c, p in library_sources])
    print(f"motif library size: {len(motif_library)} from {library_sources}")

    valid_dir = ARTIFACTS_DIR / "valid"
    failed_dir = ARTIFACTS_DIR / "failed"
    valid_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    valid_records = []
    failed_records = []
    t0 = time.time()

    attempt = 0
    while len(valid_records) < TARGET_N_VALID and attempt < MAX_ATTEMPTS:
        layout_name, dots = layouts[attempt % len(layouts)]
        seed = 900000 + attempt  # disjoint seed range from run_benchmark.py's 0..499, avoids any accidental reuse
        out = generate_kolam(
            motif_library, dots, seed=seed, n_restarts=N_RESTARTS, scorer=scorer,
            novelty_sources=real_sources,
        )
        record = {
            "attempt": attempt, "seed": seed, "source_layout": layout_name,
            "success": out["success"], "metrics": out["metrics"], "validity": out["validity"],
            "novelty": out["novelty"],
        }
        if out["success"]:
            idx = len(valid_records)
            svg_path = valid_dir / f"valid_{idx:03d}_seed{seed}.svg"
            svg_path.write_text(out["render"]["svg"], encoding="utf-8")
            meta_path = valid_dir / f"valid_{idx:03d}_seed{seed}.json"
            meta_path.write_text(json.dumps(record, indent=2))
            record["svg_path"] = str(svg_path)
            valid_records.append(record)
            print(f"[{attempt}] VALID #{idx} layout={layout_name} seed={seed} "
                  f"components={record['metrics']['connected_components']} "
                  f"odd={record['metrics']['n_odd_degree_nodes']}")
        else:
            idx = len(failed_records)
            if idx < 30:  # cap how many failed SVGs we bother writing -- debugging aid, not the metric
                svg_path = failed_dir / f"failed_{idx:03d}_seed{seed}.svg"
                svg_path.write_text(out["render"]["svg"], encoding="utf-8")
                record["svg_path"] = str(svg_path)
            failed_records.append(record)
        attempt += 1

    total_time = time.time() - t0
    report = {
        "target_n_valid": TARGET_N_VALID, "max_attempts": MAX_ATTEMPTS, "n_restarts_per_attempt": N_RESTARTS,
        "n_attempts_used": attempt, "n_valid": len(valid_records), "n_failed": len(failed_records),
        "valid_rate_this_run": len(valid_records) / attempt if attempt else None,
        "total_time_seconds": total_time,
        "motif_library_size": len(motif_library), "motif_library_sources": library_sources,
        "n_test_layouts": len(layouts),
        "valid_records": valid_records,
        "failed_records_sample": failed_records[:30],
        "n_failed_total": len(failed_records),
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nn_valid={len(valid_records)}  n_attempts={attempt}  total_time={total_time:.1f}s")
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
