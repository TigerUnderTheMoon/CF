"""Run the offline KBS-style audit-prioritization route.

The route builds deterministic HotpotQA supporting-fact traces and evaluates
fixed-budget audit ordering. It is deliberately offline and claim-bounded: the
output is KBS-style audit prioritization evidence, not deployed KBS validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fma.eval.kbs_style_audit import (  # noqa: E402
    CLAIM_BOUNDARY,
    build_kbs_audit_traces,
    evaluate_kbs_audit_traces,
)

DEFAULT_SOURCE_PATH = (
    PROJECT_ROOT / "data" / "real_task_v3" / "hotpotqa_distractor_train_declared.jsonl"
)
DEFAULT_FALLBACK_SOURCE_PATH = (
    PROJECT_ROOT / "data" / "real_task_pilot" / "hotpotqa_validation.jsonl"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "kbs_style_audit"
DEFAULT_MAX_ROWS = 2000
DEFAULT_BOOTSTRAP = 1000
DEFAULT_SEED = 42


def read_jsonl(path: Path, *, max_rows: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if max_rows is not None and max_rows > 0 and len(rows) >= max_rows:
                break
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_source(source_path: Path, fallback_source_path: Path) -> Path:
    if source_path.is_file():
        return source_path
    if fallback_source_path.is_file():
        return fallback_source_path
    raise FileNotFoundError(
        f"No HotpotQA source JSONL found at {source_path} or {fallback_source_path}"
    )


def run(
    *,
    source_path: Path = DEFAULT_SOURCE_PATH,
    fallback_source_path: Path = DEFAULT_FALLBACK_SOURCE_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    max_rows: int = DEFAULT_MAX_ROWS,
    n_bootstrap: int = DEFAULT_BOOTSTRAP,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    selected_source = select_source(Path(source_path), Path(fallback_source_path))
    rows = read_jsonl(selected_source, max_rows=max_rows)
    traces = build_kbs_audit_traces(rows)
    report = evaluate_kbs_audit_traces(traces, n_bootstrap=n_bootstrap, seed=seed)

    output_dir = Path(output_dir)
    traces_path = output_dir / "kbs_audit_traces.jsonl"
    report_path = output_dir / "kbs_audit_report.json"
    summary_path = output_dir / "kbs_audit_summary.md"

    report.update(
        {
            "input": {
                "source_path": str(selected_source),
                "source_sha256": file_sha256(selected_source),
                "rows_read": len(rows),
                "traces_built": len(traces),
            },
            "config": {
                "max_rows": max_rows,
                "n_bootstrap": n_bootstrap,
                "seed": seed,
                "dev_hash_percent": 30,
                "locked_hash_percent": 70,
                "offline_only": True,
            },
            "artifacts": {
                "traces_path": str(traces_path),
                "report_path": str(report_path),
                "summary_path": str(summary_path),
            },
            "forbidden_claims": [
                "production KBS deployment",
                "downstream PRM training gain",
                "GSM8K or HotpotQA replay validation",
                "causal identification",
            ],
        }
    )
    report["claim_boundary"] = CLAIM_BOUNDARY
    report["validated_kbs_workflow"] = False
    report["api_calls"] = 0

    write_jsonl(traces_path, traces)
    write_json(report_path, report)
    summary_path.write_text(_summary_markdown(report), encoding="utf-8")
    return report


def _summary_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# KBS-style Audit Prioritization",
        "",
        f"- Claim boundary: `{report['claim_boundary']}`",
        f"- Validated KBS workflow: `{str(report['validated_kbs_workflow']).lower()}`",
        f"- API calls: `{report['api_calls']}`",
        f"- Dev samples: `{report['dev_samples']}`",
        f"- Locked samples: `{report['locked_samples']}`",
        f"- Locked steps: `{report['locked_steps']}`",
        "",
        "## Method Metrics",
        "",
        "| Method | NDCG@25% | Top-1 hit | Mass@25% | AUPRC | Spearman |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    methods = report.get("methods", {})
    if isinstance(methods, Mapping):
        for name, metrics in sorted(methods.items()):
            if not isinstance(metrics, Mapping):
                continue
            lines.append(
                "| {name} | {ndcg:.4f} | {top1:.4f} | {mass:.4f} | {auprc:.4f} | {rho:.4f} |".format(
                    name=name,
                    ndcg=float(metrics.get("mean_ndcg_at_25", 0.0)),
                    top1=float(metrics.get("mean_top1_hit", 0.0)),
                    mass=float(metrics.get("mean_mass_at_25", 0.0)),
                    auprc=float(metrics.get("mean_auprc", 0.0)),
                    rho=float(metrics.get("mean_spearman", 0.0)),
                )
            )

    decision = report.get("support_decision", {})
    lines.extend(
        [
            "",
            "## Support Decision",
            "",
            f"- Support condition met: `{str(decision.get('support_condition_met', False)).lower()}`",
            f"- Best SC-FMA method: `{decision.get('best_scfma_method', 'n/a')}`",
            f"- Best control method: `{decision.get('best_control_method', 'n/a')}`",
            f"- Delta vs best control: `{float(decision.get('best_scfma_delta_vs_best_control', 0.0)):.4f}`",
            "",
            "This route supports only offline KBS-style audit prioritization evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-path", type=Path, default=DEFAULT_SOURCE_PATH)
    parser.add_argument("--fallback-source-path", type=Path, default=DEFAULT_FALLBACK_SOURCE_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument("--n-bootstrap", type=int, default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    report = run(
        source_path=args.source_path,
        fallback_source_path=args.fallback_source_path,
        output_dir=args.output_dir,
        max_rows=args.max_rows,
        n_bootstrap=args.n_bootstrap,
        seed=args.seed,
    )
    decision = report["support_decision"]
    print(f"KBS-style audit report written to {report['artifacts']['report_path']}")
    print(
        "Support condition met: "
        f"{decision['support_condition_met']} "
        f"(delta={decision['best_scfma_delta_vs_best_control']:.4f})"
    )
    print(f"Claim boundary: {report['claim_boundary']}")


if __name__ == "__main__":
    main()
