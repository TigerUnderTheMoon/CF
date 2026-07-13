"""Tests for the same-supervision structure-only Ridge experiment."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_structure_only_baseline.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_structure_only_baseline", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_structure_only_feature_set_excludes_position_and_lexical_fields():
    baseline = _load_script_module()

    assert "relative_position" not in baseline.STRUCTURE_GRAPH_FEATURES
    assert "is_last_step" not in baseline.STRUCTURE_GRAPH_FEATURES
    assert "raw_local_utility" not in baseline.STRUCTURE_GRAPH_FEATURES
    assert set(baseline.POSITION_FEATURES) == {
        "relative_position",
        "is_first_step",
        "is_last_step",
        "log_step_count",
    }


def test_closed_form_ridge_recovers_simple_monotonic_signal():
    baseline = _load_script_module()
    feature_rows = [
        [{"x": 0.0}, {"x": 1.0}],
        [{"x": 2.0}, {"x": 3.0}],
    ]
    labels = [[0.0, 1.0], [2.0, 3.0]]

    model = baseline.fit_ridge(feature_rows, labels, ["x"], ridge_lambda=0.0)
    predictions = baseline.predict_ridge([{"x": 0.5}, {"x": 2.5}], model)

    assert np.allclose(predictions, [0.5, 2.5], atol=1e-10)
