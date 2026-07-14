from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import zipfile
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
    assert report["package_directories"] == []
    assert report["schema_valid"] is True
    assert report["archive_checksum_errors"] == []
    assert report["latex_warnings"] == []
    assert set(report["figure_references"]) == {
        "fig_scar_framework.pdf",
        "wikidata_core_structure.png",
        "wikidata_impact_coverage_comparison.png",
    }
    assert report["errors"] == []


def test_jiis_source_is_flat_and_bounded() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")

    assert r"\documentclass[pdflatex,sn-basic]{sn-jnl}" in manuscript
    assert "Numbered" not in manuscript.split("\n", 6)[3]
    assert r"\input{" not in manuscript
    assert "A Structural Contract for Audit Records in Budget-Aware Knowledge-Graph Maintenance" in manuscript
    assert "Structural Contract for Audit Records (SCAR)" in manuscript
    assert "SCAR stores structural audit information in a machine-readable record" in manuscript
    assert "SC-FMA" not in manuscript
    assert "Structural label extractor" in manuscript
    assert "illustrative policy consumer" in manuscript.lower()
    assert "Impact Coverage@K" in manuscript
    assert r"U_\lambda(S_K)" not in manuscript
    assert "PageRank and centrality" in manuscript
    assert "KG quality assessment" in manuscript
    assert "XAI attribution" in manuscript
    assert "reachable descendants" in manuscript
    assert "Life-Saving First" in manuscript
    assert "No-Fallback Ablation" not in manuscript
    assert "This paper establishes the representation protocol and controlled extraction fidelity" in manuscript
    assert "not a quantitatively established representation advantage over scalar scoring" not in manuscript
    assert "Random Stratified" in manuscript
    assert "Betweenness Centrality" in manuscript
    assert "Directed Out-Closeness Centrality" in manuscript
    assert "average path length" in manuscript.lower()
    assert "transitive closure" in manuscript
    assert "Flat Top-K uses the shared" in manuscript
    assert "sole ranking criterion" in manuscript
    assert "Recall@25%" not in manuscript
    assert "Supplementary Tables C.8 and C.9" not in manuscript
    assert "Full edge lists" not in manuscript
    assert "production effectiveness" in manuscript
    assert "do not show that the representation is robust to arbitrary KG noise" in manuscript
    assert r"\label{tab:prm800k-boundary-compact}" not in manuscript
    assert "Supplementary Appendices A--C" in manuscript
    assert "| Method |" not in manuscript


def test_jiis_abstract_centers_representation_and_reports_negative_policy_result() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    abstract = manuscript.split(r"\abstract{", 1)[1].split("}\n\n\\keywords", 1)[0]

    for policy_detail in ("Flat Top-K", "0.993", "0.953", "0.385", "Holm"):
        assert policy_detail not in abstract
    assert "Intelligent information systems" in abstract
    assert "audit-record representation contract" in abstract
    assert "Greedy Maximum Coverage outperforms" in abstract
    assert "consumer choice materially affects" in abstract
    assert "F1=1.000" not in abstract
    assert "rather than" not in abstract.lower()


def test_jiis_introduction_has_venue_relevant_citation_density() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    introduction = manuscript.split(r"\section{Introduction}", 1)[1].split(
        r"\section{Related Work}", 1
    )[0]
    cite_groups = re.findall(r"\\citep\{([^}]+)\}", introduction)
    cited_keys = {
        key.strip()
        for group in cite_groups
        for key in group.split(",")
    }

    assert len(cite_groups) >= 5
    assert len(cited_keys) >= 8
    assert {
        "slifka2023evolvable",
        "ma2023temporalrdf",
        "malburg2023mapek",
    } <= cited_keys
    assert "rather than" not in introduction.lower()


