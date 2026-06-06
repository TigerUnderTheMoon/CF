from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


EXPECTED_MAIN_FIGURE_LABELS = {
    1: "fig-attribution-prune",
    2: "fig-structural-mode-comparison",
    3: "fig-redundancy-density",
    4: "fig-compensation-distribution",
    5: "fig-resilience-curves",
}


@dataclass(frozen=True)
class MainFigure:
    number: int
    inventory_path: str

    @property
    def filename(self) -> str:
        return Path(self.inventory_path).name


def parse_main_figures(inventory_text: str) -> list[MainFigure]:
    figures: list[MainFigure] = []
    pattern = re.compile(r"`(?P<path>outputs/figures/[^`]+)`.*Main Figure (?P<number>\d+)")

    for line in inventory_text.splitlines():
        match = pattern.search(line)
        if match is None:
            continue
        figures.append(
            MainFigure(
                number=int(match.group("number")),
                inventory_path=match.group("path"),
            )
        )

    return sorted(figures, key=lambda figure: figure.number)


def check_inventory(paper_dir: Path, require_generated: bool) -> list[str]:
    inventory_path = paper_dir / "figure_inventory.md"
    results_path = paper_dir / "chapters" / "05_results.qmd"
    generated_dir = paper_dir / "generated" / "figures"

    errors: list[str] = []

    if not inventory_path.exists():
        return [f"missing inventory: {inventory_path}"]
    if not results_path.exists():
        return [f"missing results chapter: {results_path}"]

    figures = parse_main_figures(inventory_path.read_text(encoding="utf-8"))
    expected_numbers = sorted(EXPECTED_MAIN_FIGURE_LABELS)
    actual_numbers = [figure.number for figure in figures]
    if actual_numbers != expected_numbers:
        errors.append(
            f"main figure inventory mismatch: expected {expected_numbers}, found {actual_numbers}"
        )

    results_text = results_path.read_text(encoding="utf-8")
    for figure in figures:
        label = EXPECTED_MAIN_FIGURE_LABELS.get(figure.number)
        if label is None:
            errors.append(f"unexpected main figure number: {figure.number}")
            continue
        if f"#{label}" not in results_text:
            errors.append(f"missing Quarto label #{label} for Main Figure {figure.number}")
        if figure.filename not in results_text:
            errors.append(
                f"results chapter does not reference generated file for Main Figure {figure.number}: "
                f"{figure.filename}"
            )
        if require_generated and not (generated_dir / figure.filename).exists():
            errors.append(
                f"generated figure missing for Main Figure {figure.number}: "
                f"{generated_dir / figure.filename}"
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that Quarto results figures match paper/figure_inventory.md."
    )
    parser.add_argument("--paper-dir", default="paper", type=Path)
    parser.add_argument(
        "--require-generated",
        action="store_true",
        help="Require paper/generated/figures files to exist after quarto render.",
    )
    args = parser.parse_args(argv)

    errors = check_inventory(args.paper_dir, args.require_generated)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("figure inventory check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
