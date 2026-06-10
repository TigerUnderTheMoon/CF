"""Generate position-stratified report for GSM8K + HotpotQA."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fma.data import load_open_traces  # noqa: E402
from fma.eval.masking_ciu import compute_masking_ciu  # noqa: E402
from fma.eval.position_stratified import (  # noqa: E402
    compute_position_baseline_accuracy,
    compute_position_stratified_accuracy,
    write_position_report,
)


def main() -> None:
    results: dict[str, dict] = {}

    print("=== GSM8K (1319 traces) ===")
    gsm8k = load_open_traces("gsm8k_cot", max_samples=-1, classify_operations=True)
    n_steps = sum(len(r.step_annotations) for r in gsm8k)
    print(f"  Traces: {len(gsm8k)}  Steps: {n_steps}")
    fma = compute_masking_ciu(gsm8k)
    nz = sum(1 for v in fma.values() if any(abs(s) > 0 for s in v))
    print(f"  Nonzero FMA: {nz}/{len(fma)}")

    ps = compute_position_stratified_accuracy(gsm8k, fma)
    pb = compute_position_baseline_accuracy(gsm8k)
    results["gsm8k"] = {"fma": ps, "baseline_pos": pb}

    print("  Position-stratified FMA:")
    for bn in ["early", "middle", "late"]:
        print(f"    {bn:7s}: {ps[bn]}")

    print("\n=== HotpotQA (500 traces) ===")
    hotpotqa = load_open_traces(
        "hotpotqa",
        split="validation",
        max_samples=500,
        trace_dir="outputs/hotpotqa_traces",
        classify_operations=False,
    )
    n_steps_hq = sum(len(r.step_annotations) for r in hotpotqa)
    print(f"  Traces: {len(hotpotqa)}  Steps: {n_steps_hq}")
    fma_hq = compute_masking_ciu(hotpotqa)
    nz_hq = sum(1 for v in fma_hq.values() if any(abs(s) > 0 for s in v))
    print(f"  Nonzero FMA: {nz_hq}/{len(fma_hq)}")

    ps_hq = compute_position_stratified_accuracy(hotpotqa, fma_hq)
    pb_hq = compute_position_baseline_accuracy(hotpotqa)
    results["hotpotqa"] = {"fma": ps_hq, "baseline_pos": pb_hq}

    print("  Position-stratified FMA:")
    for bn in ["early", "middle", "late"]:
        print(f"    {bn:7s}: {ps_hq[bn]}")

    out = Path("outputs/downstream_comparison_v1/position_stratified_report.json")
    write_position_report(ps, pb, out)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
