"""Offline v3.5 validation on PRM800K real human step labels.

This route validates the step-ranking claim only. It does not upgrade the
failed GSM8K/HotpotQA replay validation claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "real_task_v3_5_prm800k_validation.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "real_task_v3_5_prm800k"
SOURCE_KIND = "real_prm800k_phase2"
USER_AGENT = "fma-real-task-v3-5-validation"

FORBIDDEN_FEATURE_FIELD_NAMES = {
    "label",
    "labels",
    "rating",
    "ratings",
    "ground_truth",
    "ground_truth_answer",
    "ground_truth_solution",
    "ground_truth_importance",
    "target",
    "targets",
    "correct",
    "correctness",
}


@dataclass(frozen=True)
class RankingSample:
    sample_id: str
    source_kind: str
    split_name: str
    row_index: int
    question_hash: str
    step_texts: tuple[str, ...]
    labels: tuple[float, ...]
    raw_local_utility: tuple[float, ...]
    feature_rows: tuple[dict[str, float], ...]


def feature_names() -> list[str]:
    return [
        "raw_local_utility",
        "relative_position",
        "relative_position_sq",
        "relative_position_cu",
        "log_token_count",
        "numeric_density",
        "equation_density",
        "answer_cue",
        "conclusion_cue_count",
        "error_uncertainty_cue_count",
        "reasoning_cue_count",
        "is_first_step",
        "is_last_step",
        "trace_step_count",
        "source_step_index_ratio",
    ]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--stage",
        choices=[
            "fixture_smoke",
            "preflight",
            "dev_calibration",
            "locked_validation",
            "decision",
            "all",
        ],
        default="all",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.stage == "fixture_smoke":
        output_dir = args.output_dir or DEFAULT_OUTPUT_ROOT
        report = run_fixture_smoke(output_dir)
        print(json.dumps({"status": report["status"], "output_dir": str(output_dir)}, sort_keys=True))
        return

    config = load_config(args.config)
    output_dir = args.output_dir or PROJECT_ROOT / config["outputs"]["root"]
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.stage in {"preflight", "all"}:
        run_preflight(config, output_dir)
    if args.stage in {"dev_calibration", "all"}:
        run_dev_calibration(config, output_dir)
    if args.stage in {"locked_validation", "all"}:
        run_locked_validation(config, output_dir)
    if args.stage in {"decision", "all"}:
        decision = run_decision(config, output_dir)
        print(
            json.dumps(
                {
                    "status": decision["status"],
                    "next_allowed_step": decision["next_allowed_step"],
                    "decision_report": str(output_dir / config["outputs"]["decision_report"]),
                },
                sort_keys=True,
            )
        )


def load_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Config is not a mapping: {path}")
    return value


def run_fixture_smoke(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "question": {"problem": "Compute 2+2.", "ground_truth_answer": "4"},
        "label": {
            "steps": [
                {
                    "completions": [{"text": "Let x = 2 + 2.", "rating": 1, "flagged": False}],
                    "chosen_completion": 0,
                },
                {
                    "completions": [{"text": "Then x = 5.", "rating": -1, "flagged": False}],
                    "chosen_completion": 0,
                },
                {
                    "completions": [{"text": "Therefore the answer is 4.", "rating": 1, "flagged": False}],
                    "chosen_completion": 0,
                },
            ]
        },
    }
    samples = build_samples([row], split_name="fixture")
    report = {
        "status": "pass" if len(samples) == 1 else "fail",
        "source_kind": SOURCE_KIND,
        "n_samples": len(samples),
        "n_steps": sum(len(sample.labels) for sample in samples),
        "feature_names": feature_names(),
        "leakage_audit": leakage_audit(),
        "claim_boundary": "fixture_smoke_only_not_validation",
    }
    write_json(output_dir / "fixture_smoke_report.json", report)
    return report


def run_preflight(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    source = config["data"]["source"]
    started = time.time()
    rows = stream_prm800k_rows(source["url"], start_row=0, row_count=3)
    report = {
        "status": "pass" if len(rows) == 3 else "fail",
        "source": source,
        "sample_rows_read": len(rows),
        "api_calls": 0,
        "estimated_api_cost_usd": 0.0,
        "elapsed_seconds": round(time.time() - started, 3),
        "cost_policy": config["cost_policy"],
    }
    write_json(output_dir / "preflight_report.json", report)
    return report


def run_dev_calibration(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    rows = load_configured_rows(config, "dev")
    samples = build_samples(rows, split_name="dev", row_start=int(config["data"]["dev"]["start_row"]))
    gates = config["validation_gates"]["dev"]
    model = fit_w_struct_model(samples, ridge_lambda=float(config["model"]["ridge_lambda"]))
    stability = compute_stability(samples, ridge_lambda=float(config["model"]["ridge_lambda"]))
    leak = leakage_audit()
    row_hash = selected_rows_hash(rows)

    report = {
        "status": "pass",
        "route_id": config["route"]["id"],
        "source_kind": SOURCE_KIND,
        "n_source_rows": len(rows),
        "n_samples": len(samples),
        "n_steps": count_steps(samples),
        "selected_rows_sha256": row_hash,
        "leakage_audit": leak,
        "stability": stability,
        "gates": {
            "dev_min_samples": {
                "threshold": int(gates["min_samples"]),
                "observed": len(samples),
                "pass": len(samples) >= int(gates["min_samples"]),
            },
            "dev_min_steps": {
                "threshold": int(gates["min_steps"]),
                "observed": count_steps(samples),
                "pass": count_steps(samples) >= int(gates["min_steps"]),
            },
            "leakage_audit": {"pass": leak["pass"]},
            "stability": {"pass": stability["pass"]},
        },
        "claim_boundary": "dev_calibration_only",
    }
    report["status"] = "pass" if all(gate["pass"] for gate in report["gates"].values()) else "fail"

    write_json(output_dir / config["outputs"]["dev_model"], model)
    write_json(output_dir / config["outputs"]["dev_report"], report)
    write_jsonl(output_dir / "dev_sample_manifest.jsonl", sample_manifest_rows(samples))
    return report


def run_locked_validation(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    model_path = output_dir / config["outputs"]["dev_model"]
    if not model_path.exists():
        raise FileNotFoundError(f"Missing frozen dev model: {model_path}")
    model = json.loads(model_path.read_text(encoding="utf-8"))

    rows = load_configured_rows(config, "locked")
    samples = build_samples(rows, split_name="locked", row_start=int(config["data"]["locked"]["start_row"]))
    metrics = evaluate_locked_samples(samples, model, bootstrap_samples=int(config["validation_gates"]["locked"]["bootstrap_samples"]))
    gates_cfg = config["validation_gates"]["locked"]
    gates = locked_gates(metrics, gates_cfg)
    report = {
        "status": "pass" if all(gate["pass"] for gate in gates.values()) else "fail",
        "route_id": config["route"]["id"],
        "source_kind": SOURCE_KIND,
        "n_source_rows": len(rows),
        "n_samples": len(samples),
        "n_steps": count_steps(samples),
        "selected_rows_sha256": selected_rows_hash(rows),
        "model_path": str(model_path),
        "metrics": metrics,
        "gates": gates,
        "claim_boundary": "locked_real_prm800k_step_label_validation",
        "api_calls": 0,
        "estimated_api_cost_usd": 0.0,
    }
    write_json(output_dir / config["outputs"]["locked_report"], report)
    write_jsonl(output_dir / "locked_sample_manifest.jsonl", sample_manifest_rows(samples))
    return report


def run_decision(config: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    dev_report = read_json(output_dir / config["outputs"]["dev_report"])
    locked_report = read_json(output_dir / config["outputs"]["locked_report"])
    decision = build_decision_report(dev_report=dev_report, locked_report=locked_report)
    decision["route_id"] = config["route"]["id"]
    decision["config"] = {
        "data": config["data"],
        "validation_gates": config["validation_gates"],
        "claim_policy": config["claim_policy"],
    }
    write_json(output_dir / config["outputs"]["decision_report"], decision)
    return decision


def load_configured_rows(config: Mapping[str, Any], split_key: str) -> list[dict[str, Any]]:
    source = config["data"]["source"]
    split = config["data"][split_key]
    return stream_prm800k_rows(
        source["url"],
        start_row=int(split["start_row"]),
        row_count=int(split["row_count"]),
    )


def stream_prm800k_rows(url: str, *, start_row: int, row_count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        for row_index, raw_line in enumerate(response):
            if row_index < start_row:
                continue
            if len(rows) >= row_count:
                break
            stripped = raw_line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def build_samples(
    rows: Iterable[Mapping[str, Any]],
    *,
    split_name: str,
    row_start: int = 0,
) -> list[RankingSample]:
    samples: list[RankingSample] = []
    for local_index, row in enumerate(rows):
        row_index = row_start + local_index
        steps = select_labeled_steps(row)
        if len(steps) < 3:
            continue
        labels = tuple(step["label"] for step in steps)
        if len(set(labels)) < 2:
            continue
        texts = tuple(step["text"] for step in steps)
        feature_rows, raw_scores = build_feature_rows(steps)
        question = extract_question(row)
        qhash = sha256_text(question)
        samples.append(
            RankingSample(
                sample_id=f"prm800k_{split_name}_{row_index:06d}_{qhash[:10]}",
                source_kind=SOURCE_KIND,
                split_name=split_name,
                row_index=row_index,
                question_hash=qhash,
                step_texts=texts,
                labels=labels,
                raw_local_utility=tuple(raw_scores),
                feature_rows=tuple(feature_rows),
            )
        )
    return samples


def select_labeled_steps(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    label = row.get("label")
    if not isinstance(label, Mapping):
        return []
    raw_steps = label.get("steps")
    if not isinstance(raw_steps, list):
        return []

    selected: list[dict[str, Any]] = []
    for source_step_index, step in enumerate(raw_steps):
        if not isinstance(step, Mapping):
            continue
        completions = step.get("completions")
        if not isinstance(completions, list):
            continue
        picked = pick_completion(step, completions)
        if picked is None:
            continue
        text = str(picked.get("text") or "").strip()
        if not text:
            continue
        try:
            rating = float(picked["rating"])
        except (KeyError, TypeError, ValueError):
            continue
        label_value = max(0.0, min(1.0, (rating + 1.0) / 2.0))
        selected.append(
            {
                "source_step_index": float(source_step_index),
                "text": text,
                "label": label_value,
            }
        )
    return selected


def pick_completion(
    step: Mapping[str, Any],
    completions: Sequence[Any],
) -> Mapping[str, Any] | None:
    chosen = step.get("chosen_completion")
    if isinstance(chosen, int) and 0 <= chosen < len(completions):
        candidate = completions[chosen]
        if is_rated_completion(candidate):
            return candidate
    for candidate in completions:
        if is_rated_completion(candidate):
            return candidate
    return None


def is_rated_completion(candidate: Any) -> bool:
    return (
        isinstance(candidate, Mapping)
        and candidate.get("rating") is not None
        and candidate.get("flagged") is not True
    )


def build_feature_rows(steps: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, float]], list[float]]:
    names = feature_names()
    rows: list[dict[str, float]] = []
    raw_scores: list[float] = []
    n_steps = len(steps)
    for step_position, step in enumerate(steps):
        text = str(step["text"])
        text_lower = text.lower()
        tokens = re.findall(r"[A-Za-z0-9]+|[^\s]", text)
        token_count = max(1, len(tokens))
        numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
        relative_position = step_position / max(1, n_steps - 1)
        numeric_density = len(numbers) / token_count
        equation_density = sum(text_lower.count(char) for char in ["=", "+", "-", "*", "/", "^"]) / token_count
        answer_cue = 1.0 if ("boxed" in text_lower or "answer" in text_lower) else 0.0
        conclusion_cues = count_cues(
            text_lower,
            ("therefore", "thus", "hence", "so ", "we get", "we have", "answer", "boxed", "final"),
        )
        error_cues = count_cues(
            text_lower,
            ("oops", "mistake", "wrong", "incorrect", "cannot", "not enough", "maybe", "assume", "guess", "approximately"),
        )
        reasoning_cues = count_cues(text_lower, ("because", "since", "then", "if", "let", "must"))
        raw = (
            0.25 * math.log1p(token_count)
            + 0.60 * numeric_density
            + 0.40 * equation_density
            + 0.25 * min(conclusion_cues, 2)
            + 0.35 * answer_cue
            - 0.35 * error_cues
            + 0.15 * reasoning_cues
            - 0.08 * relative_position
        )
        source_index_ratio = float(step["source_step_index"]) / max(1, n_steps - 1)
        row = {
            "raw_local_utility": raw,
            "relative_position": relative_position,
            "relative_position_sq": relative_position * relative_position,
            "relative_position_cu": relative_position * relative_position * relative_position,
            "log_token_count": math.log1p(token_count),
            "numeric_density": numeric_density,
            "equation_density": equation_density,
            "answer_cue": answer_cue,
            "conclusion_cue_count": float(min(conclusion_cues, 2)),
            "error_uncertainty_cue_count": float(error_cues),
            "reasoning_cue_count": float(reasoning_cues),
            "is_first_step": 1.0 if step_position == 0 else 0.0,
            "is_last_step": 1.0 if step_position == n_steps - 1 else 0.0,
            "trace_step_count": float(n_steps),
            "source_step_index_ratio": source_index_ratio,
        }
        if list(row) != names:
            raise AssertionError("feature row order drifted")
        rows.append(row)
        raw_scores.append(raw)
    return rows, raw_scores


def count_cues(text: str, cues: Sequence[str]) -> int:
    return sum(1 for cue in cues if cue in text)


def fit_w_struct_model(samples: Sequence[RankingSample], *, ridge_lambda: float) -> dict[str, Any]:
    X = samples_to_feature_matrix(samples)
    y = samples_to_label_vector(samples)
    if X.size == 0 or y.size == 0:
        raise ValueError("No training data available for w_struct")
    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds = np.where(stds < 1e-8, 1.0, stds)
    Xs = (X - means) / stds
    design = np.column_stack([np.ones(Xs.shape[0]), Xs])
    penalty = ridge_lambda * np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return {
        "model_name": "w_struct_ridge_v1",
        "frozen": True,
        "ridge_lambda": ridge_lambda,
        "feature_names": feature_names(),
        "intercept": float(coefficients[0]),
        "coefficients": [float(v) for v in coefficients[1:]],
        "feature_means": [float(v) for v in means],
        "feature_stds": [float(v) for v in stds],
        "training_samples": len(samples),
        "training_steps": count_steps(samples),
        "leakage_audit": leakage_audit(),
    }


def compute_stability(samples: Sequence[RankingSample], *, ridge_lambda: float) -> dict[str, Any]:
    fold_diffs: list[float] = []
    for fold in range(5):
        train = [sample for idx, sample in enumerate(samples) if idx % 5 != fold]
        test = [sample for idx, sample in enumerate(samples) if idx % 5 == fold]
        if not train or not test:
            fold_diffs.append(0.0)
            continue
        model = fit_w_struct_model(train, ridge_lambda=ridge_lambda)
        metrics = method_metrics(test, model)
        fold_diffs.append(
            metrics["mean_spearman"]["w_struct"] - metrics["mean_spearman"]["raw_local_utility"]
        )
    positive = sum(1 for value in fold_diffs if value > 0.0)
    return {
        "pass": positive == 5,
        "fold_count": 5,
        "positive_folds": positive,
        "fold_diffs": [float(v) for v in fold_diffs],
    }


def evaluate_locked_samples(
    samples: Sequence[RankingSample],
    model: Mapping[str, Any],
    *,
    bootstrap_samples: int,
) -> dict[str, Any]:
    metrics = method_metrics(samples, model)
    raw = np.asarray(metrics["per_sample_spearman"]["raw_local_utility"], dtype=float)
    w_struct = np.asarray(metrics["per_sample_spearman"]["w_struct"], dtype=float)
    diff = w_struct - raw
    best_heuristic = np.maximum.reduce(
        [
            np.asarray(metrics["per_sample_spearman"]["relative_position"], dtype=float),
            np.asarray(metrics["per_sample_spearman"]["span_length"], dtype=float),
            np.asarray(metrics["per_sample_spearman"]["random"], dtype=float),
        ]
    )
    heuristic_diff = w_struct - best_heuristic
    primary_ci = bootstrap_ci(diff, n_bootstrap=bootstrap_samples)
    heuristic_ci = bootstrap_ci(heuristic_diff, n_bootstrap=bootstrap_samples)
    primary_p = one_sided_wilcoxon_pvalue(diff)
    heuristic_p = one_sided_wilcoxon_pvalue(heuristic_diff)
    holm = holm_correction(
        [
            {"name": "w_struct_vs_raw_local_utility", "p_value": primary_p},
            {"name": "w_struct_vs_best_heuristic", "p_value": heuristic_p},
        ],
        alpha=0.05,
    )
    return {
        "n_samples": len(samples),
        "n_steps": count_steps(samples),
        "mean_spearman": metrics["mean_spearman"],
        "mean_kendall": metrics["mean_kendall"],
        "w_struct_minus_raw_local_utility": {
            "mean": float(np.mean(diff)),
            "bootstrap_ci": primary_ci,
            "wilcoxon_one_sided_p": primary_p,
        },
        "w_struct_minus_best_heuristic": {
            "mean": float(np.mean(heuristic_diff)),
            "bootstrap_ci": heuristic_ci,
            "wilcoxon_one_sided_p": heuristic_p,
        },
        "holm_correction": holm,
    }


def method_metrics(samples: Sequence[RankingSample], model: Mapping[str, Any]) -> dict[str, Any]:
    methods = ["w_struct", "raw_local_utility", "relative_position", "span_length", "random"]
    spearman: dict[str, list[float]] = {method: [] for method in methods}
    kendall: dict[str, list[float]] = {method: [] for method in methods}

    for sample in samples:
        labels = np.asarray(sample.labels, dtype=float)
        scores = {
            "w_struct": predict_w_struct(sample, model),
            "raw_local_utility": np.asarray(sample.raw_local_utility, dtype=float),
            "relative_position": np.arange(len(labels), dtype=float),
            "span_length": np.asarray([len(text.split()) for text in sample.step_texts], dtype=float),
            "random": random_scores(sample.sample_id, len(labels)),
        }
        for method, values in scores.items():
            spearman[method].append(safe_spearman(values, labels))
            kendall[method].append(safe_kendall(values, labels))

    return {
        "per_sample_spearman": spearman,
        "mean_spearman": {method: float(np.mean(values)) for method, values in spearman.items()},
        "mean_kendall": {method: float(np.mean(values)) for method, values in kendall.items()},
    }


def locked_gates(metrics: Mapping[str, Any], gates_cfg: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    n_samples = int(metrics["n_samples"])
    n_steps = int(metrics["n_steps"])
    mean_spearman = metrics["mean_spearman"]
    raw_ci_lower = float(metrics["w_struct_minus_raw_local_utility"]["bootstrap_ci"]["ci_lower"])
    heuristic_ci_lower = float(metrics["w_struct_minus_best_heuristic"]["bootstrap_ci"]["ci_lower"])
    holm_pass = bool(metrics["holm_correction"]["pass"])
    best_heuristic = max(
        mean_spearman["relative_position"],
        mean_spearman["span_length"],
        mean_spearman["random"],
    )
    return {
        "locked_min_samples": {
            "threshold": int(gates_cfg["min_samples"]),
            "observed": n_samples,
            "pass": n_samples >= int(gates_cfg["min_samples"]),
        },
        "locked_min_steps": {
            "threshold": int(gates_cfg["min_steps"]),
            "observed": n_steps,
            "pass": n_steps >= int(gates_cfg["min_steps"]),
        },
        "w_struct_beats_raw_ci": {
            "threshold": float(gates_cfg["ci_lower_must_exceed"]),
            "observed": raw_ci_lower,
            "pass": raw_ci_lower > float(gates_cfg["ci_lower_must_exceed"]),
        },
        "w_struct_beats_heuristics": {
            "best_heuristic_mean_spearman": float(best_heuristic),
            "w_struct_mean_spearman": float(mean_spearman["w_struct"]),
            "ci_lower": heuristic_ci_lower,
            "pass": mean_spearman["w_struct"] > best_heuristic and heuristic_ci_lower > 0.0,
        },
        "holm_primary_pass": {
            "alpha": float(gates_cfg["holm_alpha"]),
            "pass": holm_pass,
        },
    }


def build_decision_report(
    *,
    dev_report: Mapping[str, Any],
    locked_report: Mapping[str, Any],
) -> dict[str, Any]:
    dev_pass = dev_report.get("status") == "pass"
    locked_pass = locked_report.get("status") == "pass"
    status = "pass" if dev_pass and locked_pass else "fail"
    return {
        "status": status,
        "dev_status": dev_report.get("status"),
        "locked_status": locked_report.get("status"),
        "claim_permissions": {
            "M_STEP_RANKING_REAL_PRM800K": status == "pass",
            "M_STEP_RANKING": status == "pass",
            "F_REAL_TASK_SC_FMA": False,
            "F_PRM_TRAINING": False,
            "deterministic_replay_claim": False,
            "causal_identification_claim": False,
        },
        "next_allowed_step": (
            "UPDATE_STEP_RANKING_CLAIM_WITH_V3_5_ARTIFACT"
            if status == "pass"
            else "KEEP_REAL_STEP_RANKING_CLAIM_UNCHANGED_AND_WRITE_FAILURE_AUDIT"
        ),
        "claim_boundary": "real_prm800k_step_label_ranking_only",
    }


def samples_to_feature_matrix(samples: Sequence[RankingSample]) -> np.ndarray:
    rows: list[list[float]] = []
    names = feature_names()
    for sample in samples:
        for row in sample.feature_rows:
            rows.append([float(row[name]) for name in names])
    return np.asarray(rows, dtype=float)


def samples_to_label_vector(samples: Sequence[RankingSample]) -> np.ndarray:
    return np.asarray([label for sample in samples for label in sample.labels], dtype=float)


def predict_w_struct(sample: RankingSample, model: Mapping[str, Any]) -> np.ndarray:
    names = list(model["feature_names"])
    matrix = np.asarray(
        [[float(row[name]) for name in names] for row in sample.feature_rows],
        dtype=float,
    )
    means = np.asarray(model["feature_means"], dtype=float)
    stds = np.asarray(model["feature_stds"], dtype=float)
    coeffs = np.asarray(model["coefficients"], dtype=float)
    return float(model["intercept"]) + ((matrix - means) / stds) @ coeffs


def bootstrap_ci(
    values: np.ndarray,
    *,
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> dict[str, float]:
    if values.size == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}
    rng = np.random.default_rng(seed)
    means = np.empty(n_bootstrap, dtype=float)
    n = len(values)
    for idx in range(n_bootstrap):
        means[idx] = float(np.mean(values[rng.integers(0, n, n)]))
    return {
        "mean": float(np.mean(values)),
        "ci_lower": float(np.percentile(means, 2.5)),
        "ci_upper": float(np.percentile(means, 97.5)),
    }


def one_sided_wilcoxon_pvalue(values: np.ndarray) -> float:
    nonzero = values[values != 0]
    if len(nonzero) < 2:
        return 1.0
    try:
        result = stats.wilcoxon(values, alternative="greater", zero_method="wilcox")
    except ValueError:
        return 1.0
    pvalue = float(result.pvalue)
    return pvalue if not math.isnan(pvalue) else 1.0


def holm_correction(tests: list[dict[str, float]], *, alpha: float) -> dict[str, Any]:
    ordered = sorted(tests, key=lambda item: item["p_value"])
    adjusted: list[dict[str, Any]] = []
    all_pass = True
    m = len(ordered)
    for rank, item in enumerate(ordered):
        threshold = alpha / (m - rank)
        passed = item["p_value"] <= threshold
        adjusted.append({**item, "threshold": threshold, "pass": passed})
        if not passed:
            all_pass = False
    return {"alpha": alpha, "pass": all_pass, "tests": adjusted}


def safe_spearman(predicted: Sequence[float] | np.ndarray, labels: Sequence[float] | np.ndarray) -> float:
    value = stats.spearmanr(predicted, labels).statistic
    return 0.0 if math.isnan(float(value)) else float(value)


def safe_kendall(predicted: Sequence[float] | np.ndarray, labels: Sequence[float] | np.ndarray) -> float:
    value = stats.kendalltau(predicted, labels).statistic
    return 0.0 if math.isnan(float(value)) else float(value)


def random_scores(sample_id: str, n: int) -> np.ndarray:
    digest = hashlib.sha256(sample_id.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big") % (2**32)
    rng = np.random.default_rng(seed)
    return rng.random(n)


def leakage_audit() -> dict[str, Any]:
    names = feature_names()
    forbidden = sorted(set(names) & FORBIDDEN_FEATURE_FIELD_NAMES)
    return {
        "pass": not forbidden,
        "feature_names": names,
        "forbidden_feature_names_present": forbidden,
        "labels_used_only_as_targets": True,
        "raw_completion_ratings_written_to_feature_rows": False,
    }


def sample_manifest_rows(samples: Sequence[RankingSample]) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": sample.sample_id,
            "source_kind": sample.source_kind,
            "split_name": sample.split_name,
            "row_index": sample.row_index,
            "question_hash": sample.question_hash,
            "n_steps": len(sample.labels),
            "label_variance_nonzero": len(set(sample.labels)) > 1,
        }
        for sample in samples
    ]


def selected_rows_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def extract_question(row: Mapping[str, Any]) -> str:
    question = row.get("question")
    if isinstance(question, Mapping):
        return str(question.get("problem") or question.get("question") or "")
    return str(question or "")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def count_steps(samples: Sequence[RankingSample]) -> int:
    return sum(len(sample.labels) for sample in samples)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object in {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