def test_jiis_results_prioritize_fidelity_and_demote_policy_statistics() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    supplementary = (JIIS / "source" / "supplementary.tex").read_text(encoding="utf-8")

    assert "The following results are organized by evidence priority" in manuscript
    assert r"\subsection{Controlled extraction fidelity}" in manuscript
    assert r"\subsection{Illustrative policy consumption on controlled substrates}" in manuscript
    assert "Illustrative policy consumption of SCAR fields" in manuscript
    assert "Fair-v1 policy consumption across controlled substrates" in manuscript
    assert "single Holm family" in manuscript
    assert "Cliff's" not in manuscript
    assert "p=0.385" not in manuscript
    assert "Policy-consumption statistics, Pareto analysis, and utility" in supplementary
    assert "matched-pairs rank-biserial" in supplementary
    assert "Cliff's" not in supplementary
    assert "Greedy Maximum Coverage is higher than LSF on both" in supplementary


def test_jiis_artifact_and_system_positioning_is_venue_aligned() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    bibliography = (JIIS / "source" / "references.bib").read_text(encoding="utf-8")

    assert r"\subsection{Artifact and System Positioning}" in manuscript
    assert "knowledge representation, maintenance, and evolution" in manuscript
    for citation_key in (
        "hevner2004design",
        "gregor2013positioning",
        "slifka2023evolvable",
        "ma2023temporalrdf",
        "sacenti2021kgsummarization",
        "malburg2023mapek",
    ):
        assert citation_key in manuscript
        assert "{" + citation_key + "," in bibliography


def test_jiis_f1_contexts_state_the_deterministic_evidence_boundary() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    supplementary = (JIIS / "source" / "supplementary.tex").read_text(encoding="utf-8")
    abstract = manuscript.split(r"\abstract{", 1)[1].split("}\n\n\\keywords", 1)[0]
    assert "exact implementation of the declared structural rules" in abstract
    assert "do not provide independent ground truth" in abstract
    assert "same deterministic rules used to define the controlled reference labels" in manuscript
    assert "independent ground truth" in supplementary
    assert "fixture-specific coincidence under that protocol" in manuscript
    assert "matched-positive-count protocol" in manuscript


def test_jiis_method_terms_complexity_and_practice_implications_are_bounded() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")

    assert "Core notation and audit fields" in manuscript
    notation_block = manuscript.split("Core notation and audit fields", 1)[1].split(
        r"\subsection{Structural label extractor}", 1
    )[0]
    assert r"\begin{table}" not in notation_block
    for field in (
        r"\texttt{is\_bottleneck}",
        r"\texttt{is\_redundant}",
        r"\texttt{redundancy\_group\_id}",
        r"\texttt{sink\_drop\_count}",
        r"\texttt{raw\_risk\_score}",
    ):
        assert field in notation_block
    assert r"\texttt{bottleneck} and \texttt{redundancy}" not in manuscript
    assert "its bottleneck" not in manuscript
    assert r"O(|V|(|V|+|E|))" in manuscript
    assert r"O(|V|^2|S|)" in manuscript
    assert r"O(|V|^2+|E|)" in manuscript
    assert r"\subsection{Implications for Practice}" in manuscript
    assert "The archived data and code run this pipeline end to end" in manuscript
    assert "Measuring human efficiency, accuracy, or production effectiveness requires" in manuscript


def test_jiis_table_two_contains_native_articulation_point_baseline() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")

    table = manuscript.split(r"\label{tab:kg-label-validation}", 1)[1].split(
        r"\end{table}", 1
    )[0]
    assert "Undirected Articulation Point & 0.000 & N/A & 124" in table
    assert r"\makecell{Reference redundancy\\positives}" in table
    assert "native binary output" in manuscript


def test_jiis_policy_utility_and_sensitivity_are_supplementary_only() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    supplementary = (JIIS / "source" / "supplementary.tex").read_text(encoding="utf-8")

    assert r"U_\lambda(S_K)" not in manuscript
    assert r"\label{eq:coverage-protection-utility}" not in manuscript
    assert "0.661" not in manuscript
    assert "0.661" not in supplementary
    assert r"U_\lambda(S_K)" in supplementary
    assert r"\label{eq:supp-coverage-protection-utility}" in supplementary
    assert "Greedy Maximum Coverage is higher than LSF on both $C$ and $P$" in manuscript
    assert "provides no evidence of an effective LSF governance trade-off" in manuscript
    assert "PRM800K necessary-condition" not in supplementary
    assert "16 stable SHA-256 anchor clusters" not in manuscript
    assert "Budget-sweep and anchor-cluster results" not in manuscript
    assert "Sensitivity results are provided in Supplementary Section" in manuscript


