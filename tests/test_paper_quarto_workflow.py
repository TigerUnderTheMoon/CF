from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
JIIS = PAPER / "JIIS_submission"
FINAL_SOURCE = JIIS / "source"
FINAL_PACKAGE = JIIS / "submission_package"

TITLE = (
    "Structural Labels for Stratified Audit Budget Allocation in "
    "Knowledge-Graph Dependency Flows"
)


def test_jiis_submission_source_declares_current_latex_contract() -> None:
    manuscript = (FINAL_SOURCE / "manuscript.tex").read_text(encoding="utf-8")
    supplementary = (FINAL_SOURCE / "supplementary.tex").read_text(encoding="utf-8")
    references = (FINAL_SOURCE / "references.bib").read_text(encoding="utf-8")

    assert TITLE in manuscript
    assert TITLE in supplementary
    assert r"\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}" in manuscript
    assert r"\input{" not in manuscript
    assert "Impact Coverage@K" in manuscript
    assert "Life-Saving First" in manuscript
    assert (
        "This experiment validates the proposed audit representation under controlled "
        "knowledge-maintenance scenarios on a real KG substrate"
    ) in manuscript
    assert "not a same-graph rerun" in manuscript
    assert "10.1016/j.knosys.2025.113503" in references
    assert "10.1016/j.knosys.2025.113648" in references
    assert "10.1016/j.knosys.2024.112410" in references


def test_jiis_final_upload_boundary_contains_required_files() -> None:
    required = {
        "manuscript.pdf",
        "supplementary.pdf",
        "manuscript.tex",
        "supplementary.tex",
        "references.bib",
        "sn-jnl.cls",
        "sn-mathphys-num.bst",
    }
    forbidden_suffixes = (
        ".aux",
        ".bbl",
        ".blg",
        ".fdb_latexmk",
        ".fls",
        ".log",
        ".out",
        ".synctex.gz",
    )

    observed = {path.name for path in FINAL_PACKAGE.iterdir() if path.is_file()}

    assert required <= observed
    assert not [
        path.name
        for path in FINAL_PACKAGE.iterdir()
        if path.is_file() and any(path.name.endswith(suffix) for suffix in forbidden_suffixes)
    ]
    assert (FINAL_PACKAGE / "manuscript.pdf").read_bytes().startswith(b"%PDF-")


def test_paper_build_workflow_is_wired_to_current_kbs_package() -> None:
    workflow_text = (ROOT / ".github" / "workflows" / "paper-build.yml").read_text(
        encoding="utf-8"
    )

    required_snippets = [
        "scripts/check_claim_boundaries.py --active-only",
        "curl -I -L https://doi.org/",
        "scripts/verify_kbs_submission_package.py",
        "--package-dir paper/kbs_submission/final_package",
        "--min-manuscript-pages 12",
        "--max-manuscript-pages 20",
        "latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex",
        "DVC remote unavailable in CI; pipeline contract-only check passed",
        "tests/test_prm800k_audit_prioritization.py",
        "tests/test_kbs_submission_package_verifier.py",
    ]
    for snippet in required_snippets:
        assert snippet in workflow_text

    assert "quarto-dev/quarto-actions/setup" not in workflow_text
    assert "quarto render paper" not in workflow_text


def test_legacy_quarto_sources_are_not_active_submission_gate() -> None:
    legacy_quarto = ROOT / "docs" / "legacy" / "diagnostic_fma_paper" / "_quarto.yml"

    assert legacy_quarto.exists()
    assert not (PAPER / "_quarto.yml").exists()
