"""M5 OBJECTIVE 8: real-photo end-to-end experiment.

photo -> quality analysis -> normalization -> recognition (fusion) ->
structural representation -> generation -> verification

HONESTY RULES ENFORCED THROUGHOUT (this project has NO hand-labeled
ground-truth dots for these photos -- docs/M4_2_EVALUATION.md and
experiments/real_photo_baseline.json already established this):
  - No precision/recall/accuracy is computed for recognition. Every
    recognition-quality field is either a real measurement (inter-
    detector agreement, dot count) or explicitly "UNRESOLVED".
  - A photo where the classical detector's own is_traceable() gate
    fails (see engine.image_io) is recorded as a genuine recognition
    failure, not silently skipped -- prior work
    (experiments/real_photo_baseline.json) already found most of these
    23 real photos fail at that gate; this script reports the SAME
    honest failure mode, not a rosier one.
  - Generation only runs for a photo whose recognition succeeded AND
    produced a graph with at least one edge -- an empty/edgeless
    representation cannot seed a motif library (see
    engine.generation_contract.generate_novel_kolams), and this script
    reports that as "generation_skipped_reason", not a silent 0.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REAL_PHOTOS_DIR = REPO_ROOT / "real_photos"
RESULTS_PATH = Path(__file__).resolve().parent / "results" / "real_photo_experiment.json"
DEBUG_DIR = Path(__file__).resolve().parent / "results" / "real_photo_debug"

N_CANDIDATES_PER_PHOTO = 3
N_RESTARTS = 3


def run(max_photos: int | None = None) -> dict:
    from api.recognition_fusion import fuse_recognition
    from engine.generation_contract import StructuralRepresentation, build_representation, generate_novel_kolams
    from engine.image_quality import assess_quality, normalize_for_recognition
    from engine.learned_scoring import load_scorer

    photo_paths = sorted(REAL_PHOTOS_DIR.glob("*.jpg"))
    if max_photos is not None:
        photo_paths = photo_paths[:max_photos]

    scorer = load_scorer()
    records = []

    for photo_path in photo_paths:
        record: dict = {"file": photo_path.name}
        t0 = time.time()

        try:
            quality = assess_quality(str(photo_path))
            record["quality"] = quality.to_dict()
        except Exception as e:  # noqa: BLE001
            record["quality_error"] = f"{type(e).__name__}: {e}"
            records.append(record)
            continue

        normalize_for_recognition(str(photo_path), debug_dir=DEBUG_DIR)
        record["normalized_debug_saved"] = True

        try:
            fusion, raw_results = fuse_recognition(str(photo_path))
        except Exception as e:  # noqa: BLE001
            record["recognition_error"] = f"{type(e).__name__}: {e}"
            records.append(record)
            continue

        record["recognition"] = {
            "sources": [
                {"detector": s.detector, "available": s.available, "count": s.count, "error": s.error}
                for s in fusion.sources
            ],
            "n_consensus_dots": fusion.n_consensus_dots,
            "agreement_fraction": fusion.agreement_fraction,
            "pairwise_disagreement": fusion.pairwise_disagreement,
            "primary_graph_source": fusion.primary_graph_source,
            "precision_recall_note": "UNRESOLVED -- no hand-labeled ground-truth dots exist for real photos",
        }

        if fusion.primary_graph_source is None or fusion.primary_graph_source not in raw_results:
            record["generation_skipped_reason"] = "no detector produced usable output"
            records.append(record)
            continue

        primary = raw_results[fusion.primary_graph_source]
        graph = primary.graph
        dots = set(graph.nodes())

        if graph.number_of_edges() == 0 or len(dots) < 3:
            record["structural_representation"] = None
            record["generation_skipped_reason"] = (
                f"primary detector ({fusion.primary_graph_source}) produced "
                f"{len(dots)} dots / {graph.number_of_edges()} edges -- insufficient to build a structural "
                "representation or induce a motif library (matches known real-photo recognition "
                "limitation, see experiments/real_photo_baseline.json)"
            )
            records.append(record)
            continue

        rep = build_representation(graph, dot_points=dots)
        record["structural_representation"] = {
            "n_nodes": rep.n_nodes,
            "n_distinct_edges": rep.n_distinct_edges,
            "connected_components": rep.connected_components,
            "n_odd_degree_nodes": rep.n_odd_degree_nodes,
            "is_valid_single_stroke": rep.is_valid_single_stroke,
            "symmetry_coverage": rep.symmetry_coverage,
        }

        try:
            gen_results = generate_novel_kolams(
                rep, num_candidates=N_CANDIDATES_PER_PHOTO, seed=0, scorer=scorer, n_restarts=N_RESTARTS,
            )
            record["generation"] = {
                "n_candidates": len(gen_results),
                "n_valid": sum(1 for r in gen_results if r["is_valid"]),
                "candidates": [
                    {
                        "candidate_id": r["candidate_id"],
                        "is_valid": r["is_valid"],
                        "validity_score": r["validity_score"],
                        "n_odd_degree_nodes": r["representation"]["n_odd_degree_nodes"],
                        "connected_components": r["representation"]["connected_components"],
                    }
                    for r in gen_results
                ],
            }
        except Exception as e:  # noqa: BLE001
            record["generation_error"] = f"{type(e).__name__}: {e}"

        record["total_time_seconds"] = round(time.time() - t0, 1)
        records.append(record)
        print(f"{photo_path.name}: {record.get('generation_skipped_reason', record.get('generation', {}).get('n_valid'))}")

    n_total = len(records)
    n_recognition_failed = sum(1 for r in records if "recognition_error" in r or "quality_error" in r)
    n_generation_skipped = sum(1 for r in records if "generation_skipped_reason" in r)
    n_generation_attempted = sum(1 for r in records if "generation" in r)
    n_generation_valid = sum(r.get("generation", {}).get("n_valid", 0) for r in records)

    summary = {
        "n_photos": n_total,
        "n_recognition_failed": n_recognition_failed,
        "n_generation_skipped_insufficient_recognition": n_generation_skipped,
        "n_generation_attempted": n_generation_attempted,
        "n_generation_candidates_total": n_generation_attempted * N_CANDIDATES_PER_PHOTO,
        "n_generation_valid_total": n_generation_valid,
        "real_photo_recognition_precision_recall": "UNRESOLVED (no ground truth)",
        "note": (
            "Real-photo recognition on this dataset is a known, previously documented weak point "
            "(experiments/real_photo_baseline.json, docs/M4_2_EVALUATION.md) -- classical/ML detectors "
            "frequently fail the is_traceable gate on real photographs (lighting, shadow, non-uniform "
            "dot ink vs. line ink). This experiment measures the SAME honest limitation for the "
            "generation pipeline: generation can only run once recognition succeeds."
        ),
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"summary": summary, "records": records}, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--max-photos", type=int, default=None)
    args = parser.parse_args()
    run(max_photos=args.max_photos)