def test_jiis_main_presentation_conventions_are_unambiguous() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")

    assert r"\detokenize{raw_risk_score}" not in manuscript
    assert manuscript.count(r"\texttt{raw\_risk\_score}") >= 3
    assert "Avg. Path Length" in manuscript
    assert (
        "Inferential details for the policy comparison are retained in the Supplementary "
        "Material; the representation claim does not rely on these statistics."
    ) in manuscript
    assert r"Figure~\ref{fig:overall-framework}" in manuscript
    assert r"\includegraphics[width=\linewidth]{fig_scar_framework.pdf}" in manuscript
    assert "the downstream maintenance uses shown are illustrative" in manuscript
    assert manuscript.index(r"\label{fig:overall-framework}") < manuscript.index(
        r"\label{fig:wikidata-core-structure}"
    )
    assert manuscript.index(r"\label{fig:wikidata-core-structure}") < manuscript.index(
        r"\label{fig:impact-coverage-comparison}"
    )
    assert manuscript.count(r"\section*{Statements and Declarations}") == 1
    for heading in ("Funding", "Competing Interest", "AI Disclosure", "Data Availability", "CRediT"):
        assert heading in manuscript


def test_jiis_consolidates_evidence_boundary_and_main_structure() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")

    boundary_sentence = (
        "This paper establishes the representation protocol and controlled extraction "
        "fidelity."
    )
    assert manuscript.count(boundary_sentence) == 1
    assert "Appendix A. Synthetic Scalability and Threshold Sensitivity" not in manuscript
    assert r"\section{Boundary Diagnosis}" not in manuscript
    assert "Supplementary Appendices A--C" in manuscript
    assert "1.100" not in manuscript
    assert manuscript.index(r"\section{Results}") < manuscript.index(r"\section{Discussion}")
    assert manuscript.index(r"\section{Discussion}") < manuscript.index(r"\section{Limitations}")
    assert manuscript.index(r"\section{Limitations}") < manuscript.index(r"\section{Conclusions}")


def test_jiis_disclosure_and_reproducibility_commitments_are_explicit() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")

    assert "manuscript organization and argument-consistency checks" in manuscript
    assert "frozen reproduction archive supplied with this submission" in manuscript
    assert "Zenodo" in manuscript
    assert "GitHub" in manuscript


def test_jiis_reproducibility_archive_contains_frozen_inputs_and_code() -> None:
    archive = JIIS / "submission_package" / "reproducibility_archive.zip"
    assert archive.exists()

    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        archived_core = bundle.read("scripts/jiis_countries_kg_validation_core.py")

    required = {
        "README.md",
        "SHA256SUMS.txt",
        "configs/jiis_controlled_maintenance_fair_v1.yaml",
        "requirements-jiis-lock.txt",
        "schemas/scar_audit_record.schema.json",
        "scripts/run_wikidata_scientist_audit.py",
        "src/fma/eval/wikidata_scientist_audit_runner.py",
        "src/fma/eval/wikidata_controlled_audit.py",
        "data/wdqs_cache.json",
        "data/countries_kg_labels_cached.json",
        "results/countries/audit_records.jsonl",
        "results/countries/jiis_audit_case_report.json",
        "results/wikidata/metrics/noise_inference_family.json",
        "results/wikidata/metrics/utility_tradeoff.json",
        "results/wikidata/traces/audit_records.jsonl",
    }
    assert required <= names
    assert archived_core == (ROOT / "scripts" / "jiis_countries_kg_validation_core.py").read_bytes()


