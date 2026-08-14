"""M5: build an imitation-learning dataset for engine.learned_scoring.

TEACHER (oracle label), STUDENT (learned features) -- kept strictly
separate: for each real, verified-valid pattern in kolam19/kolam29, this
script replays the exact same deterministic candidate stream
engine.novel_generation.select_novel_placements would enumerate (sorted
interior points x this pattern's own induced motif library x 8 D4
transforms) against the pattern's OWN dot layout, and labels each
candidate 1 (accept) iff every edge/strand it would contribute is
actually present in the pattern's real edge multiset within the
remaining budget -- i.e. the oracle is exactly
engine.validity.check_self_consistency's edge-multiset-match logic,
applied incrementally. The REPLAY STATE then evolves according to the
oracle's own accept/reject decisions (teacher forcing), so training
examples reflect the states a perfectly-guided search would actually
visit.

The feature vector recorded per example (engine.learned_scoring.extract_features)
uses ONLY structural quantities available at real generation time on an
UNSEEN layout (growth, parity, connectivity effect, progress) -- the
ground-truth edge multiset is used solely to compute the label, never as
a feature. This is what makes the trained scorer usable on a layout with
no source pattern at all.

Leakage discipline: patterns are split into disjoint train/val/test SETS
BY PATTERN ID before any example is generated (same principle as
experiments/m4_2/generate_training_data.py's split, independently seeded
here since this is a different corpus/task) -- no pattern contributes
examples to more than one split.
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np

from engine.dataset import list_pattern_ids, load_kolam
from engine.motifs import induce_motif_set_adaptive, interior_points
from engine.novel_generation import (
    _UnionFind,
    _connectivity_effect,
    _parity_effect,
    _stamp_contribution,
    extract_motif_library,
)
from engine.symmetry import D4_TRANSFORMS
from engine.learned_scoring import extract_features

SEED = 5252  # independent of m4_2's 4242 -- different corpus/task, no reason to share
MAX_MULTIPLICITY = 2  # same dataset-wide ceiling engine.novel_generation uses
NEG_PER_POS_CAP = 4  # subsample negatives per pattern to bound dataset size / class imbalance
MAX_EXAMPLES_PER_PATTERN = 6000

OUT_DIR = Path(__file__).resolve().parent / "data"
DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "kolam_data"


def _split_pattern_ids() -> dict:
    pool = [("kolam19", pid) for pid in list_pattern_ids("kolam19")]
    pool += [("kolam29", pid) for pid in list_pattern_ids("kolam29")]
    rng = random.Random(SEED)
    rng.shuffle(pool)

    n = len(pool)
    n_train = int(n * 0.7)
    n_val = int(n * 0.15)
    train = pool[:n_train]
    val = pool[n_train : n_train + n_val]
    test = pool[n_train + n_val :]

    assert not (set(train) & set(val) & set(test))
    assert not (set(train) & set(val))
    assert not (set(train) & set(test))
    assert not (set(val) & set(test))

    return {"train": train, "val": val, "test": test}


def _replay_pattern(collection: str, pattern_id: int, rng: random.Random) -> tuple[np.ndarray, np.ndarray]:
    pattern = load_kolam(collection, pattern_id)
    dots = pattern.dot_points
    n_dots = len(dots)
    interior = interior_points(dots, radius=1)

    placements, _residual, _full = induce_motif_set_adaptive(pattern)
    motif_library = extract_motif_library(placements)
    if not motif_library or not interior:
        return np.empty((0, 16), dtype=np.float32), np.empty((0,), dtype=np.float32)

    ground_truth = Counter(frozenset(e) for e in pattern.graph.edges())

    accumulated: Counter = Counter()
    degree: Counter = Counter()
    uf = _UnionFind(dots)
    touched_dots: set = set()
    any_real_structure_exists = False

    candidate_keys = [
        (point, motif, transform)
        for point in sorted(interior)
        for motif in motif_library
        for transform in sorted(D4_TRANSFORMS)
    ]

    pos_features, neg_features = [], []

    for point, motif, transform in candidate_keys:
        contribution = _stamp_contribution(motif, point, transform, dots)
        if not contribution:
            continue
        if any(accumulated.get(e, 0) + c > MAX_MULTIPLICITY for e, c in contribution.items()):
            continue  # structurally excluded at generation time too -- not a labeled decision

        label = 1.0 if all(
            ground_truth.get(e, 0) >= accumulated.get(e, 0) + c for e, c in contribution.items()
        ) else 0.0

        conn_effect = _connectivity_effect(uf, contribution)
        parity_effect = _parity_effect(degree, contribution)
        progress_frac = len(touched_dots) / n_dots if n_dots else 0.0
        n_odd = sum(1 for d in degree.values() if d % 2 == 1)
        global_odd_frac = n_odd / n_dots if n_dots else 0.0

        feats = extract_features(
            motif_len=len(motif),
            contribution=contribution,
            degree_before=degree,
            connectivity_effect=conn_effect,
            parity_effect=parity_effect,
            any_real_structure_exists=any_real_structure_exists,
            progress_frac=progress_frac,
            global_odd_frac=global_odd_frac,
        )
        (pos_features if label == 1.0 else neg_features).append(feats)

        if label == 1.0:
            for edge, count in contribution.items():
                accumulated[edge] += count
                a, b = tuple(edge)
                degree[a] += count
                degree[b] += count
                touched_dots.add(a)
                touched_dots.add(b)
                uf.union(a, b)
            any_real_structure_exists = True

    rng.shuffle(neg_features)
    cap = min(len(neg_features), max(len(pos_features) * NEG_PER_POS_CAP, 50))
    neg_features = neg_features[:cap]

    all_feats = pos_features + neg_features
    all_labels = [1.0] * len(pos_features) + [0.0] * len(neg_features)

    if len(all_feats) > MAX_EXAMPLES_PER_PATTERN:
        idx = list(range(len(all_feats)))
        rng.shuffle(idx)
        idx = idx[:MAX_EXAMPLES_PER_PATTERN]
        all_feats = [all_feats[i] for i in idx]
        all_labels = [all_labels[i] for i in idx]

    if not all_feats:
        return np.empty((0, 16), dtype=np.float32), np.empty((0,), dtype=np.float32)
    return np.stack(all_feats), np.array(all_labels, dtype=np.float32)


def build_split(patterns: list[tuple[str, int]], rng: random.Random) -> tuple[np.ndarray, np.ndarray, dict]:
    feats_list, labels_list = [], []
    n_patterns_used = 0
    for collection, pid in patterns:
        X, y = _replay_pattern(collection, pid, rng)
        if len(X) == 0:
            continue
        feats_list.append(X)
        labels_list.append(y)
        n_patterns_used += 1
    if not feats_list:
        return np.empty((0, 16), dtype=np.float32), np.empty((0,), dtype=np.float32), {"n_patterns_used": 0}
    X = np.concatenate(feats_list)
    y = np.concatenate(labels_list)
    stats = {
        "n_patterns_used": n_patterns_used,
        "n_examples": int(len(X)),
        "n_positive": int(y.sum()),
        "n_negative": int(len(y) - y.sum()),
        "positive_rate": float(y.mean()) if len(y) else None,
    }
    return X, y, stats


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    splits = _split_pattern_ids()
    manifest = {
        name: [f"{c}#{p}" for c, p in ids] for name, ids in splits.items()
    }
    manifest["seed"] = SEED
    manifest["n_total_patterns"] = sum(len(v) for v in splits.values())

    rng = random.Random(SEED)
    t0 = time.time()
    report = {}
    for name, patterns in splits.items():
        X, y, stats = build_split(patterns, rng)
        np.savez_compressed(OUT_DIR / f"{name}.npz", X=X, y=y)
        report[name] = stats
        print(name, stats)

    report["elapsed_seconds"] = round(time.time() - t0, 1)
    (OUT_DIR / "split_manifest.json").write_text(json.dumps(manifest, indent=2))
    (OUT_DIR / "build_report.json").write_text(json.dumps(report, indent=2))
    print("done in", report["elapsed_seconds"], "s")


if __name__ == "__main__":
    main()
