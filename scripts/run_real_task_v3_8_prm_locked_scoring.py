"""Frozen PRM baseline scoring on the v3.6 PRM800K hash split."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import numpy as np
import yaml
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_real_task_v3_5_prm800k_validation import (  # noqa: E402
    build_feature_rows,
    bootstrap_ci,
    count_steps,
    extract_question,
    holm_correction,
    one_sided_wilcoxon_pvalue,
    pick_completion,
    predict_w_struct,
    read_json,
    safe_kendall,
    safe_spearman,
    selected_rows_hash,
    select_labeled_steps,
    stream_prm800k_rows,
    write_json,
    write_jsonl,
)
from scripts.run_real_task_v3_6_prm800k_hash_validation import assign_split  # noqa: E402


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "real_task_v3_8_prm_locked_scoring.yaml"


@dataclass(frozen=True)
class ScoringSample:
    sample_id: str
    row_index: int
    split_name: str
    question: str
    question_hash: str
    step_texts: tuple[str, ...]
    labels: tuple[float, ...]
    raw_local_utility: tuple[float, ...]
    feature_rows: tuple[dict[str, float], ...]


class StepScorer(Protocol):
    model_id: str

    def score_samples(self, samples: Sequence[ScoringSample]) -> list[list[float]]:
        ...


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=["fixture_smoke", "canary", "locked_scoring", "decision"], default="canary")
    parser.add_argument("--subset", choices=["locked", "pool"], default="locked")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--model-id", type=str, default=None)
    parser.add_argument("--model-revision", type=str, default=None)
    parser.add_argument("--scorer-backend", choices=["mock", "skywork_prefix"], default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config(args.config)
    output_dir = args.output_dir or PROJECT_ROOT / config["outputs"]["root"]
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.stage == "fixture_smoke":
        report = run_fixture_smoke(config, output_dir)
        print(json.dumps({"status": report["status"], "report": str(output_dir / "fixture_smoke_report.json")}, sort_keys=True))
        return

    if args.stage in {"canary", "locked_scoring"}:
        report = run_scoring_stage(config, args, output_dir)
        key = "canary_report" if args.stage == "canary" else "locked_report"
        print(json.dumps({"status": report["status"], "report": str(output_dir / config["outputs"][key])}, sort_keys=True))
        return

    decision = run_decision(config, output_dir)
    print(json.dumps({"status": decision["status"], "decision_report": str(output_dir / config["outputs"]["decision_report"])}, sort_keys=True))


def load_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Config is not a mapping: {path}")
    return value


def run_fixture_smoke(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    sample = ScoringSample(
        sample_id="fixture",
        row_index=0,
        split_name="fixture",
        question="Compute 2+2.",
        question_hash=hashlib.sha256(b"Compute 2+2.").hexdigest(),
        step_texts=("Let x = 2 + 2.", "Then x = 5.", "Therefore the answer is 4."),
        labels=(1.0, 0.0, 1.0),
        raw_local_utility=(0.5, 0.1, 0.8),
        feature_rows=tuple(build_feature_rows([
            {"source_step_index": 0.0, "text": "Let x = 2 + 2.", "label": 1.0},
            {"source_step_index": 1.0, "text": "Then x = 5.", "label": 0.0},
            {"source_step_index": 2.0, "text": "Therefore the answer is 4.", "label": 1.0},
        ])[0]),
    )
    scores = MockStepScorer("mock").score_samples([sample])
    report = summarize_score_rows(
        config,
        [sample],
        scores,
        model=None,
        elapsed_seconds=0.0,
        stage="fixture_smoke",
        model_revision=config["model"].get("revision"),
    )
    write_json(output_dir / "fixture_smoke_report.json", report)
    return report


def run_scoring_stage(config: Mapping[str, Any], args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    started = time.time()
    source_config = load_config(PROJECT_ROOT / config["source_route"]["config"])
    max_samples = args.max_samples
    if args.stage == "canary" and max_samples is None:
        max_samples = int(config["subsets"]["canary_samples"])
    samples, rows_hash = load_scoring_samples(source_config, args.subset, max_samples=max_samples)
    if max_samples is not None:
        samples = samples[:max_samples]

    backend = args.scorer_backend or str(config["model"]["scorer_backend"])
    model_id = args.model_id or str(config["model"]["default_model_id"])
    model_revision = args.model_revision or config["model"].get("revision")
    batch_size = int(args.batch_size or config["model"]["batch_size"])
    scorer = build_scorer(backend, model_id=model_id, model_revision=model_revision, batch_size=batch_size, config=config)
    scores = scorer.score_samples(samples)
    model = None if args.stage == "canary" else read_json(PROJECT_ROOT / config["source_route"]["dev_model"])
    report = summarize_score_rows(
        config,
        samples,
        scores,
        model=model,
        elapsed_seconds=round(time.time() - started, 3),
        stage=args.stage,
        model_id=model_id,
        model_revision=model_revision,
        subset=args.subset,
        selected_rows_sha256=rows_hash,
    )

    if args.stage == "canary":
        write_json(output_dir / config["outputs"]["canary_report"], report)
    else:
        write_jsonl(output_dir / config["outputs"]["locked_scores"], score_manifest_rows(samples, scores))
        write_json(output_dir / config["outputs"]["locked_report"], report)
    return report


def run_decision(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    locked_path = output_dir / config["outputs"]["locked_report"]
    if not locked_path.exists():
        raise FileNotFoundError(f"Missing locked report: {locked_path}")
    locked = read_json(locked_path)
    gates_pass = locked.get("status") in {"pass_strong", "pass_weak"}
    decision = {
        "status": locked.get("status", "fail"),
        "route_id": config["route"]["id"],
        "locked_status": locked.get("status"),
        "claim_permissions": {
            "M_BASELINE_COMPARISON": False,
            "M_BASELINE_COMPARISON_CONTEXT_ONLY": bool(gates_pass),
            "in_distribution_prm_baseline_context_allowed": bool(gates_pass),
            "external_generalization_claim_allowed": False,
            "F_PRM_TRAINING": False,
            "F_REAL_TASK_SC_FMA": False,
            "deterministic_replay_claim": False,
            "causal_identification_claim": False,
        },
        "claim_boundary": "in_distribution_prm_baseline_context_only",
        "next_allowed_step": (
            "REPORT_PRM_BASELINE_CONTEXT_WITH_OVERLAP_LIMITATION"
            if gates_pass
            else "FREEZE_PRM_SCORING_AS_DIAGNOSTIC_OR_FAILURE"
        ),
    }
    write_json(output_dir / config["outputs"]["decision_report"], decision)
    return decision


def load_scoring_samples(
    config: Mapping[str, Any],
    subset: str,
    *,
    max_samples: int | None = None,
) -> tuple[list[ScoringSample], str]:
    source = config["data"]["source"]
    pool = config["data"]["pool"]
    start_row = int(pool["start_row"])
    row_count = int(pool["row_count"])
    row_index_offset = int(pool.get("row_index_offset", start_row))
    if max_samples is not None:
        rows, samples = load_samples_until_limit(
            source["url"],
            start_row=start_row,
            row_count=row_count,
            row_index_offset=row_index_offset,
            subset=subset,
            split_config=config["data"]["split_strategy"],
            max_samples=max_samples,
        )
    else:
        rows = stream_prm800k_rows(source["url"], start_row=start_row, row_count=row_count)
        samples = build_scoring_samples(rows, row_start=row_index_offset)
        if subset == "locked":
            split_cfg = config["data"]["split_strategy"]
            samples = [
                sample
                for sample in samples
                if sample_in_split(sample, split_cfg, "locked")
            ]
    return samples, selected_rows_hash(rows)


def load_samples_until_limit(
    url: str,
    *,
    start_row: int,
    row_count: int,
    row_index_offset: int,
    subset: str,
    split_config: Mapping[str, Any],
    max_samples: int,
) -> tuple[list[dict[str, Any]], list[ScoringSample]]:
    import urllib.request

    rows: list[dict[str, Any]] = []
    samples: list[ScoringSample] = []
    request = urllib.request.Request(url, headers={"User-Agent": "fma-real-task-v3-8-prm-scoring"})
    with urllib.request.urlopen(request, timeout=180) as response:
        for row_index, raw_line in enumerate(response):
            if row_index < start_row:
                continue
            if row_index >= start_row + row_count:
                break
            stripped = raw_line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            rows.append(row)
            source_row_index = row_index_offset + (row_index - start_row)
            built = build_scoring_samples([row], row_start=source_row_index)
            if not built:
                continue
            sample = built[0]
            if subset == "locked" and not sample_in_split(sample, split_config, "locked"):
                continue
            samples.append(sample)
            if len(samples) >= max_samples:
                break
    return rows, samples


def sample_in_split(sample: ScoringSample, split_config: Mapping[str, Any], target: str) -> bool:
    return (
        assign_split(
            sample.sample_id,
            salt=str(split_config["salt"]),
            dev_mod_upper_exclusive=int(split_config["dev_mod_upper_exclusive"]),
        )
        == target
    )


def build_scoring_samples(rows: Sequence[Mapping[str, Any]], *, row_start: int) -> list[ScoringSample]:
    samples: list[ScoringSample] = []
    for local_index, row in enumerate(rows):
        row_index = row_start + local_index
        steps = select_labeled_steps(row)
        if len(steps) < 3:
            continue
        labels = tuple(float(step["label"]) for step in steps)
        if len(set(labels)) < 2:
            continue
        question = extract_question(row)
        qhash = hashlib.sha256(question.encode("utf-8")).hexdigest()
        feature_rows, raw_scores = build_feature_rows(steps)
        samples.append(
            ScoringSample(
                sample_id=f"prm800k_pool_{row_index:06d}_{qhash[:10]}",
                row_index=row_index,
                split_name="pool",
                question=question,
                question_hash=qhash,
                step_texts=tuple(str(step["text"]) for step in steps),
                labels=labels,
                raw_local_utility=tuple(float(v) for v in raw_scores),
                feature_rows=tuple(feature_rows),
            )
        )
    return samples


def build_scorer(
    backend: str,
    *,
    model_id: str,
    model_revision: str | None,
    batch_size: int,
    config: Mapping[str, Any],
) -> StepScorer:
    if backend == "mock":
        return MockStepScorer(model_id)
    if backend == "skywork_prefix":
        return SkyworkPrefixRewardScorer(
            model_id=model_id,
            model_revision=model_revision,
            batch_size=batch_size,
            max_seq_length=int(config["model"]["max_seq_length"]),
            dtype=str(config["model"]["dtype"]),
        )
    raise ValueError(f"Unknown scorer backend: {backend}")


class MockStepScorer:
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id

    def score_samples(self, samples: Sequence[ScoringSample]) -> list[list[float]]:
        all_scores: list[list[float]] = []
        for sample in samples:
            scores = []
            for idx, text in enumerate(sample.step_texts):
                digest = hashlib.sha256(f"{sample.sample_id}|{idx}|{text}".encode("utf-8")).digest()
                scores.append(int.from_bytes(digest[:4], "big") / float(2**32 - 1))
            all_scores.append(scores)
        return all_scores


class SkyworkPrefixRewardScorer:
    def __init__(
        self,
        *,
        model_id: str,
        model_revision: str | None,
        batch_size: int,
        max_seq_length: int,
        dtype: str,
    ) -> None:
        self.model_id = model_id
        self.model_revision = model_revision
        self.batch_size = batch_size
        self.max_seq_length = max_seq_length
        self.dtype = dtype
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        import torch
        from transformers import AutoModel, AutoTokenizer

        try:
            from model_utils.io_utils import prepare_input, prepare_batch_input_for_model
        except ImportError as exc:
            raise ImportError(
                "Skywork prefix scorer requires skywork-o1-prm-inference on PYTHONPATH. "
                "Clone https://github.com/SkyworkAI/skywork-o1-prm-inference and export PYTHONPATH to it."
            ) from exc

        dtype = torch.bfloat16 if self.dtype == "bfloat16" else torch.float16
        self._torch = torch
        self._prepare_input = prepare_input
        self._prepare_batch = prepare_batch_input_for_model
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=self.model_revision,
            trust_remote_code=True,
        )
        self._model = AutoModel.from_pretrained(
            self.model_id,
            revision=self.model_revision,
            torch_dtype=dtype,
            device_map="auto",
            trust_remote_code=True,
        ).eval()
        self._loaded = True

    def score_samples(self, samples: Sequence[ScoringSample]) -> list[list[float]]:
        self._load()
        outputs: list[list[float]] = []
        for start in range(0, len(samples), self.batch_size):
            batch = samples[start : start + self.batch_size]
            prepared: list[tuple[int, int, list[int], list[int]]] = []
            for batch_idx, sample in enumerate(batch):
                for step_idx in range(len(sample.step_texts)):
                    response_prefix = "\n".join(sample.step_texts[: step_idx + 1])
                    input_ids, _, reward_flags = self._prepare_input(
                        sample.question,
                        response_prefix,
                        tokenizer=self._tokenizer,
                        step_token="\n",
                    )
                    if len(input_ids) <= self.max_seq_length:
                        prepared.append((batch_idx, step_idx, input_ids, reward_flags))
            by_sample: list[list[float]] = [[] for _ in batch]
            for prefix_start in range(0, len(prepared), max(1, self.batch_size)):
                chunk = prepared[prefix_start : prefix_start + max(1, self.batch_size)]
                input_ids, attention_mask, _reward_flags = self._prepare_batch(
                    [item[2] for item in chunk],
                    [item[3] for item in chunk],
                    self._tokenizer.pad_token_id,
                )
                device = next(self._model.parameters()).device
                input_ids = input_ids.to(device)
                attention_mask = attention_mask.to(device)
                with self._torch.no_grad():
                    output = self._model(input_ids=input_ids, attention_mask=attention_mask)
                logits = output.logits.detach().float().view(-1)
                probs = self._torch.sigmoid(logits).cpu().tolist()
                for (batch_idx, _step_idx, _ids, _flags), value in zip(chunk, probs, strict=False):
                    by_sample[batch_idx].append(float(value))
            outputs.extend(by_sample)
        return outputs


def summarize_score_rows(
    config: Mapping[str, Any],
    samples: Sequence[ScoringSample],
    scores: Sequence[Sequence[float]],
    *,
    model: Mapping[str, Any] | None,
    elapsed_seconds: float,
    stage: str,
    model_id: str = "mock",
    model_revision: str | None = None,
    subset: str = "fixture",
    selected_rows_sha256: str | None = None,
) -> dict[str, Any]:
    finite = 0
    total = 0
    aligned_samples: list[ScoringSample] = []
    aligned_scores: list[list[float]] = []
    failures: list[dict[str, Any]] = []
    for sample, sample_scores in zip(samples, scores, strict=False):
        total += len(sample.labels)
        finite += sum(1 for value in sample_scores if math.isfinite(float(value)))
        if len(sample_scores) != len(sample.labels):
            failures.append(
                {
                    "sample_id": sample.sample_id,
                    "reason": "step_count_mismatch",
                    "expected": len(sample.labels),
                    "observed": len(sample_scores),
                }
            )
            continue
        if any(not math.isfinite(float(value)) for value in sample_scores):
            failures.append({"sample_id": sample.sample_id, "reason": "nonfinite_score"})
            continue
        aligned_samples.append(sample)
        aligned_scores.append([float(value) for value in sample_scores])

    score_values = np.asarray([value for row in aligned_scores for value in row], dtype=float)
    finite_rate = finite / max(1, total)
    alignment_success_rate = len(aligned_samples) / max(1, len(samples))
    exclusion_rate = 1.0 - alignment_success_rate
    nonconstant = bool(score_values.size > 1 and float(np.std(score_values)) > 1e-10)
    gates_cfg = config["validation_gates"]
    gates = {
        "finite_score_rate": {
            "observed": finite_rate,
            "threshold": float(gates_cfg["min_finite_score_rate"]),
            "pass": finite_rate >= float(gates_cfg["min_finite_score_rate"]),
        },
        "alignment_success_rate": {
            "observed": alignment_success_rate,
            "threshold": float(gates_cfg["min_alignment_success_rate"]),
            "pass": alignment_success_rate >= float(gates_cfg["min_alignment_success_rate"]),
        },
        "exclusion_rate": {
            "observed": exclusion_rate,
            "threshold": float(gates_cfg["max_exclusion_rate"]),
            "pass": exclusion_rate <= float(gates_cfg["max_exclusion_rate"]),
        },
        "nonconstant_scores": {
            "observed": nonconstant,
            "pass": nonconstant if bool(gates_cfg["require_nonconstant_scores"]) else True,
        },
    }

    metrics: dict[str, Any] = {
        "n_samples": len(samples),
        "n_aligned_samples": len(aligned_samples),
        "n_steps": count_steps(aligned_samples),
        "finite_score_rate": finite_rate,
        "alignment_success_rate": alignment_success_rate,
        "exclusion_rate": exclusion_rate,
        "score_distribution": {
            "mean": float(np.mean(score_values)) if score_values.size else 0.0,
            "std": float(np.std(score_values)) if score_values.size else 0.0,
            "min": float(np.min(score_values)) if score_values.size else 0.0,
            "max": float(np.max(score_values)) if score_values.size else 0.0,
        },
    }
    if model is not None and aligned_samples:
        metrics.update(compare_prm_with_w_struct(aligned_samples, aligned_scores, model, gates_cfg))

    if model is not None and metrics.get("w_struct_minus_prm", {}).get("bootstrap_ci", {}).get("ci_lower", -1) > 0:
        status = "pass_strong" if all(gate["pass"] for gate in gates.values()) else "fail_gate"
    elif model is not None and all(gate["pass"] for gate in gates.values()):
        status = "pass_weak"
    else:
        status = "pass_canary" if all(gate["pass"] for gate in gates.values()) else "fail_gate"

    return {
        "status": status,
        "route_id": config["route"]["id"],
        "stage": stage,
        "subset": subset,
        "model_id": model_id,
        "model_revision": model_revision,
        "selected_rows_sha256": selected_rows_sha256,
        "elapsed_seconds": elapsed_seconds,
        "metrics": metrics,
        "gates": gates,
        "alignment_failures_preview": failures[:20],
        "claim_boundary": "in_distribution_prm_baseline_context_only",
        "api_calls": 0,
        "estimated_api_cost_usd": 0.0,
    }


def compare_prm_with_w_struct(
    samples: Sequence[ScoringSample],
    prm_scores: Sequence[Sequence[float]],
    model: Mapping[str, Any],
    gates_cfg: Mapping[str, Any],
) -> dict[str, Any]:
    per_sample: dict[str, list[float]] = {key: [] for key in ["w_struct", "prm", "raw_local_utility", "span_length", "relative_position"]}
    kendall: dict[str, list[float]] = {key: [] for key in per_sample}
    for sample, prm in zip(samples, prm_scores, strict=False):
        labels = np.asarray(sample.labels, dtype=float)
        scores = {
            "w_struct": predict_w_struct(sample, model),
            "prm": np.asarray(prm, dtype=float),
            "raw_local_utility": np.asarray(sample.raw_local_utility, dtype=float),
            "span_length": np.asarray([len(text.split()) for text in sample.step_texts], dtype=float),
            "relative_position": np.arange(len(labels), dtype=float),
        }
        for method, values in scores.items():
            per_sample[method].append(safe_spearman(values, labels))
            kendall[method].append(safe_kendall(values, labels))
    diff = np.asarray(per_sample["w_struct"], dtype=float) - np.asarray(per_sample["prm"], dtype=float)
    pvalue = one_sided_wilcoxon_pvalue(diff)
    holm = holm_correction([{"name": "w_struct_vs_frozen_prm", "p_value": pvalue}], alpha=float(gates_cfg["holm_alpha"]))
    return {
        "mean_spearman": {method: float(np.mean(values)) for method, values in per_sample.items()},
        "mean_kendall": {method: float(np.mean(values)) for method, values in kendall.items()},
        "w_struct_minus_prm": {
            "mean": float(np.mean(diff)),
            "bootstrap_ci": bootstrap_ci(
                diff,
                n_bootstrap=int(gates_cfg["bootstrap_samples"]),
                seed=int(gates_cfg["bootstrap_seed"]),
            ),
            "wilcoxon_one_sided_p": pvalue,
        },
        "holm_correction": holm,
    }


def score_manifest_rows(samples: Sequence[ScoringSample], scores: Sequence[Sequence[float]]) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": sample.sample_id,
            "row_index": sample.row_index,
            "question_hash": sample.question_hash,
            "n_steps": len(sample.labels),
            "scores": [float(value) for value in sample_scores],
        }
        for sample, sample_scores in zip(samples, scores, strict=False)
    ]


if __name__ == "__main__":
    main()
