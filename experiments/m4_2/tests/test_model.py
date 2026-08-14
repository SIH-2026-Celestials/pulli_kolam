"""M4.2 Phase K: model-level tests. Run with KMP_DUPLICATE_LIB_OK=TRUE
(see PROJECT_STATE.md's documented OpenMP finding) whenever combined
with engine.image_io in the same process."""

from __future__ import annotations

import os
import sys

import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from experiments.m4_2.model import DotHeatmapNetV2, MODEL_INPUT_SIZE, HEATMAP_SIZE, OUTPUT_STRIDE, make_gaussian_heatmap  # noqa: E402


def test_output_shape_is_native_128x128():
    model = DotHeatmapNetV2()
    model.eval()
    x = torch.zeros((1, 1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
    with torch.no_grad():
        out = model(x)
    assert HEATMAP_SIZE == 128
    assert out.shape == (1, 1, 128, 128)


def test_output_stride_is_two_not_eight():
    # the whole point of M4.2 vs M4.1: native finer output, not an
    # upsampled coarse one.
    assert OUTPUT_STRIDE == 2
    assert MODEL_INPUT_SIZE // OUTPUT_STRIDE == HEATMAP_SIZE


def test_deterministic_inference_same_weights_same_input():
    model = DotHeatmapNetV2()
    model.eval()
    x = torch.rand((1, 1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
    with torch.no_grad():
        out_a = model(x)
        out_b = model(x)
    assert torch.equal(out_a, out_b)


def test_serialization_round_trip_preserves_output():
    import tempfile
    model = DotHeatmapNetV2()
    model.eval()
    x = torch.rand((1, 1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
    with torch.no_grad():
        out_before = model(x)

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ckpt.pt")
        torch.save(model.state_dict(), path)

        reloaded = DotHeatmapNetV2()
        reloaded.load_state_dict(torch.load(path, map_location="cpu"))
        reloaded.eval()
        with torch.no_grad():
            out_after = reloaded(x)

    assert torch.equal(out_before, out_after)


def test_gaussian_heatmap_peak_at_dot_position():
    heatmap = make_gaussian_heatmap([(10.0, 20.0)], 32, 32, sigma=1.2)
    import numpy as np
    peak_row, peak_col = np.unravel_index(int(heatmap.argmax()), heatmap.shape)
    assert (peak_row, peak_col) == (20, 10)  # (y, x) -> (row, col)
    assert heatmap.max() > 0.99  # exact-position Gaussian peak ~= 1.0


def test_gaussian_heatmap_empty_dots_is_all_zero():
    heatmap = make_gaussian_heatmap([], 32, 32)
    assert float(heatmap.max()) == 0.0


def test_model_parameter_count_documented_and_stable():
    model = DotHeatmapNetV2()
    # regression guard: catches accidental architecture changes: exact
    # count measured and documented in docs/M4_2_MODEL.md
    assert model.n_parameters() == 382769
