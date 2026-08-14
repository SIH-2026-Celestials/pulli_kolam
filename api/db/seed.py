"""M7 platform integration: model registry seed data.

Every metric below is READ from an existing, already-produced results
file (never invented) -- see each entry's `_source` comment. Idempotent:
`seed_models()` upserts by (model name, version), safe to call on every
process start alongside `init_db()`.

CRITICAL: M6 is seeded with status="research" and its checkpoint is
NEVER read by api/services/generation.py or api/services/verification.py
-- the status string is the enforcement point application code checks,
not merely a label (see api/services/generation.py's own guard).
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from api.db.models import Model, ModelVersion

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _read_json(rel_path: str) -> dict:
    path = _REPO_ROOT / rel_path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001 -- seeding must never crash app startup over a malformed results file
        return {}


def _m5_metrics() -> dict:
    # source: experiments/m5_generation/results/train_report.json (placement-scorer
    # training metrics) + experiments/m5_generation/results/benchmark_report.json
    # (final 500-candidate generation benchmark, both already-produced research
    # artifacts, read verbatim here, never recomputed or altered).
    train = _read_json("experiments/m5_generation/results/train_report.json").get("metadata", {})
    bench = _read_json("experiments/m5_generation/results/benchmark_report.json")
    bench_summary = bench.get("summary", {})
    return {
        "scorer_architecture": train.get("architecture"),
        "scorer_n_parameters": train.get("n_parameters"),
        "scorer_test_accuracy": train.get("test_acc"),
        "scorer_test_auc": train.get("test_auc"),
        "benchmark_n_candidates": bench_summary.get("n_generated"),
        "benchmark_validity_rate": bench_summary.get("validity_rate"),
        "benchmark_unique_rate": bench_summary.get("novelty", {}).get("unique_rate"),
        "benchmark_avg_latency_seconds": bench_summary.get("avg_generation_latency_seconds"),
    }


def _m4_2_metrics() -> dict:
    # source: experiments/m4_2/results/evaluate_m4_2.json's synthetic_test set
    # (the ML detector's own held-out evaluation, real-photo metrics
    # deliberately excluded here -- see api/services/verification.py's
    # module docstring on why M4.2 is not a production photo verifier).
    ev = _read_json("experiments/m4_2/results/evaluate_m4_2.json")
    synth_test = ev.get("sets", {}).get("synthetic_test", {}).get("ml", {})
    return {
        "synthetic_test_recall": synth_test.get("mean_recall"),
        "synthetic_test_precision": synth_test.get("mean_precision"),
        "synthetic_test_f1": synth_test.get("mean_f1"),
        "real_photo_note": "NOT evaluated as a production photo verifier -- see docs/M4_2_EVALUATION.md",
    }


def _m6_metrics() -> dict:
    # source: experiments/m6_generation/results/training_log.json +
    # results/benchmark.json (M6 V1's own honestly-reported 0% validity
    # result -- included as-is, not hidden, since this row exists purely
    # for research-provenance transparency and is never used for live
    # generation).
    train = _read_json("experiments/m6_generation/results/training_log.json")
    bench = _read_json("experiments/m6_generation/results/benchmark.json")
    bench_summary = bench.get("summary", {})
    return {
        "n_parameters": train.get("n_parameters"),
        "best_val_loss": train.get("best_val_loss"),
        "benchmark_structural_validity_rate": bench_summary.get("structural_validity_rate"),
        "status_note": "research-only; 0% structural validity in its own benchmark -- not used for generation",
    }


def seed_models(session: Session) -> None:
    specs = [
        ("M5", "Learned-scorer-guided structural search generator (engine.learned_generation)",
         "v1.0", "production",
         "experiments/m5_generation/checkpoints/placement_scorer.pt", _m5_metrics()),
        ("M4.2", "DotHeatmapNetV2 dot-lattice detector (experiments/m4_2)",
         "v2", "production-verifier",
         "experiments/m4_2/results/dot_heatmap_net_v2.pt", _m4_2_metrics()),
        ("M6", "Autoregressive sequence generator, V1 (experiments/m6_generation) -- research only",
         "v1", "research",
         "experiments/m6_generation/results/generator_v1_best.pt", _m6_metrics()),
    ]

    for model_name, description, version, status, checkpoint_rel, metrics in specs:
        model = session.query(Model).filter_by(name=model_name).one_or_none()
        if model is None:
            model = Model(name=model_name, description=description)
            session.add(model)
            session.flush()

        existing_version = (
            session.query(ModelVersion)
            .filter_by(model_id=model.id, version=version)
            .one_or_none()
        )
        checkpoint_path = str(_REPO_ROOT / checkpoint_rel) if checkpoint_rel else None
        if existing_version is None:
            session.add(
                ModelVersion(
                    model_id=model.id, version=version, status=status,
                    checkpoint_path=checkpoint_path, metrics=metrics,
                )
            )
        else:
            # Re-seeding refreshes metrics from the latest results files
            # (a research run may have produced new numbers since the
            # last app start) without creating a duplicate version row.
            existing_version.metrics = metrics
            existing_version.status = status
            existing_version.checkpoint_path = checkpoint_path

    session.commit()