def test_jiis_main_narrative_appears_in_first_five_pages() -> None:
    pdf = PdfReader(str(JIIS / "source" / "manuscript.pdf"))
    first_five = "\n".join(page.extract_text() or "" for page in pdf.pages[:5])
    normalized_first_five = " ".join(first_five.split())

    assert "Life-Saving First" in first_five
    assert "Impact Coverage@K" in first_five
    assert "reachable descendants" in first_five
    assert "Jaccard similarity strictly greater than 0.85" in normalized_first_five


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
        "sn-basic.bst",
        "fig_scar_framework.pdf",
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
    assert not [path.name for path in package.iterdir() if path.is_dir()]
    assert {path.name for path in package.glob("*.png")} == {
        "wikidata_core_structure.png",
        "wikidata_impact_coverage_comparison.png",
    }
    assert not [
        path.name
        for path in package.iterdir()
        if path.is_file() and any(path.name.endswith(suffix) for suffix in build_suffixes)
    ]


def test_jiis_supplementary_has_only_three_current_appendices() -> None:
    supplementary = (JIIS / "source" / "supplementary.tex").read_text(encoding="utf-8")

    assert supplementary.count(r"\section{Appendix") == 3
    assert "Appendix A. Synthetic scalability and threshold sensitivity" in supplementary
    assert "Appendix B. Policy-consumption statistics" in supplementary
    assert "Appendix C. Record schema, cache lock, and offline reproduction" in supplementary
    for legacy in (
        "Extended Proofs",
        "SCU",
        "QP Calibration",
        "Ridge",
        "Projection",
        "PRM800K",
        "WebQSP",
        "MuSiQue",
        "Stage 2",
        "Failure Taxonomy",
        "Audit Cards",
    ):
        assert legacy not in supplementary
    assert "scar-1.0" in supplementary
    assert r"noise\_inference\_family.json" in supplementary

    for relative in ("source/supplementary.pdf", "submission_package/supplementary.pdf"):
        pdf = PdfReader(str(JIIS / relative))
        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:3])
        normalized = " ".join(text.split())

        assert "A Structural Contract for Audit Records in Budget-Aware Knowledge-Graph Maintenance" in normalized
        assert "Synthetic scalability" in normalized


def test_jiis_rendered_bibliography_has_no_placeholders() -> None:
    pdf = PdfReader(str(JIIS / "source" / "manuscript.pdf"))
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    compact_text = re.sub(r"\s+", "", text)

    assert "???" not in text
    assert re.search(r"\([A-Z][A-Za-z-]+ et al\., \d{4}", text)
    assert not re.search(r"\[\d+(?:,\s*\d+)+\]", text)
    assert "https://doi.org/" in text
    assert "10.18653/v1/2021.emnlp-main.585" in compact_text
    assert "10.1007/s10844-023-00809-w" in compact_text

    references = text.split("References", 1)[1]
    assert references.index("Abraham R") < references.index("Zheng C")


def test_jiis_active_bibliography_contains_main_text_citations() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    supplementary = (JIIS / "source" / "supplementary.tex").read_text(encoding="utf-8")
    bibliography = (JIIS / "source" / "references.bib").read_text(encoding="utf-8")

    assert "@article{noy2019industry," in bibliography
    assert "@article{abraham2019data," in bibliography

    cited_keys = {
        key.strip()
        for group in re.findall(r"\\citep\{([^}]+)\}", manuscript + supplementary)
        for key in group.split(",")
    }
    entries = {
        match.group("key"): match.group("body")
        for match in re.finditer(
            r"(?ms)^@\w+\{(?P<key>[^,]+),(?P<body>.*?)(?=^@|\Z)",
            bibliography,
        )
    }

    assert cited_keys <= entries.keys()
    for key in cited_keys:
        assert re.search(r"(?im)^\s*(doi|url)\s*=", entries[key]), key

    entailment_tree = entries["dalvi2021entailmenttrees"]
    assert "Empirical Methods in Natural Language Processing" in entailment_tree
    assert "10.18653/v1/2021.emnlp-main.585" in entailment_tree


