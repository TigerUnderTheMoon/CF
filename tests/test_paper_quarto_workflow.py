from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
KBS = PAPER / "kbs_submission"
FINAL_SOURCE = KBS / "final_source"
FINAL_PACKAGE = KBS / "final_package"

TITLE = (
    "Structurally-Calibrated Functional Attribution for Audit Prioritization "
    "in Knowledge-Intensive Reasoning"
)


def test_kbs_submission_source_declares_current_latex_contract() -> None:
    manuscript = (FINAL_SOURCE / "manuscript.tex").read_text(encoding="utf-8")
    supplementary = (FINAL_SOURCE / "supplementary.tex").read_text(encoding="utf-8")
    references = (FINAL_SOURCE / "references.bib").read_text(encoding="utf-8")

    assert TITLE in manuscript
    assert f"Supplementary Material for {TITLE}" in supplementary
    assert "moderate, preliminary real-data support" in manuscript
    assert "validated_kbs_workflow=false" in manuscript
    assert "10.1016/j.knosys.2025.113503" in references
    assert "10.1016/j.knosys.2025.113648" in references
    assert "10.1016/j.knosys.2024.112410" in references


def test_kbs_final_upload_boundary_contains_exact_required_files() -> None:
    expected = {
        "cover_letter.docx",
        "Highlights.docx",
        "latex_source.zip",
        "manuscript.pdf",
        "supplementary.docx",
    }

    observed = {path.name for path in FINAL_PACKAGE.iterdir() if path.is_file()}

    assert observed == expected
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
