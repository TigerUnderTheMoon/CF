from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
JIIS = ROOT / "paper" / "JIIS_submission"


def test_jiis_submission_verifier_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_jiis_submission.py",
            "--workspace",
            "paper/JIIS_submission",
            "--json",
            "paper/JIIS_submission/reports/jiis_verification_report.json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((JIIS / "reports" / "jiis_verification_report.json").read_text(encoding="utf-8"))
    assert report["abstract_words"] >= 150
    assert report["abstract_words"] <= 250
    assert report["keyword_count"] == 6
    assert report["manuscript_pages"] >= 10
    assert report["manuscript_pages"] <= 25
    assert report["errors"] == []


def test_jiis_source_is_flat_and_bounded() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")

    assert r"\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}" in manuscript
    assert r"\input{" not in manuscript
    assert "Structural Labels for Stratified Audit Budget Allocation in Knowledge-Graph Dependency Flows" in manuscript
    assert "systematization of fixed-budget audit allocation" in manuscript
    assert "structural label extractor" in manuscript
    assert "stratified budget allocation" in manuscript
    assert "Impact Coverage@K" in manuscript
    assert "reachable descendants" in manuscript
    assert "Life-Saving First" in manuscript
    assert "No-Fallback Ablation matches the main policy (both 1.000)" in manuscript
    assert "Random Stratified" in manuscript
    assert "Betweenness Centrality" in manuscript
    assert "Directed Out-Closeness Centrality" in manuscript
    assert "average path length" in manuscript
    assert "transitive closure" in manuscript
    assert "Flat Top-K baseline (using the shared" in manuscript
    assert "sole ranking criterion" in manuscript
    assert "Recall@25%" not in manuscript
    assert "Supplementary Tables C.8 and C.9" not in manuscript
    assert "Full edge lists" not in manuscript
    assert "production knowledge-base validation" in manuscript
    assert "do not claim that structural labels are robust to arbitrary KG noise" in manuscript
    assert "| Method |" not in manuscript


def test_jiis_main_narrative_appears_in_first_five_pages() -> None:
    pdf = PdfReader(str(JIIS / "source" / "manuscript.pdf"))
    first_five = "\n".join(page.extract_text() or "" for page in pdf.pages[:5])

    assert "Life-Saving First" in first_five
    assert "Impact Coverage@K" in first_five
    assert "reachable descendants" in first_five
    assert "Jaccard > 0.85" in first_five or "Jaccard>0.85" in first_five


def test_jiis_human_eval_pending_package_is_blank_and_blinded() -> None:
    human_dir = JIIS / "human_eval_pending"
    key_path = human_dir / "analyst_only" / "blinding_key.csv"

    assert key_path.exists()
    for evaluator_idx in range(1, 4):
        folder = human_dir / f"evaluator_{evaluator_idx}"
        sheet = folder / f"rating_sheet_evaluator_{evaluator_idx}.csv"
        assert (folder / "INSTRUCTIONS.md").exists()
        assert (folder / "RETURN_DECLARATION.md").exists()
        assert len(list((folder / "cards").glob("*.md"))) == 9
        with sheet.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 9
        for row in rows:
            assert row["usefulness_1_5"] == ""
            assert row["interpretability_1_5"] == ""
            assert row["actionability_1_5"] == ""
            assert row["would_prioritize_yes_no"] == ""


def test_jiis_submission_package_has_no_build_artifacts() -> None:
    package = JIIS / "submission_package"
    required = {
        "manuscript.pdf",
        "supplementary.pdf",
        "manuscript.tex",
        "supplementary.tex",
        "references.bib",
        "sn-jnl.cls",
        "sn-mathphys-num.bst",
    }
    build_suffixes = (
        ".aux",
        ".bbl",
        ".blg",
        ".log",
        ".fls",
        ".fdb_latexmk",
        ".out",
        ".synctex.gz",
    )

    files = {path.name for path in package.iterdir() if path.is_file()}
    assert required <= files
    assert not [
        path.name
        for path in package.iterdir()
        if path.is_file() and any(path.name.endswith(suffix) for suffix in build_suffixes)
    ]


def test_jiis_supplementary_is_restored_full_length() -> None:
    supplementary = (JIIS / "source" / "supplementary.tex").read_text(encoding="utf-8")

    assert "Main-text and supplementary consistency map" in supplementary
    assert r"\label{tab:supp-consistency-map}" in supplementary
    assert r"\label{tab:supp-kg-backend-artifacts}" in supplementary
    assert "Degeneracy handling" in supplementary
    assert "Process-Annotation Variant Details and Audit Readout" in supplementary

    for relative in ("source/supplementary.pdf", "submission_package/supplementary.pdf"):
        pdf = PdfReader(str(JIIS / relative))
        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:3])
        normalized = " ".join(text.split())

        assert len(pdf.pages) >= 10
        assert "Structural Labels for Stratified Audit Budget Allocation" in normalized
        assert "Synthetic scalability" in normalized
        assert "Necessary Condition Diagnosis" in normalized


def test_jiis_output_reports_are_claim_bounded() -> None:
    claim_report = (JIIS / "reports" / "claim_boundary_report.md").read_text(encoding="utf-8")

    assert "structural label extractor" in claim_report
    assert "Impact Coverage@K" in claim_report
    assert "PRM800K necessary-condition diagnosis" in claim_report
    assert "production knowledge-base validation" in claim_report
    assert "causal effect" in claim_report
    assert "human usefulness" in claim_report
