"""M4.1 Phase 6: focused tests for peak_detect.py. Pure numpy, no torch,
no trained model needed -- deliberately independent of training having
run, so these are meaningful even before/without a checkpoint."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402


def test_single_clear_peak_detected():
    heatmap = np.zeros((20, 20), dtype=np.float32)
    heatmap[10, 12] = 0.9
    peaks, confidences = detect_peaks(heatmap, threshold=0.4, min_distance_px=2.0)
    assert peaks == [(10.0, 12.0)]
    assert confidences == pytest.approx([0.9], abs=1e-6)


def test_two_distant_peaks_both_detected():
    heatmap = np.zeros((20, 20), dtype=np.float32)
    heatmap[2, 2] = 0.8
    heatmap[17, 17] = 0.6
    peaks, _ = detect_peaks(heatmap, threshold=0.4, min_distance_px=2.0)
    assert set(peaks) == {(2.0, 2.0), (17.0, 17.0)}


def test_duplicate_suppression_keeps_only_the_stronger_of_two_close_peaks():
    heatmap = np.zeros((20, 20), dtype=np.float32)
    heatmap[10, 10] = 0.9
    heatmap[10, 11] = 0.7  # 1px away -- within min_distance_px, must be suppressed
    peaks, confidences = detect_peaks(heatmap, threshold=0.4, min_distance_px=3.0)
    assert peaks == [(10.0, 10.0)]
    assert confidences == pytest.approx([0.9], abs=1e-6)


def test_empty_prediction_below_threshold():
    heatmap = np.full((20, 20), 0.1, dtype=np.float32)
    peaks, confidences = detect_peaks(heatmap, threshold=0.4, min_distance_px=2.0)
    assert peaks == []
    assert confidences == []


def test_all_zero_heatmap_returns_empty():
    heatmap = np.zeros((20, 20), dtype=np.float32)
    peaks, confidences = detect_peaks(heatmap, threshold=0.01, min_distance_px=2.0)
    assert peaks == []
    assert confidences == []


def test_deterministic_across_repeated_calls():
    rng = np.random.RandomState(7)
    heatmap = rng.rand(30, 30).astype(np.float32)
    peaks_a, conf_a = detect_peaks(heatmap, threshold=0.7, min_distance_px=3.0)
    peaks_b, conf_b = detect_peaks(heatmap, threshold=0.7, min_distance_px=3.0)
    assert peaks_a == peaks_b
    assert conf_a == conf_b


def test_many_peaks_each_at_least_min_distance_apart():
    heatmap = np.zeros((40, 40), dtype=np.float32)
    for r, c, v in [(5, 5, 0.9), (5, 30, 0.85), (30, 5, 0.8), (30, 30, 0.75), (20, 20, 0.95)]:
        heatmap[r, c] = v
    peaks, confidences = detect_peaks(heatmap, threshold=0.4, min_distance_px=3.0)
    assert len(peaks) == 5
    # highest confidence found first (greedy order)
    assert confidences[0] == pytest.approx(0.95, abs=1e-6)
    # pairwise distances all exceed min_distance_px
    pts = np.array(peaks)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            assert np.linalg.norm(pts[i] - pts[j]) > 3.0
