"""Verify the manuscript w_struct feature list against the frozen model JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence


BEGIN_MARKER = "w_struct_feature_list_begin"
END_MARKER = "w_struct_feature_list_end"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--manuscript", type=Path, required=True)
    return parser.parse_args(argv)


def load_model_features(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    feature_names = payload.get("feature_names")
    if not isinstance(feature_names, list) or not all(
        isinstance(item, str) for item in feature_names
    ):
        raise ValueError(f"{path} does not contain a string list at feature_names")
    return feature_names


def extract_marked_block(text: str) -> str:
    begin = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if begin < 0 or end < 0 or end <= begin:
        raise ValueError(
            f"manuscript must contain ordered markers {BEGIN_MARKER} and {END_MARKER}"
        )
    return text[begin + len(BEGIN_MARKER) : end]


def normalize_latex_token(token: str) -> str:
    return token.strip().replace(r"\_", "_")


def extract_manuscript_features(path: Path) -> list[str]:
    block = extract_marked_block(path.read_text(encoding="utf-8"))
    matches = re.findall(r"\\texttt\{([^{}]+)\}", block)
    if not matches:
        raise ValueError("marked feature-list block does not contain \\texttt{...} tokens")
    return [normalize_latex_token(match) for match in matches]


def format_feature_list(values: Sequence[str]) -> str:
    return ", ".join(values)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        model_features = load_model_features(args.model)
        manuscript_features = extract_manuscript_features(args.manuscript)
    except Exception as exc:
        print(f"Feature list verification failed: {exc}", file=sys.stderr)
        return 1

    if manuscript_features != model_features:
        print("Feature list mismatch", file=sys.stderr)
        print(f"Model:      {format_feature_list(model_features)}", file=sys.stderr)
        print(f"Manuscript: {format_feature_list(manuscript_features)}", file=sys.stderr)
        return 1

    print(f"Feature list matches ({len(model_features)} features).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
