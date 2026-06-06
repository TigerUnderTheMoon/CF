"""Span-level artifact coverage checks for the real-task pilot."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


SpanKey = tuple[str, int]


def expected_span_keys(
    records: Sequence[Mapping[str, Any]],
    *,
    max_spans_per_trace: int,
) -> list[dict[str, Any]]:
    """Return the expected `(sample_id, span_index)` keys for current traces."""

    keys: list[dict[str, Any]] = []
    for record in records:
        sample_id = str(record.get("sample_id") or "")
        spans = record.get("reflection_spans") or []
        span_count = min(len(spans), max_spans_per_trace)
        for span_index in range(span_count):
            keys.append(
                {
                    "sample_id": sample_id,
                    "span_index": span_index,
                    "task_type": record.get("task_type"),
                }
            )
    return keys


def audit_key_coverage(
    expected_keys: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    *,
    artifact_name: str,
    success_statuses: Iterable[str] | None = None,
    preview_limit: int = 10,
) -> dict[str, Any]:
    """Compare observed artifact rows against expected span keys."""

    expected = {_key_from_mapping(row) for row in expected_keys}
    observed = _observed_keys(rows, success_statuses=success_statuses)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    return {
        "artifact": artifact_name,
        "coverage_pass": not missing and not extra and bool(expected),
        "expected_count": len(expected),
        "observed_count": len(observed),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "missing_preview": [_key_payload(key) for key in missing[:preview_limit]],
        "extra_preview": [_key_payload(key) for key in extra[:preview_limit]],
    }


def coverage_gates(artifact_coverage: Mapping[str, Mapping[str, Any]] | None) -> dict[str, bool]:
    """Return readiness gate booleans for the required coverage artifacts."""

    coverage = artifact_coverage or {}
    return {
        "replay_coverage": bool(coverage.get("replay", {}).get("coverage_pass", True)),
        "delta_coverage": bool(coverage.get("delta", {}).get("coverage_pass", True)),
        "baseline_coverage": bool(coverage.get("baseline", {}).get("coverage_pass", True)),
        "rank_signal_coverage": bool(coverage.get("rank_signal", {}).get("coverage_pass", True)),
    }


def all_coverage_passes(artifact_coverage: Mapping[str, Mapping[str, Any]] | None) -> bool:
    """Return whether every supplied coverage artifact passes."""

    if not artifact_coverage:
        return True
    return all(bool(item.get("coverage_pass")) for item in artifact_coverage.values())


def _observed_keys(
    rows: Sequence[Mapping[str, Any]],
    *,
    success_statuses: Iterable[str] | None,
) -> set[SpanKey]:
    allowed = set(success_statuses or [])
    observed = set()
    for row in rows:
        status = row.get("status")
        if allowed and status not in allowed:
            continue
        key = _key_from_mapping(row)
        if key[0]:
            observed.add(key)
    return observed


def _key_from_mapping(row: Mapping[str, Any]) -> SpanKey:
    return str(row.get("sample_id") or ""), int(row.get("span_index", 0) or 0)


def _key_payload(key: SpanKey) -> dict[str, Any]:
    return {"sample_id": key[0], "span_index": key[1]}


__all__ = [
    "all_coverage_passes",
    "audit_key_coverage",
    "coverage_gates",
    "expected_span_keys",
]
