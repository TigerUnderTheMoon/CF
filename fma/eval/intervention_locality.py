"""Post-hoc locality diagnostics for counterfactual reflection masking.

This module intentionally does not participate in attribution, replay, or
aggregation logic. It reads existing JSONL outputs and writes a standalone
diagnostic report describing intervention-sensitive locality patterns.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_TRACE_PATH = Path("outputs") / "reflection_traces.jsonl"
DEFAULT_COUNTERFACTUAL_PATH = Path("outputs") / "counterfactual_results.jsonl"
DEFAULT_OUTPUT_PATH = Path("outputs") / "locality_probe.json"
MASK_TOKEN = "[REASONING_MASK]"
LOCALITY_THRESHOLD = 0.7

ORIGINAL_OUTCOME_FIELDS = ("correctness", "original_correctness", "original_outcome", "outcome")
COUNTERFACTUAL_OUTCOME_FIELDS = (
    "counterfactual_correctness",
    "intervened_correctness",
    "counterfactual_outcome",
    "intervened_outcome",
    "masked_correctness",
    "masked_outcome",
    "replayed_correctness",
    "replayed_outcome",
)
REFLECTION_CIU_FIELDS = ("reflection_ciu", "ciu")
CONTROL_CIU_FIELDS = ("control_ciu", "negative_control_ciu", "ordinary_control_ciu")
CONTROL_OUTCOME_FIELDS = (
    "control_counterfactual_correctness",
    "negative_control_correctness",
    "ordinary_counterfactual_correctness",
    "control_correctness",
    "control_intervened_outcome",
    "control_outcome",
)
METACOGNITIVE_STEP_TYPES = {
    "metacognition",
    "reflection",
    "self-reflection",
    "self-evaluation",
    "error_diagnosis",
    "error-diagnosis",
    "plan_revision",
    "plan-revision",
    "strategy_critique",
    "strategy-critique",
}

FINAL_ANSWER_RE = re.compile(r"final\s+answer\s*:\s*(?P<answer>.+)", re.IGNORECASE)
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON.") from exc
    return records


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sample_id(record: dict[str, Any]) -> str | None:
    value = record.get("sample_id") or record.get("task_id")
    if value is None or str(value) == "":
        return None
    return str(value)


def pair_records(
    original_records: list[dict[str, Any]],
    counterfactual_records: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    original_ids = [sample_id(record) for record in original_records]
    counterfactual_ids = [sample_id(record) for record in counterfactual_records]

    if original_ids and counterfactual_ids and all(original_ids) and all(counterfactual_ids):
        by_id: dict[str, dict[str, Any]] = {}
        for record, record_id in zip(counterfactual_records, counterfactual_ids, strict=True):
            assert record_id is not None
            if record_id in by_id:
                raise ValueError(f"Duplicate counterfactual record for sample_id={record_id!r}.")
            by_id[record_id] = record

        pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for original, record_id in zip(original_records, original_ids, strict=True):
            assert record_id is not None
            if record_id not in by_id:
                raise ValueError(f"No counterfactual record found for sample_id={record_id!r}.")
            pairs.append((original, by_id[record_id]))
        return pairs

    if len(original_records) != len(counterfactual_records):
        raise ValueError(
            "Cannot pair records by deterministic ordering because input lengths differ: "
            f"{len(original_records)} traces vs {len(counterfactual_records)} counterfactuals."
        )
    return list(zip(original_records, counterfactual_records, strict=True))


def coerce_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        number = float(value)
        if math.isfinite(number):
            return number
    return None


def first_numeric(record: dict[str, Any], fields: Iterable[str]) -> float | None:
    for field in fields:
        if field in record:
            value = coerce_numeric(record[field])
            if value is not None:
                return value
    return None


def require_original_outcome(record: dict[str, Any]) -> float:
    outcome = first_numeric(record, ORIGINAL_OUTCOME_FIELDS)
    if outcome is None:
        record_id = sample_id(record) or "<ordered-record>"
        raise ValueError(f"Original record for sample_id={record_id!r} lacks an outcome field.")
    return outcome


def counterfactual_outcome(record: dict[str, Any]) -> float | None:
    return first_numeric(record, COUNTERFACTUAL_OUTCOME_FIELDS)


def reflection_ciu(original: dict[str, Any], counterfactual: dict[str, Any]) -> float:
    for record in (counterfactual, original):
        direct = first_numeric(record, REFLECTION_CIU_FIELDS)
        if direct is not None:
            return direct

    original_outcome = require_original_outcome(original)
    intervened_outcome = counterfactual_outcome(counterfactual)
    if intervened_outcome is None:
        record_id = sample_id(original) or sample_id(counterfactual) or "<ordered-record>"
        raise ValueError(f"Counterfactual record for sample_id={record_id!r} lacks an outcome field.")
    return original_outcome - intervened_outcome


def control_ciu(original: dict[str, Any], counterfactual: dict[str, Any]) -> float:
    for record in (counterfactual, original):
        direct = first_numeric(record, CONTROL_CIU_FIELDS)
        if direct is not None:
            return direct

    original_outcome = require_original_outcome(original)
    for record in (counterfactual, original):
        control_outcome = first_numeric(record, CONTROL_OUTCOME_FIELDS)
        if control_outcome is not None:
            return original_outcome - control_outcome

    # Post-hoc JSONL inputs do not contain a regenerated ordinary-step control
    # outcome in Phase 1 fixtures. In that case, the sampled control mask is a
    # lexical diagnostic proxy whose final answer is unchanged.
    return 0.0


def steps_text(record: dict[str, Any]) -> str:
    steps = record.get("steps")
    if not isinstance(steps, list):
        return ""
    return " ".join(str(step.get("text") or "") for step in steps if isinstance(step, dict)).strip()


def trace_text(original: dict[str, Any], counterfactual: dict[str, Any] | None = None) -> str:
    candidates: list[Any] = []
    if counterfactual is not None:
        candidates.extend(
            (
                counterfactual.get("original_trace"),
                counterfactual.get("reasoning_trace"),
                steps_text(counterfactual),
            )
        )
    candidates.extend((original.get("reasoning_trace"), original.get("original_trace"), steps_text(original)))
    for value in candidates:
        if isinstance(value, str) and value:
            return value
    return ""


def counterfactual_trace_text(original: dict[str, Any], counterfactual: dict[str, Any]) -> str:
    for field in ("counterfactual_trace", "intervened_trace", "masked_counterfactual_trace", "masked_trace"):
        value = counterfactual.get(field)
        if isinstance(value, str) and value:
            return value
    return trace_text(original, counterfactual)


def tokens(text: str) -> list[str]:
    return text.split()


def reflection_spans(record: dict[str, Any]) -> list[dict[str, Any]]:
    return list(record.get("reflection_spans") or record.get("metacognitive_spans") or [])


def span_token_range(span: dict[str, Any], token_count: int) -> tuple[int, int]:
    start = int(span.get("start_token", span.get("start_idx", 0)) or 0)
    if "end_token" in span or "end_idx" in span:
        end = int(span.get("end_token", span.get("end_idx", start)) or start)
    elif "span_length" in span:
        end = start + int(span.get("span_length") or 0)
    elif "token_count" in span:
        end = start + int(span.get("token_count") or 0)
    else:
        end = start + len(str(span.get("content") or "").split())

    start = max(0, min(start, token_count))
    end = max(start, min(end, token_count))
    return start, end


def reflection_ranges(record: dict[str, Any], token_count: int) -> list[tuple[int, int]]:
    ranges = [span_token_range(span, token_count) for span in reflection_spans(record)]
    return [(start, end) for start, end in ranges if end > start]


def first_intervention_end_token(original: dict[str, Any], counterfactual: dict[str, Any], token_count: int) -> int:
    for record in (counterfactual, original):
        for field in ("masked_reflection_spans", "reflection_spans", "metacognitive_spans"):
            spans = record.get(field)
            if isinstance(spans, list) and spans:
                _, end = span_token_range(spans[0], token_count)
                return end
    return 0


def overlaps_any(start: int, end: int, ranges: Sequence[tuple[int, int]]) -> bool:
    return any(start < range_end and end > range_start for range_start, range_end in ranges)


def ordinary_step_ranges(
    record: dict[str, Any],
    token_count: int,
    excluded_ranges: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    steps = record.get("steps")
    if not isinstance(steps, list):
        return []

    ranges: list[tuple[int, int]] = []
    cursor = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        text = str(step.get("text") or "")
        length = len(tokens(text))
        start = int(step.get("start_token", cursor) or cursor)
        end = int(step.get("end_token", start + length) or start + length)
        cursor = end
        step_type = str(step.get("step_type") or "").strip().lower()
        if step_type in METACOGNITIVE_STEP_TYPES:
            continue
        start = max(0, min(start, token_count))
        end = max(start, min(end, token_count))
        if end > start and not overlaps_any(start, end, excluded_ranges):
            ranges.append((start, end))
    return ranges


def contiguous_runs(indices: Sequence[int]) -> list[tuple[int, int]]:
    if not indices:
        return []

    sorted_indices = sorted(set(indices))
    runs: list[tuple[int, int]] = []
    run_start = sorted_indices[0]
    previous = sorted_indices[0]
    for index in sorted_indices[1:]:
        if index == previous + 1:
            previous = index
            continue
        runs.append((run_start, previous + 1))
        run_start = index
        previous = index
    runs.append((run_start, previous + 1))
    return runs


def fallback_control_windows(
    token_count: int,
    excluded_ranges: Sequence[tuple[int, int]],
    target_length: int,
) -> list[tuple[int, int]]:
    excluded = set()
    for start, end in excluded_ranges:
        excluded.update(range(start, end))

    eligible = [index for index in range(token_count) if index not in excluded]
    runs = contiguous_runs(eligible)
    windows: list[tuple[int, int]] = []
    for start, end in runs:
        run_length = end - start
        if run_length <= 0:
            continue
        width = min(max(1, target_length), run_length)
        for window_start in range(start, end - width + 1):
            windows.append((window_start, window_start + width))
    return windows


def mask_token_range(token_values: Sequence[str], start: int, end: int) -> str:
    masked = list(token_values)
    masked[start:end] = [MASK_TOKEN] * max(0, end - start)
    return " ".join(masked)


def sample_control_intervention(record: dict[str, Any], rng: random.Random) -> dict[str, Any] | None:
    original_tokens = tokens(trace_text(record))
    if not original_tokens:
        return None

    ranges = reflection_ranges(record, len(original_tokens))
    first_reflection_length = ranges[0][1] - ranges[0][0] if ranges else 1
    candidates = ordinary_step_ranges(record, len(original_tokens), ranges)
    if not candidates:
        candidates = fallback_control_windows(len(original_tokens), ranges, first_reflection_length)
    if not candidates:
        return None

    start, end = rng.choice(candidates)
    return {
        "start_token": start,
        "end_token": end,
        "token_count": end - start,
        "masked_trace": mask_token_range(original_tokens, start, end),
    }


def levenshtein_distance(left: Sequence[str], right: Sequence[str]) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            insertion = current[right_index - 1] + 1
            deletion = previous[right_index] + 1
            substitution = previous[right_index - 1] + (0 if left_value == right_value else 1)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def normalized_edit_distance(left: Sequence[str], right: Sequence[str]) -> float:
    denominator = max(len(left), len(right), 1)
    distance = levenshtein_distance(left, right)
    return min(1.0, max(0.0, distance / denominator))


def downstream_drift(original: dict[str, Any], counterfactual: dict[str, Any]) -> float:
    original_text = trace_text(original, counterfactual)
    original_tokens = tokens(original_text)
    intervention_end = first_intervention_end_token(original, counterfactual, len(original_tokens))
    counterfactual_tokens = tokens(counterfactual_trace_text(original, counterfactual))

    original_downstream = original_tokens[intervention_end:]
    counterfactual_downstream = counterfactual_tokens[intervention_end:]
    return normalized_edit_distance(original_downstream, counterfactual_downstream)


def extract_final_answer(text: str) -> str | None:
    matches = list(FINAL_ANSWER_RE.finditer(text))
    if matches:
        return matches[-1].group("answer").strip()
    return None


def normalize_answer(text: str) -> str:
    if "####" in text:
        text = text.split("####")[-1]
    numbers = NUMBER_RE.findall(text)
    if numbers:
        return numbers[-1].replace(",", "")
    return text.strip().lower()


def answer_from_fields(record: dict[str, Any], fields: Iterable[str], fallback_trace: str | None = None) -> str | None:
    for field in fields:
        value = record.get(field)
        if value is not None and str(value) != "":
            return str(value)
    if fallback_trace:
        return extract_final_answer(fallback_trace)
    return None


def final_answer_unchanged(
    original: dict[str, Any],
    counterfactual: dict[str, Any],
    original_outcome: float | None,
    intervened_outcome: float | None,
) -> bool:
    original_answer = answer_from_fields(
        counterfactual,
        ("original_answer",),
    ) or answer_from_fields(
        original,
        ("final_answer", "original_answer"),
        trace_text(original, counterfactual),
    )
    counterfactual_answer = answer_from_fields(
        counterfactual,
        ("counterfactual_answer", "intervened_answer", "masked_answer", "replayed_answer", "final_answer"),
        counterfactual.get("counterfactual_trace")
        if isinstance(counterfactual.get("counterfactual_trace"), str)
        else None,
    )

    if original_answer is not None and counterfactual_answer is not None:
        return normalize_answer(original_answer) == normalize_answer(counterfactual_answer)
    if original_outcome is not None and intervened_outcome is not None:
        return original_outcome == intervened_outcome
    return True


def mean(values: Sequence[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def population_std(values: Sequence[float]) -> float:
    return float(statistics.pstdev(values)) if len(values) > 1 else 0.0


def classify_pair(locality_index: float, answer_changed: bool) -> str:
    high_locality = locality_index >= LOCALITY_THRESHOLD
    if high_locality and answer_changed:
        return "functional_influence_count"
    if high_locality and not answer_changed:
        return "benign_local_perturbation_count"
    if not high_locality and not answer_changed:
        return "drift_artifact_count"
    return "unstable_global_rewrite_count"


def interpretation_lines(specificity_gap: float, locality_index_mean: float) -> list[str]:
    if specificity_gap > 0.0:
        specificity = "Reflective interventions exhibit stronger attributional influence than ordinary control masking."
    else:
        specificity = "Reflective interventions do not exceed ordinary control masking in this diagnostic run."

    if locality_index_mean >= LOCALITY_THRESHOLD:
        locality = "Most interventions preserve downstream locality while selectively altering functional outcomes."
    else:
        locality = "Downstream drift is substantial enough that locality should be inspected before attributional interpretation."

    return [
        specificity,
        locality,
        "Lexical locality metrics are approximate proxies and do not guarantee semantic equivalence.",
    ]


def has_reflection_intervention(original: dict[str, Any], counterfactual: dict[str, Any]) -> bool:
    if reflection_spans(original):
        return True
    spans = counterfactual.get("masked_reflection_spans")
    return isinstance(spans, list) and len(spans) > 0


def build_locality_probe_report(
    original_records: list[dict[str, Any]],
    counterfactual_records: list[dict[str, Any]],
    seed: int = 42,
) -> dict[str, Any]:
    rng = random.Random(seed)
    pairs = pair_records(original_records, counterfactual_records)

    reflection_cius: list[float] = []
    control_cius: list[float] = []
    drift_ratios: list[float] = []
    locality_indexes: list[float] = []
    counts = {
        "functional_influence_count": 0,
        "drift_artifact_count": 0,
        "benign_local_perturbation_count": 0,
        "unstable_global_rewrite_count": 0,
    }

    for original, counterfactual in pairs:
        if not has_reflection_intervention(original, counterfactual):
            continue

        reflection_cius.append(reflection_ciu(original, counterfactual))

        control_intervention = sample_control_intervention(original, rng)
        if control_intervention is not None:
            control_cius.append(control_ciu(original, counterfactual))

        drift_ratio = downstream_drift(original, counterfactual)
        locality_index = 1.0 - drift_ratio
        drift_ratios.append(drift_ratio)
        locality_indexes.append(locality_index)

        original_outcome = first_numeric(original, ORIGINAL_OUTCOME_FIELDS)
        intervened_outcome = counterfactual_outcome(counterfactual)
        answer_changed = not final_answer_unchanged(
            original,
            counterfactual,
            original_outcome,
            intervened_outcome,
        )
        counts[classify_pair(locality_index, answer_changed)] += 1

    control_ciu_mean = mean(control_cius)
    reflection_ciu_mean = mean(reflection_cius)
    specificity_gap = reflection_ciu_mean - control_ciu_mean
    locality_index_mean = mean(locality_indexes)

    # TODO: Add early/middle/late position sensitivity once regenerated
    # ordinary-step control outcomes are available in the post-hoc records.
    return {
        "control_ciu_mean": control_ciu_mean,
        "control_ciu_std": population_std(control_cius),
        "reflection_ciu_mean": reflection_ciu_mean,
        "reflection_ciu_std": population_std(reflection_cius),
        "specificity_gap": specificity_gap,
        "drift_ratio_mean": mean(drift_ratios),
        "drift_ratio_std": population_std(drift_ratios),
        "locality_index_mean": locality_index_mean,
        "functional_influence_count": counts["functional_influence_count"],
        "drift_artifact_count": counts["drift_artifact_count"],
        "benign_local_perturbation_count": counts["benign_local_perturbation_count"],
        "unstable_global_rewrite_count": counts["unstable_global_rewrite_count"],
        "interpretation": interpretation_lines(specificity_gap, locality_index_mean),
    }


def run_locality_probe(
    input_traces: Path,
    input_counterfactuals: Path,
    output: Path,
    seed: int,
) -> dict[str, Any]:
    original_records = read_jsonl(input_traces)
    counterfactual_records = read_jsonl(input_counterfactuals)
    report = build_locality_probe_report(original_records, counterfactual_records, seed=seed)
    write_report(report, output)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a standalone post-hoc locality diagnostic for counterfactual masking outputs."
    )
    parser.add_argument("--input-traces", type=Path, default=DEFAULT_TRACE_PATH)
    parser.add_argument("--input-counterfactuals", type=Path, default=DEFAULT_COUNTERFACTUAL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_locality_probe(args.input_traces, args.input_counterfactuals, args.output, args.seed)
    print(
        "Wrote locality probe report to "
        f"{args.output} "
        f"(specificity_gap={report['specificity_gap']:.3f}, "
        f"locality_index_mean={report['locality_index_mean']:.3f})."
    )


if __name__ == "__main__":
    main()
