from __future__ import annotations

from pathlib import Path


V2_1_OUTPUT_NAME = "s_fma_v2_1_fresh_holdout"


def v2_1_failed_provenance_root(output_root: Path) -> Path:
    """Route the abandoned v2.1 output root to its archive provenance path."""

    root = Path(output_root)
    parts = root.parts
    if len(parts) >= 3 and parts[-3:] == ("outputs", "archive", V2_1_OUTPUT_NAME):
        return root
    if len(parts) >= 2 and parts[-2:] == ("outputs", V2_1_OUTPUT_NAME):
        return root.parent / "archive" / root.name
    return root
