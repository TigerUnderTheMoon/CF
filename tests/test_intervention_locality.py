from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path

from fma.eval.intervention_locality import (
    build_locality_probe_report,
    normalized_edit_distance,
    pair_records,
    run_locality_probe,
    sample_control_intervention,
)


class InterventionLocalityTests(unittest.TestCase):
    def test_pairs_by_sample_id_even_when_order_differs(self) -> None:
        originals = [{"sample_id": "a"}, {"sample_id": "b"}]
        counterfactuals = [{"sample_id": "b"}, {"sample_id": "a"}]

        pairs = pair_records(originals, counterfactuals)

        self.assertEqual([pair[1]["sample_id"] for pair in pairs], ["a", "b"])

    def test_control_mask_excludes_reflection_and_preserves_token_count(self) -> None:
        record = {
            "reasoning_trace": "one two reflect now five six",
            "reflection_spans": [{"start_token": 2, "end_token": 4}],
        }

        intervention = sample_control_intervention(record, random.Random(7))

        self.assertIsNotNone(intervention)
        assert intervention is not None
        self.assertEqual(len(intervention["masked_trace"].split()), 6)
        self.assertFalse(2 <= intervention["start_token"] < 4)
        self.assertNotEqual((intervention["start_token"], intervention["end_token"]), (2, 4))

    def test_control_mask_supports_structured_steps(self) -> None:
        record = {
            "steps": [
                {"text": "one two", "step_type": "reasoning"},
                {"text": "reflect now", "step_type": "metacognition"},
                {"text": "five six", "step_type": "reasoning"},
            ],
            "reflection_spans": [{"start_token": 2, "end_token": 4}],
        }

        intervention = sample_control_intervention(record, random.Random(1))

        self.assertIsNotNone(intervention)
        assert intervention is not None
        self.assertEqual(len(intervention["masked_trace"].split()), 6)
        self.assertNotEqual((intervention["start_token"], intervention["end_token"]), (2, 4))

    def test_normalized_edit_distance_is_bounded(self) -> None:
        self.assertEqual(normalized_edit_distance(["a"], ["a"]), 0.0)
        self.assertEqual(normalized_edit_distance([], ["a", "b"]), 1.0)
        self.assertLessEqual(normalized_edit_distance(["a", "b"], ["c"]), 1.0)

    def test_report_skips_records_without_reflection_intervention(self) -> None:
        originals = [
            {
                "sample_id": "plain",
                "correctness": True,
                "reasoning_trace": "one two Final Answer: 2",
                "reflection_spans": [],
            }
        ]
        counterfactuals = [{"sample_id": "plain", "counterfactual_correctness": True}]

        report = build_locality_probe_report(originals, counterfactuals)

        self.assertEqual(report["reflection_ciu_mean"], 0.0)
        self.assertEqual(report["benign_local_perturbation_count"], 0)

    def test_report_computes_specificity_drift_and_counts(self) -> None:
        originals = [
            {
                "sample_id": "targeted",
                "correctness": True,
                "final_answer": "4",
                "reasoning_trace": "one two reflect now five six Final Answer: 4",
                "reflection_spans": [{"start_token": 2, "end_token": 4}],
            },
            {
                "sample_id": "benign",
                "correctness": True,
                "final_answer": "8",
                "reasoning_trace": "a b reflect now c d Final Answer: 8",
                "reflection_spans": [{"start_token": 2, "end_token": 4}],
            },
            {
                "sample_id": "artifact",
                "correctness": True,
                "final_answer": "9",
                "reasoning_trace": "p q reflect now r s Final Answer: 9",
                "reflection_spans": [{"start_token": 2, "end_token": 4}],
            },
            {
                "sample_id": "rewrite",
                "correctness": True,
                "final_answer": "10",
                "reasoning_trace": "h i reflect now j k Final Answer: 10",
                "reflection_spans": [{"start_token": 2, "end_token": 4}],
            },
        ]
        counterfactuals = [
            {
                "sample_id": "targeted",
                "counterfactual_correctness": False,
                "counterfactual_answer": "5",
                "counterfactual_trace": "one two MASK MASK five six Final Answer: 5",
                "control_ciu": 0.0,
            },
            {
                "sample_id": "benign",
                "counterfactual_correctness": True,
                "counterfactual_answer": "8",
                "counterfactual_trace": "a b MASK MASK c d Final Answer: 8",
                "control_ciu": 0.0,
            },
            {
                "sample_id": "artifact",
                "counterfactual_correctness": True,
                "counterfactual_answer": "9",
                "counterfactual_trace": "totally different downstream words here Final Answer: 9",
                "control_ciu": 0.0,
            },
            {
                "sample_id": "rewrite",
                "counterfactual_correctness": False,
                "counterfactual_answer": "11",
                "counterfactual_trace": "totally different downstream words here Final Answer: 11",
                "control_ciu": 0.0,
            },
        ]

        report = build_locality_probe_report(originals, counterfactuals, seed=1)

        self.assertEqual(report["reflection_ciu_mean"], 0.5)
        self.assertEqual(report["control_ciu_mean"], 0.0)
        self.assertEqual(report["specificity_gap"], 0.5)
        self.assertEqual(report["functional_influence_count"], 1)
        self.assertEqual(report["benign_local_perturbation_count"], 1)
        self.assertEqual(report["drift_artifact_count"], 1)
        self.assertEqual(report["unstable_global_rewrite_count"], 1)
        self.assertIn("approximate proxies", report["interpretation"][-1])

    def test_run_locality_probe_writes_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            trace_path = tmp_path / "reflection_traces.jsonl"
            counterfactual_path = tmp_path / "counterfactual_results.jsonl"
            output_path = tmp_path / "locality_probe.json"
            trace_record = {
                "sample_id": "x",
                "correctness": True,
                "final_answer": "1",
                "reasoning_trace": "a b reflect now c Final Answer: 1",
                "reflection_spans": [{"start_token": 2, "end_token": 4}],
            }
            counterfactual_record = {
                "sample_id": "x",
                "counterfactual_correctness": False,
                "counterfactual_answer": "2",
                "counterfactual_trace": "a b MASK MASK c Final Answer: 2",
            }
            trace_path.write_text(json.dumps(trace_record) + "\n", encoding="utf-8")
            counterfactual_path.write_text(json.dumps(counterfactual_record) + "\n", encoding="utf-8")

            report = run_locality_probe(trace_path, counterfactual_path, output_path, seed=42)

            self.assertTrue(output_path.exists())
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(written["specificity_gap"], report["specificity_gap"])


if __name__ == "__main__":
    unittest.main()
