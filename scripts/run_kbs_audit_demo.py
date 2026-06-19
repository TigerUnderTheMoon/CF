"""KBS audit demo — thin wrapper around frozen PRM800K v3.6 audit-prioritization artifacts.

Frames the existing audit-prioritization results as a KBS (Knowledge-Based System)
auditing scenario: a reviewer must prioritize process steps for inspection under a
fixed budget.  Reuses the frozen ``audit_prioritization_report.json`` and the
``prm800k_audit_prioritization`` module — ZERO new API calls.

Outputs:
    outputs/kbs_audit_demo/audit_demo_report.json
    outputs/kbs_audit_demo/audit_demo_summary.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from fma.eval.prm800k_audit_prioritization import keep_count  # reused module helper

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FROZEN_REPORT = (
    PROJECT_ROOT
    / "outputs"
    / "real_task_v3_6_prm800k_hash"
    / "audit_prioritization_report.json"
)
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "kbs_audit_demo"

KBS_SCENARIO = (
    "A reviewer of a knowledge-intensive reasoning system with a fixed budget "
    "to inspect 25% of process steps must prioritize which steps to audit. "
    "We compare methods on this audit-prioritization task using PRM800K-like "
    "process supervision annotations."
)

KBS_METHODS = (
    "w_struct",
    "scfma_ridge",
    "raw_local_utility",
    "random",
)

_METRIC_KEYS = ("top1_hit", "mass25", "mass50", "ndcg25", "ndcg50")


def main() -> None:  # noqa: D401  (imperative-mood OK for entry point)
    """Load frozen v3.6 artifact, apply KBS framing, and write demo outputs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load frozen PRM800K v3.6 artifact (ZERO API calls)
    # ------------------------------------------------------------------
    frozen = _load_json(FROZEN_REPORT)
    n_samples = int(frozen["n_samples"])
    n_steps = int(frozen["n_steps"])

    # ------------------------------------------------------------------
    # 2. Extract per-method metrics
    # ------------------------------------------------------------------
    methods: dict[str, dict[str, float]] = {}
    for entry in frozen["methods"]:
        name = str(entry["method"])
        if name not in KBS_METHODS:
            continue
        methods[name] = {
            "top1_hit": float(entry.get("mean_top1_hit", 0.0)),
            "mass25": float(entry.get("mean_mass_at_25", 0.0)),
            "mass50": float(entry.get("mean_mass_at_50", 0.0)),
            "ndcg25": float(entry.get("mean_ndcg_at_25", 0.0)),
            "ndcg50": float(entry.get("mean_ndcg_at_50", 0.0)),
        }

    # ------------------------------------------------------------------
    # 3. Assemble KBS audit demo report
    # ------------------------------------------------------------------
    review_budget = 0.25
    budget_steps = keep_count(n_steps, review_budget)

    report: dict[str, Any] = {
        "scenario": KBS_SCENARIO,
        "methods": methods,
        "config": {
            "data_source": "PRM800K phase2 locked split (v3.6 hash-split)",
            "locked_samples": n_samples,
            "total_steps": n_steps,
            "review_budget_fraction": review_budget,
            "review_budget_steps": budget_steps,
            "seed": 42,
        },
        "evidence_level": "demonstration",
        "validated_kbs_workflow": False,
    }

    report_path = OUTPUT_DIR / "audit_demo_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # 4. Write human-readable summary
    # ------------------------------------------------------------------
    summary_path = OUTPUT_DIR / "audit_demo_summary.md"
    summary_path.write_text(_build_summary(report), encoding="utf-8")

    print(f"KBS audit demo report → {report_path}")
    print(f"KBS audit demo summary → {summary_path}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _load_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise TypeError(f"Expected JSON object in {path}")
    return payload


def _build_summary(report: Mapping[str, Any]) -> str:
    methods = report["methods"]
    config = report["config"]
    lines = [
        "# KBS Audit Demo — Summary",
        "",
        "## Scenario",
        "",
        report["scenario"],
        "",
        "## Configuration",
        "",
        f"- Data source: {config['data_source']}",
        f"- Locked samples: {config['locked_samples']}",
        f"- Total process steps: {config['total_steps']}",
        f"- Review budget: {int(config['review_budget_fraction'] * 100)}% "
        f"({config['review_budget_steps']} steps)",
        f"- Evidence level: **{report['evidence_level']}**",
        f"- Validated KBS workflow: **{report['validated_kbs_workflow']}**",
        "",
        "## Audit-Prioritization Comparison (PRM800K locked split)",
        "",
        "| Method | Top-1 Max-Label Hit | Label Mass @ 25% | NDCG @ 25% |",
        "|---|---:|---:|---:|",
    ]

    priority: list[str] = sorted(
        methods,
        key=lambda name: abs(float(methods[name].get("ndcg25", 0.0))),
        reverse=True,
    )

    def _display(name: str) -> str:
        return _DISPLAY_NAMES.get(name, name)

    for name in priority:
        m = methods[name]
        lines.append(
            f"| {_display(name)} | {m['top1_hit']:.4f} | "
            f"{m['mass25']:.4f} | {m['ndcg25']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Comparison Notes",
            "",
            _comparison_note(methods),
            "",
            "## Claim Boundary",
            "",
            "- **Evidence level**: `demonstration` — this is a packaged demo, "
            "not a validated production workflow.",
            "- **Validated KBS workflow**: `false` — no real KBS deployment "
            "validation has been performed.",
            "- **Data**: PRM800K phase2 locked hash-split (v3.6). "
            "Results are in-distribution for PRM800K-like process "
            "supervision only.",
            "- **Zero API calls**: All data originates from the frozen "
            "v3.6 artifact; no model APIs were called.",
            "- **No downstream claims**: This demo does not claim "
            "PRM training superiority, filtering gains, external "
            "generalization, or causal identification.",
            "",
        ]
    )

    return "\n".join(lines)


def _comparison_note(methods: Mapping[str, Mapping[str, float]]) -> str:
    w_struct = methods.get("w_struct", {})
    random_ = methods.get("random", {})
    raw = methods.get("raw_local_utility", {})

    ndcg_w = float(w_struct.get("ndcg25", 0.0))
    ndcg_rnd = float(random_.get("ndcg25", 0.0))
    ndcg_raw = float(raw.get("ndcg25", 0.0))

    parts: list[str] = []

    if ndcg_w > ndcg_rnd and ndcg_w > ndcg_raw:
        delta_rnd = ndcg_w - ndcg_rnd
        delta_raw = ndcg_w - ndcg_raw
        parts.append(
            f"**w_struct** achieves NDCG@25% of {ndcg_w:.4f}, outperforming "
            f"random ({ndcg_rnd:.4f}, +{delta_rnd:.4f}) and raw local utility "
            f"({ndcg_raw:.4f}, +{delta_raw:.4f}). Under the 25% review budget, "
            f"w_struct concentrates high-rated process steps most effectively "
            f"among the compared methods."
        )
    else:
        parts.append(
            f"**w_struct** (NDCG@25%: {ndcg_w:.4f}) does not clearly outperform "
            f"the baselines under the 25% review budget."
        )

    parts.append(
        f"**random** selection achieves NDCG@25% of {ndcg_rnd:.4f}, serving "
        f"as the uninformed baseline."
    )

    return " ".join(parts)


_DISPLAY_NAMES: dict[str, str] = {
    "w_struct": "w_struct",
    "scfma_ridge": "SC-FMA Ridge",
    "raw_local_utility": "raw_local_utility",
    "random": "random",
}


if __name__ == "__main__":
    main()
