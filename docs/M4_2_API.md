# M4.2 REST API

`api/main.py` - new FastAPI service, the first backend server in this
repository (verified in Phase A's audit: none existed before). Run
locally with:

```
KMP_DUPLICATE_LIB_OK=TRUE uvicorn api.main:app --reload
```

(`KMP_DUPLICATE_LIB_OK` is set inside `api/main.py` itself at import
time - the `uvicorn` prefix above is redundant but harmless; see
`docs/M4_2_MODEL.md`'s "Known environment requirement.")

## Conventions

- All detection/analysis endpoints accept `multipart/form-data` with an
  `image` file field and an optional `detector` form field
  (`classical` | `ml`), **defaulting to `classical`** - never `ml` by
  default, per the production-fallback rule.
- Detected coordinates are always in the **original, as-uploaded
  image's** pixel space - never the model-input-resized or
  heatmap-cell space, and specifically un-rotated back through
  `preprocess()`'s own deskew rotation so overlays align with the image
  the user actually sees (see `api/detectors.py`'s module docstring).
- No silent fallback: if `detector=ml` is requested and the ML detector
  is unavailable (missing checkpoint, load failure, inference error),
  the response is HTTP 503 with an explicit error message - never a
  silent substitution of the classical result.
- No NetworkX/engine-internal objects are ever serialized - see
  `api/canonical.py`.
- Uploaded images are written to a temp file for the duration of one
  request and deleted immediately after; never logged or persisted.

## `GET /api/v1/health`

```json
{"status": "ok", "classical_detector_available": true, "ml_detector_available": true}
```

`ml_detector_available` reflects whether a checkpoint file exists on
disk - not whether it has been load-tested.

## `GET /api/v1/model`

```json
{
  "ml_model_version": "m4.2-128",
  "ml_checkpoint_exists": true,
  "ml_model_input_size": 256,
  "ml_heatmap_size": 128,
  "classical_detector": "engine.image_io.detect_lattice (deterministic)"
}
```

## `POST /api/v1/detect`

Form fields: `image` (file, required), `detector` (`classical`|`ml`,
default `classical`).

```json
{
  "success": true,
  "detector": "ml",
  "model_version": "m4.2-128",
  "image": {"width": 900, "height": 900},
  "detections": [{"x": 123.4, "y": 456.7}],
  "count": 184,
  "processing_ms": 142.3
}
```

Errors: `400` invalid/empty/unsupported image, `503` ML detector
unavailable, `500` unexpected detector failure (message includes the
exception type, never swallowed).

## `POST /api/v1/analyze`

Same form fields as `/detect`. Runs detection, then graph
construction, motif induction, and validity checking through the
UNCHANGED deterministic engine (`engine.motifs`, `engine.validity`).

```json
{
  "success": true,
  "detector": "classical",
  "model_version": null,
  "dots": [{"x": 123.4, "y": 456.7}],
  "dot_count": 184,
  "processing_ms": 142.3,
  "graph": {"nodes": 184, "edges": 310, "distinct_edges": 228},
  "motifs": {"motif_count": 11},
  "validity": {"is_eulerian_circuit": false, "has_eulerian_path": false,
               "connected_components": 1, "largest_component_covers_all_nodes": true}
}
```

## `POST /api/v1/reconstruct`

Same form fields. Builds a minimal `KolamPattern` from the detected
graph (`api/reconstruct_adapter.py` - see its docstring for the honesty
note: this uses dot positions as a stand-in trace, NOT a real CSV
polyline, since a photo has no such trace; `collection="uploaded"`
marks this provenance explicitly) and runs
`engine.reconstruction.reconstruct_kolam` against it.

```json
{
  "success": true,
  "detector": "classical",
  "model_version": null,
  "processing_ms": 180.1,
  "graph": {"nodes": 184, "edges": 310, "distinct_edges": 228},
  "reconstruction": {
    "is_valid": false,
    "motif_edges": 208,
    "residual_edges": 20,
    "capped_excess_pairs": 74,
    "connectivity": {"connected_components": 1, "largest_component_covers_all_nodes": true},
    "validity": {"...": "..."}
  }
}
```

## `POST /api/v1/compare-detectors`

Form field: `image` only (runs both detectors, no `detector` field).

```json
{
  "success": true,
  "image": {"width": 900, "height": 900},
  "classical": {"detector": "classical", "model_version": null, "detections": [...], "count": 184, "processing_ms": 140.2, "error": null},
  "ml": {"detector": "ml", "model_version": "m4.2-128", "detections": [...], "count": 190, "processing_ms": 95.4, "error": null},
  "agreement": {"match_tolerance_px": 6.0, "classical_count": 184, "ml_count": 190, "agreeing_dots": 178, "classical_only": 6, "ml_only": 12}
}
```

If one detector fails, its side reports `count: 0`, empty detections,
and a non-null `error` string - the other side's result is still
returned (partial success, not an all-or-nothing failure).

## Detector modes

Only `classical` and `ml` are implemented. `auto` is deliberately NOT
implemented - routing decisions need measurable evidence first (see
`docs/M4_2_EVALUATION.md`).