def test_jiis_main_text_maps_design_requirements_to_record_evidence() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")

    assert r"\subsection{Design requirements and traceability}" in manuscript
    assert r"\label{tab:design-requirement-traceability}" in manuscript
    for requirement in (
        "Snapshot identity",
        "Candidate reproducibility",
        "Structural role preservation",
        "Dependency consequence",
        "Policy-independent consumption",
    ):
        assert requirement in manuscript


def test_jiis_worked_record_matches_archived_fair_v1_values() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    records_path = (
        ROOT
        / "outputs"
        / "jiis_controlled_maintenance_fair_v1"
        / "traces"
        / "audit_records.jsonl"
    )
    records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    record = next(item for item in records if item["artifact_id"] == "Q101010678")

    impact_path = (
        ROOT
        / "outputs"
        / "jiis_controlled_maintenance_fair_v1"
        / "metrics"
        / "impact_coverage.json"
    )
    impact = json.loads(impact_path.read_text(encoding="utf-8"))
    methods = impact["primary_seed_detail"]["methods"]

    assert record["schema_version"] == "scar-1.0"
    assert record["at_risk_terminal_ids"] == ["Q1202039"]
    assert record["downstream_impact_count"] == 2
    assert record["sink_drop_count"] == 1
    assert record["is_bottleneck"] is True
    assert record["is_redundant"] is False
    assert record["raw_risk_score"] == 1 / 63
    assert "Q101010678" in methods["greedy_maximum_coverage"]["selected_node_ids"]
    assert "Q101010678" not in methods["life_saving_first"]["selected_node_ids"]

    assert r"\subsection{Worked audit-record example}" in manuscript
    for archived_value in (
        "Q101010678",
        "Q1202039",
        "P361",
        "0.015873",
        record["extractor_metadata"]["candidate_id_sha256"][:8],
        record["graph_snapshot"]["sha256"][:8],
    ):
        assert archived_value in manuscript
    assert "Greedy Maximum Coverage selected Q101010678" in manuscript
    assert "Life-Saving First did not select it" in manuscript


def test_jiis_main_text_formalizes_record_and_policy_contract() -> None:
    manuscript = (JIIS / "source" / "manuscript.tex").read_text(encoding="utf-8")
    method = manuscript.split(r"\section{Method}", 1)[1].split(r"\section{Results}", 1)[0]

    for label in (
        "eq:structural-sets",
        "eq:record-fields",
        "eq:redundancy-graph",
        "eq:raw-risk",
        "eq:scar-record",
        "eq:lsf-strata",
        "eq:lsf-recurrence",
        "eq:greedy-marginal",
    ):
        assert rf"\label{{{label}}}" in method

    for contract_token in (
        r"\operatorname{Reach}_{H}(U)",
        r"D(v)=\operatorname{Desc}_{G}(v)",
        r"T(v)=D(v)\cap V_{\mathrm{term}}",
        r"a(v)=\mathbf{1}",
        r"b(v)=\mathbf{1}",
        r"q_{\theta}(v)=\mathbf{1}",
        r"\operatorname{SCAR}_{G}(v)",
        r"\mathcal{L}_{1}",
        r"S^{(j)}",
        r"M_t(v)",
    ):
        assert contract_token in method

    assert method.count(r"\begin{equation}") >= 10
    assert r"U_\lambda" not in method


def test_jiis_output_reports_are_claim_bounded() -> None:
    claim_report = (JIIS / "reports" / "claim_boundary_report.md").read_text(encoding="utf-8")

    assert "structural label extractor" in claim_report
    assert "Impact Coverage@K" in claim_report
    assert "fair-v1 policy-consumption diagnostics" in claim_report
    assert "Greedy Maximum Coverage dominates Life-Saving First" in claim_report
    assert "production knowledge-base validation" in claim_report
    assert "causal effect" in claim_report
    assert "human usefulness" in claim_report
