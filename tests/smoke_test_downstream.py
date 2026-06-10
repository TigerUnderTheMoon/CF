"""Smoke test: verify open-source data loading and FMA pipeline integration.

Usage:
  python tests/smoke_test_downstream.py
  python tests/smoke_test_downstream.py --source prm800k --max-samples 5
  python tests/smoke_test_downstream.py --source gsm8k_cot --max-samples 5
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.data import load_open_traces  # noqa: E402
from fma.eval.open_trace_converter import (  # noqa: E402
    open_traces_to_internal_format,
    open_traces_to_utility_annotations,
)
from fma.eval.counterfactual_attribution import UTILITY_NUMERIC  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("smoke_test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test downstream pipeline")
    parser.add_argument("--source", type=str, default="prm800k")
    parser.add_argument("--max-samples", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs" / "smoke_test")
    return parser.parse_args()


def test_data_loading(source: str, max_samples: int) -> dict[str, Any]:
    """Test that data can be loaded from the specified source."""
    logger.info("Loading %d samples from %s", max_samples, source)
    try:
        records = load_open_traces(
            source=source,
            max_samples=max_samples,
            classify_operations=True,
        )
    except ImportError as e:
        logger.info("SKIP: dependencies not available: %s", e)
        return {"status": "skipped", "reason": str(e)}
    except Exception as e:
        logger.error("FAIL: data loading: %s", e)
        return {"status": "failed", "reason": str(e)}

    logger.info("PASS: Loaded %d records", len(records))

    model_counts: dict[str, int] = {}
    for r in records:
        model_counts[r.model_name] = model_counts.get(r.model_name, 0) + 1

    span_counts = [len(r.step_annotations) for r in records]
    logger.info("  models: %s", model_counts)
    logger.info("  spans per trace: min=%d max=%d mean=%.1f",
                 min(span_counts) if span_counts else 0,
                 max(span_counts) if span_counts else 0,
                 sum(span_counts) / len(span_counts) if span_counts else 0)

    return {"status": "passed", "n_records": len(records), "models": model_counts}


def test_conversion(source: str) -> dict[str, Any]:
    """Test that records can be converted to annotation/internal format."""
    try:
        records = load_open_traces(source=source, max_samples=3, classify_operations=True)
    except ImportError as e:
        return {"status": "skipped", "reason": str(e)}

    if not records:
        return {"status": "failed", "reason": "no records loaded"}

    try:
        annotations = open_traces_to_utility_annotations(records)
        internal = open_traces_to_internal_format(records)
    except Exception as e:
        logger.error("FAIL: conversion: %s", e)
        return {"status": "failed", "reason": str(e)}

    logger.info("PASS: Converted %d records -> %d annotations, %d traces",
                 len(records), len(annotations), len(internal))

    return {"status": "passed", "n_annotations": len(annotations)}


def test_fma_computation(source: str) -> dict[str, Any]:
    """Test that FMA CIU scores can be computed via per-step utility."""
    try:
        records = load_open_traces(source=source, max_samples=3, classify_operations=True)
    except ImportError as e:
        return {"status": "skipped", "reason": str(e)}

    if not records:
        return {"status": "failed", "reason": "no records loaded"}

    annotations = open_traces_to_utility_annotations(records)

    grouped: dict[str, list[tuple[int, float]]] = {}
    for ann in annotations:
        grouped.setdefault(ann.trace_id, []).append(
            (ann.reflection_idx, UTILITY_NUMERIC[ann.utility])
        )

    ciu_all: list[float] = []
    for steps in grouped.values():
        for _, u in steps:
            ciu_all.append(u)

    nonzero = sum(1 for s in ciu_all if abs(s) > 1e-6)
    logger.info("PASS: Computed %d CIU scores (%d nonzero) across %d traces",
                 len(ciu_all), nonzero, len(grouped))

    return {
        "status": "passed",
        "n_scores": len(ciu_all),
        "n_nonzero": nonzero,
        "n_traces": len(grouped),
    }


def run_all_tests(args: argparse.Namespace) -> dict[str, Any]:
    results: dict[str, Any] = {}

    results["data_loading"] = test_data_loading(args.source, args.max_samples)
    results["conversion"] = test_conversion(args.source)
    results["fma_computation"] = test_fma_computation(args.source)

    passed = sum(
        1 for v in results.values()
        if isinstance(v, dict) and v.get("status") == "passed"
    )
    failed = sum(
        1 for v in results.values()
        if isinstance(v, dict) and v.get("status") == "failed"
    )
    skipped = sum(
        1 for v in results.values()
        if isinstance(v, dict) and v.get("status") == "skipped"
    )

    logger.info("=== SUMMARY ===")
    logger.info("  Passed: %d  Failed: %d  Skipped: %d", passed, failed, skipped)

    if failed:
        logger.error("SMOKE TEST FAILED")
    elif skipped:
        logger.warning("SMOKE TEST INCOMPLETE (some skipped)")
    else:
        logger.info("SMOKE TEST PASSED")

    return results


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_all_tests(args)


if __name__ == "__main__":
    main()
