"""Shared helpers for reviewer V2 experiment scripts.

This module is intentionally script-local. It keeps reviewer-facing experiment
metadata consistent without adding a public ``fma.*`` API.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "reviewer_v2_experiments"
CLAIM_BOUNDARY = "real_prm800k_audit_prioritization_only"
SEED_LIST = [42, 123, 456, 789, 1024]
COMMON_LIMITATIONS = [
    "Supports PRM800K-like audit-prioritization mechanism evidence only.",
    "Does not support external generalization claims.",
    "Does not validate human audit efficiency.",
    "Does not validate downstream PRM training.",
    "Does not validate production KBS deployment.",
]


@dataclass(frozen=True)
class Timer:
    started: float

    @classmethod
    def start(cls) -> "Timer":
        return cls(time.time())

    def elapsed(self) -> float:
        return round(time.time() - self.started, 4)


def common_metadata(
    *,
    output_dir: Path,
    evidence_level: str,
    seed_list: Sequence[int] | None = None,
    source_artifacts: Sequence[str] | None = None,
    known_limitations: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "claim_boundary": CLAIM_BOUNDARY,
        "evidence_level": evidence_level,
        "zero_api_calls": True,
        "seed_list": list(seed_list or SEED_LIST),
        "output_dir": str(output_dir.resolve()),
        "source_artifacts": list(source_artifacts or []),
        "known_limitations": list(known_limitations or COMMON_LIMITATIONS),
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_markdown(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    return float((sum((value - mu) ** 2 for value in values) / (len(values) - 1)) ** 0.5)


def safe_corr(x: Sequence[float], y: Sequence[float], method: str = "spearman") -> float:
    import numpy as np
    from scipy import stats

    if len(x) < 2 or len(y) < 2 or len(set(x)) < 2 or len(set(y)) < 2:
        return 0.0
    statistic = (
        stats.kendalltau(np.asarray(x, dtype=float), np.asarray(y, dtype=float)).statistic
        if method == "kendall"
        else stats.spearmanr(np.asarray(x, dtype=float), np.asarray(y, dtype=float)).statistic
    )
    value = float(statistic)
    return value if value == value else 0.0


def git_info() -> dict[str, Any]:
    def run_git(args: Sequence[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    status = run_git(["status", "--short"])
    return {
        "git_commit": run_git(["rev-parse", "HEAD"]),
        "git_dirty": bool(status),
    }


def environment_info() -> dict[str, Any]:
    info = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        "cpu_core_count": os.cpu_count() or 0,
        "peak_memory_mb": None,
    }
    try:
        import resource  # type: ignore[import-not-found]

        usage = resource.getrusage(resource.RUSAGE_SELF)
        info["peak_memory_mb"] = round(float(usage.ru_maxrss) / 1024.0, 3)
    except Exception:
        info["peak_memory_mb"] = None
    return info


def fixture_traces(size: int, seed: int = 42) -> list[dict[str, Any]]:
    import numpy as np

    rng = np.random.default_rng(seed)
    categories = [
        "DECOMPOSITION",
        "VERIFICATION",
        "ERROR_CORRECTION",
        "PLANNING",
        "CRITIQUE",
    ]
    traces: list[dict[str, Any]] = []
    for trace_index in range(size):
        n_steps = int(rng.integers(4, 8))
        theme = ["algebra", "entity", "constraint"][trace_index % 3]
        steps: list[dict[str, Any]] = []
        for step_index in range(n_steps):
            category = categories[(trace_index + step_index) % len(categories)]
            shared = "verify common evidence" if step_index % 2 == 0 else "revise local plan"
            steps.append(
                {
                    "category": category,
                    "text": (
                        f"{theme} step {step_index} {shared}; "
                        f"{category.lower()} signal {trace_index % 5}"
                    ),
                }
            )
        traces.append(
            {
                "trace_id": f"fixture_trace_{trace_index:04d}",
                "reflection_chain": steps,
            }
        )
    return traces


def fixture_necessity_records(traces: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for trace in traces:
        trace_id = str(trace["trace_id"])
        steps = list(trace.get("reflection_chain", []))
        total = max(1, len(steps) - 1)
        for step_idx, step in enumerate(steps):
            category = str(step.get("category", "OTHER"))
            base = 0.15 + 0.7 * (step_idx / total)
            if "VERIFICATION" in category or "ERROR" in category:
                base += 0.15
            score = min(1.0, base)
            records.append(
                {
                    "trace_id": trace_id,
                    "step_idx": step_idx,
                    "attribution_score": score,
                    "necessity": score,
                    "necessity_normalized": score,
                }
            )
    return records
