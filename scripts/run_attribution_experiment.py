"""Thin Phase 1 runner for the core attribution pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.ciu.estimator import estimate_ciu_file
from fma.eval.attribution_metrics import write_phase1_eval_report
from fma.fma.aggregator import aggregate_fma_file


STAGES = ("all", "generate", "intervene", "ciu", "fma", "eval")

# PHASE 2 TODO:
# - fma/matching/matcher.py: cross-trajectory matching by trajectory_length, token_budget, etc.
# - fma/dr/estimator.py: doubly robust correction for confounding control
# - fma/eval/supervision_metrics.py: step-level accuracy, calibration error
# - fma/supervision/weighted_prm.py: attribution-aware PRM training


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the lightweight Phase 1 attribution experiment.")
    parser.add_argument("--stage", choices=STAGES, default="all")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-name-or-path", default=None)
    parser.add_argument("--split", default="train")
    parser.add_argument("--max-samples", type=int, default=10)
    parser.add_argument("--max-input-tokens", type=int, default=2048)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--device-map", default=None)
    parser.add_argument("--torch-dtype", default="auto", choices=["auto", "float16", "bfloat16", "float32"])
    parser.add_argument("--prompt-file", type=Path, default=PROJECT_ROOT / "prompts" / "reflection_generation.txt")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--reflection-output", type=Path, default=Path("outputs") / "reflection_traces.jsonl")
    parser.add_argument("--counterfactual-output", type=Path, default=Path("outputs") / "counterfactual_results.jsonl")
    parser.add_argument("--ciu-output", type=Path, default=Path("outputs") / "ciu_results.jsonl")
    parser.add_argument("--fma-output", type=Path, default=Path("outputs") / "fma_scores.jsonl")
    parser.add_argument("--report-output", type=Path, default=Path("outputs") / "phase1_eval_report.json")
    return parser.parse_args()


def should_run(selected_stage: str, stage: str) -> bool:
    return selected_stage == "all" or selected_stage == stage


def run_command(command: list[str]) -> None:
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def maybe_add(command: list[str], flag: str, value: str | None) -> None:
    if value is not None:
        command.extend([flag, value])


def generate_command(args: argparse.Namespace) -> list[str]:
    if not args.model_name_or_path:
        raise ValueError("--model-name-or-path is required for --stage generate and --stage all.")

    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "generate_reflection_traces.py"),
        "--model-name-or-path",
        args.model_name_or_path,
        "--split",
        args.split,
        "--max-samples",
        str(args.max_samples),
        "--max-input-tokens",
        str(args.max_input_tokens),
        "--max-new-tokens",
        str(args.max_new_tokens),
        "--temperature",
        str(args.temperature),
        "--top-p",
        str(args.top_p),
        "--seed",
        str(args.seed),
        "--torch-dtype",
        args.torch_dtype,
        "--prompt-file",
        str(args.prompt_file),
        "--output",
        str(args.reflection_output),
    ]
    maybe_add(command, "--device-map", args.device_map)
    if args.trust_remote_code:
        command.append("--trust-remote-code")
    return command


def intervene_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "replay_without_reflection.py"),
        "--input",
        str(args.reflection_output),
        "--output",
        str(args.counterfactual_output),
        "--max-input-tokens",
        str(args.max_input_tokens),
        "--max-new-tokens",
        str(args.max_new_tokens),
        "--seed",
        str(args.seed),
        "--torch-dtype",
        args.torch_dtype,
        "--prompt-file",
        str(args.prompt_file),
    ]
    maybe_add(command, "--model-name-or-path", args.model_name_or_path)
    maybe_add(command, "--device-map", args.device_map)
    if args.trust_remote_code:
        command.append("--trust-remote-code")
    return command


def main() -> None:
    args = parse_args()

    if should_run(args.stage, "generate"):
        run_command(generate_command(args))
    if should_run(args.stage, "intervene"):
        run_command(intervene_command(args))
    if should_run(args.stage, "ciu"):
        records = estimate_ciu_file(args.reflection_output, args.counterfactual_output, args.ciu_output)
        print(f"Wrote {len(records)} CIU records to {args.ciu_output}")
    if should_run(args.stage, "fma"):
        fma_scores, distribution = aggregate_fma_file(args.ciu_output, args.fma_output)
        print(f"Wrote {len(fma_scores)} FMA records to {args.fma_output}; distribution={distribution}")
    if should_run(args.stage, "eval"):
        report = write_phase1_eval_report(args.ciu_output, args.fma_output, args.report_output)
        print(f"Wrote Phase 1 eval report to {args.report_output}; keys={sorted(report.keys())}")


if __name__ == "__main__":
    main()
