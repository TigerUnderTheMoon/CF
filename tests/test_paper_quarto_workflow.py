from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"


def test_quarto_book_project_declares_requested_chapters_and_formats() -> None:
    config_path = PAPER / "_quarto.yml"
    assert config_path.exists()

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["project"]["type"] == "book"
    assert config["execute"]["cache"] is True
    assert config["bibliography"] == "references.bib"
    assert set(config["format"]) >= {"html", "pdf"}

    expected_chapters = [
        "index.qmd",
        "chapters/01_introduction.qmd",
        "chapters/02_related_work.qmd",
        "chapters/03_methodology.qmd",
        "chapters/04_experiments.qmd",
        "chapters/05_results.qmd",
        "chapters/06_limitations.qmd",
        "chapters/07_conclusion.qmd",
    ]
    assert config["book"]["chapters"] == expected_chapters
    assert config["book"]["appendices"] == ["chapters/appendix.qmd"]

    for chapter in expected_chapters + config["book"]["appendices"]:
        assert (PAPER / chapter).exists()


def test_results_chapter_executes_outputs_and_defines_required_crossrefs() -> None:
    results_qmd = PAPER / "chapters" / "05_results.qmd"
    text = results_qmd.read_text(encoding="utf-8")

    required_snippets = [
        "```{python}",
        "outputs/counterfactual_summary.json",
        "outputs/structural_diagnostics.json",
        "outputs/redundancy_analysis.json",
        "import matplotlib",
        "import seaborn",
        "pd.DataFrame",
        ".to_markdown(",
        "#fig-attribution-prune",
        "@fig-attribution-prune",
        "#tbl-core-diagnostics",
        "@tbl-core-diagnostics",
    ]
    for snippet in required_snippets:
        assert snippet in text


def test_reference_bibliography_is_available_at_quarto_root() -> None:
    references = (PAPER / "references.bib").read_text(encoding="utf-8")

    for key in (
        "@inproceedings{shinn2023reflexion",
        "@inproceedings{madaan2023selfrefine",
        "@article{lightman2023verify",
    ):
        assert key in references


def test_paper_build_workflow_and_inventory_check_are_wired() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "paper-build.yml"
    assert workflow_path.exists()

    workflow_text = workflow_path.read_text(encoding="utf-8")
    for snippet in (
        "paths:",
        "outputs/**",
        "paper/**",
        "quarto-dev/quarto-actions/setup",
        "quarto render paper",
        "check_paper_figure_inventory.py",
        "paper/_book/*.pdf",
    ):
        assert snippet in workflow_text


def test_figure_inventory_checker_accepts_current_quarto_chapter() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_paper_figure_inventory.py",
            "--paper-dir",
            "paper",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
