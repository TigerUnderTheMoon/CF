"""Plot real_task_v3 governance diagnostic key contributions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import matplotlib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from scripts.generate_governance_diagnostic_report import (
    DEFAULT_AUDIT_PATH,
    DEFAULT_OUTPUT_DIR,
    EMPTY_STRING_SHA256,
    SIX_KEYS,
    per_key_marginal_contribution,
)


DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "governance_diagnostic_upset.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot real_task_v3 governance diagnostic key contributions."
    )
    parser.add_argument("--audit-path", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_governance_diagnostic_plot(
        audit_path=args.audit_path,
        output_path=args.output_path,
    )
    print(json.dumps(result, sort_keys=True))


def build_governance_diagnostic_plot(
    *,
    audit_path: Path = DEFAULT_AUDIT_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, str]:
    audit = _read_json(audit_path)
    counts = per_key_marginal_contribution(audit)
    ordered_keys = sorted(SIX_KEYS, key=lambda key: counts.get(key, 0))
    values = [counts.get(key, 0) for key in ordered_keys]

    fig = plt.figure(figsize=(11, 7), constrained_layout=True)
    grid = fig.add_gridspec(2, 1, height_ratios=[2.2, 1.4])
    ax_counts = fig.add_subplot(grid[0])
    ax_matrix = fig.add_subplot(grid[1])

    colors = [
        "#b91c1c" if key == "non_empty_alias_hash" else "#2563eb"
        for key in ordered_keys
    ]
    ax_counts.barh(ordered_keys, values, color=colors)
    ax_counts.set_title("Real-Task v3 Governance Diagnostic: Six-Key Exclusion Contributions")
    ax_counts.set_xlabel("Rows matched by key (max count across exclusion sources)")
    ax_counts.grid(axis="x", color="#e5e7eb", linewidth=0.8)
    for index, value in enumerate(values):
        ax_counts.text(value, index, f" {value}", va="center", fontsize=9)

    matrix = np.eye(len(SIX_KEYS), dtype=int)
    all_keys_row = np.ones((1, len(SIX_KEYS)), dtype=int)
    display = np.vstack([matrix, all_keys_row])
    row_labels = [f"only {key}" for key in SIX_KEYS] + ["OR-union hard stop"]
    ax_matrix.imshow(display, aspect="auto", cmap="Greys", vmin=0, vmax=1)
    ax_matrix.set_xticks(range(len(SIX_KEYS)))
    ax_matrix.set_xticklabels(SIX_KEYS, rotation=35, ha="right")
    ax_matrix.set_yticks(range(len(row_labels)))
    ax_matrix.set_yticklabels(row_labels)
    ax_matrix.set_title("Audit-Limited Overlap Matrix")
    ax_matrix.set_xlabel("Blocking key present in intersection")

    annotation = (
        "empty alias collision: "
        f"SHA-256(\"\")={EMPTY_STRING_SHA256[:12]}..."
    )
    ax_counts.annotate(
        annotation,
        xy=(counts.get("non_empty_alias_hash", 0), ordered_keys.index("non_empty_alias_hash")),
        xytext=(0.50, 0.12),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": "#7f1d1d"},
        fontsize=9,
        color="#7f1d1d",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return {
        "status": "GOVERNANCE_DIAGNOSTIC_PLOT_WRITTEN",
        "output_path": str(output_path),
    }


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


if __name__ == "__main__":
    main()
