# Future ML Work

Observations from the 2026-08-14 product-hardening audit that are **ML-relevant but out of scope for that audit** (which was product hardening only — no changes to M4.2/M5/M6 architecture, checkpoints, or training data were made or are proposed here). Documented for whoever next picks up M5.1/M6 V2 research.

## Carried forward from prior sessions (not re-investigated this audit, still open)

- **M6 exact-structural-sequence leakage.** ~2% of M6's train/test and train/val splits (25 + 29 out of ~5593/1196 unique structures) are exact-duplicate small structures produced by D4/crop augmentation coincidentally generating identical output from different source patterns. Pattern-ID-level split disjointness is clean (0 overlap); this is a narrower, augmentation-induced overlap. Documented, unfixed, correctly left untouched as M6 research data.

## New observation from this audit (single data point, not a finding)

- A single live `/api/v1/generations` request during this audit returned `novelty_score: 1.0` with `nearest_source_id: null`. That's consistent with the documented behavior (`api/main.py`'s `/api/v1/generate` docstring: "no ground-truth comparison performed per-request; see the M5 benchmark report for aggregate novelty measurement") — i.e., `novelty_score` on the live per-request path is not computed against a corpus, only aggregate benchmark runs do that comparison. This is not a bug in the product layer; it's a reminder that **per-request novelty scoring against real source patterns is not yet implemented** and would be a genuine M5/M6-adjacent research task if "how novel is this specific generated pattern" needs to be a real-time, per-candidate answer rather than an aggregate benchmark statistic.

## Not investigated this audit (would require actual ML work, correctly out of scope)

- Whether M5's ~5–55s per-candidate latency has room for algorithmic speedup (e.g., early-exit on the multi-restart search, caching motif-library lookups across requests) without touching model architecture. This is a legitimate future optimization question but was not explored here since even profiling it risks scope creep into "tuning the generator," which this audit was explicitly told not to do.
- Whether `PhotoVerifier`'s honest `UNRESOLVED` status for real-photo precision/recall could be resolved with a small labeled evaluation set — flagged in the production readiness report as a known limitation, not attempted here (would require new data collection, explicitly out of scope for a hardening pass).
