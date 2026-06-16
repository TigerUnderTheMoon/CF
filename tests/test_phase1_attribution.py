from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fma.ciu.estimator import compute_ciu_records
from fma.eval.attribution_metrics import build_phase1_eval_report, write_phase1_eval_report
from fma.fma.aggregator import aggregate_fma, bucket_ciu_distribution


class Phase1AttributionTests(unittest.TestCase):
    def test_ciu_alignment_and_fallback_fields(self) -> None:
        original_records = [
            {
                "sample_id": "gsm8k_1",
                "task_type": "gsm8k",
                "correctness": True,
                "reasoning_trace": "one two three four",
                "reflection_spans": [
                    {"start_token": 1, "end_token": 3, "reflection_type": "self-reflection"}
                ],
            },
            {
                "task_id": "math-1",
                "correctness": False,
                "generation_config": {"dataset": "math"},
                "reflection_spans": [
                    {"start_token": 0, "end_token": 1, "operation_type": "error-diagnosis"}
                ],
            },
        ]
        intervened_records = [
            {"sample_id": "gsm8k_1", "counterfactual_correctness": False, "original_token_count": 4},
            {"task_id": "math-1", "intervened_correctness": False, "original_token_count": 2},
        ]

        records = compute_ciu_records(original_records, intervened_records)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["sample_id"], "gsm8k_1")
        self.assertEqual(records[0]["operation_type"], "self-reflection")
        self.assertEqual(records[0]["ciu"], 1.0)
        self.assertEqual(records[0]["span_length"], 2)
        self.assertEqual(records[1]["sample_id"], "math-1")
        self.assertEqual(records[1]["task_type"], "math")
        self.assertEqual(records[1]["ciu"], 0.0)

    def test_ciu_missing_pair_fails(self) -> None:
        original_records = [
            {"sample_id": "gsm8k_1", "correctness": True, "reflection_spans": [{"start_token": 0, "end_token": 1}]}
        ]
        with self.assertRaisesRegex(ValueError, "No intervened record"):
            compute_ciu_records(original_records, [])

    def test_ciu_missing_counterfactual_correctness_fails(self) -> None:
        original_records = [
            {"sample_id": "gsm8k_1", "correctness": True, "reflection_spans": [{"start_token": 0, "end_token": 1}]}
        ]
        intervened_records = [{"sample_id": "gsm8k_1"}]
        with self.assertRaisesRegex(ValueError, "lacks counterfactual_correctness"):
            compute_ciu_records(original_records, intervened_records)

    def test_ciu_accepts_continuous_utility_outcomes(self) -> None:
        original_records = [
            {
                "sample_id": "gsm8k_1",
                "original_utility": 0.8,
                "reflection_spans": [{"start_token": 0, "end_token": 1}],
            }
        ]
        intervened_records = [{"sample_id": "gsm8k_1", "intervened_utility": 0.3}]

        records = compute_ciu_records(original_records, intervened_records)

        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0]["original_outcome"], 0.8)
        self.assertAlmostEqual(records[0]["intervened_outcome"], 0.3)
        self.assertAlmostEqual(records[0]["ciu"], 0.5)

    def test_ciu_rejects_non_binary_correctness(self) -> None:
        original_records = [
            {"sample_id": "gsm8k_1", "correctness": True, "reflection_spans": [{"start_token": 0, "end_token": 1}]}
        ]
        intervened_records = [{"sample_id": "gsm8k_1", "intervened_correctness": 0.5}]
        with self.assertRaisesRegex(ValueError, "must be boolean or 0/1"):
            compute_ciu_records(original_records, intervened_records)

    def test_ciu_rejects_outcome_outside_unit_interval(self) -> None:
        original_records = [
            {"sample_id": "gsm8k_1", "original_outcome": 1.1, "reflection_spans": [{"start_token": 0, "end_token": 1}]}
        ]
        intervened_records = [{"sample_id": "gsm8k_1", "intervened_outcome": 0.0}]
        with self.assertRaisesRegex(ValueError, r"must be numeric in \[0, 1\]"):
            compute_ciu_records(original_records, intervened_records)

    def test_fma_normalization_and_tie_handling(self) -> None:
        ciu_results = [
            {"task_type": "gsm8k", "operation_type": "self-reflection", "ciu": 1.0},
            {"task_type": "gsm8k", "operation_type": "self-reflection", "ciu": 0.0},
            {"task_type": "gsm8k", "operation_type": "plan_revision", "ciu": -1.0},
            {"task_type": "math", "operation_type": "self-reflection", "ciu": 0.0},
            {"task_type": "math", "operation_type": "plan_revision", "ciu": 0.0},
        ]

        scores, _ = aggregate_fma(ciu_results)
        by_key = {(record["task_distribution"], record["span_type"]): record for record in scores}

        self.assertEqual(by_key[("gsm8k", "self-reflection")]["fma_score"], 1.0)
        self.assertEqual(by_key[("gsm8k", "plan_revision")]["fma_score"], 0.0)
        self.assertEqual(by_key[("math", "self-reflection")]["fma_score"], 0.5)
        self.assertEqual(by_key[("math", "plan_revision")]["fma_score"], 0.5)

    def test_distribution_buckets(self) -> None:
        buckets = bucket_ciu_distribution(
            [{"ciu": -1.0}, {"ciu": 0.0}, {"ciu": 0.2}, {"ciu": 1.0}]
        )
        self.assertEqual(buckets, {"high": 1, "medium": 1, "low": 1, "negative": 1})

    def test_eval_report_creation(self) -> None:
        ciu_results = [
            {
                "sample_id": "gsm8k_1",
                "task_type": "gsm8k",
                "operation_type": "self-reflection",
                "ciu": 1.0,
                "span_length": 4,
                "step_index": 0.25,
                "intervened_outcome": 0.0,
            },
            {
                "sample_id": "gsm8k_2",
                "task_type": "gsm8k",
                "operation_type": "plan_revision",
                "ciu": 0.0,
                "span_length": 2,
                "step_index": 0.5,
                "intervened_outcome": 1.0,
            },
        ]
        fma_scores = [
            {"span_type": "self-reflection", "task_distribution": "gsm8k", "fma_score": 1.0},
            {"span_type": "plan_revision", "task_distribution": "gsm8k", "fma_score": 0.0},
        ]

        report = build_phase1_eval_report(ciu_results, fma_scores)
        self.assertEqual(report["experiment"], "phase1_attribution")
        self.assertIn("intervention_sensitivity", report)
        self.assertIn("utility_calibration", report)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            ciu_path = tmp_path / "ciu.jsonl"
            fma_path = tmp_path / "fma.jsonl"
            report_path = tmp_path / "report.json"
            ciu_path.write_text(
                "".join(json.dumps(record) + "\n" for record in ciu_results),
                encoding="utf-8",
            )
            fma_path.write_text(
                "".join(json.dumps(record) + "\n" for record in fma_scores),
                encoding="utf-8",
            )
            written_report = write_phase1_eval_report(ciu_path, fma_path, report_path)
            self.assertTrue(report_path.exists())
            self.assertEqual(written_report["dataset_counts"], {"gsm8k": 2})


if __name__ == "__main__":
    unittest.main()
