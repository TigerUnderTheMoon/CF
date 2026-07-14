from __future__ import annotations

import re
from pathlib import Path

from scripts.check_claim_boundaries import (
    ACTIVE_KBS_DOIS,
    iter_active_files,
    scan_active_files,
    scan_text,
    strip_fenced_code,
)


ROOT = Path(__file__).resolve().parents[1]


def _information_sciences_main_text() -> str:
    source_dir = (
        ROOT / "paper" / "information_sciences_submission" / "final_source"
    )
    parts = [(source_dir / "manuscript.tex").read_text(encoding="utf-8")]
    parts.extend(
        path.read_text(encoding="utf-8")
        for path in sorted((source_dir / "sections").glob("*.tex"))
    )
    return "\n".join(parts)


def test_strip_fenced_code_prevents_agents_template_noise():
    text = """Intro [XX]

```python
per-step counterfactual outcome differences
[XX]
```

all interventions are structure-preserving
"""

    stripped = strip_fenced_code(text)

    assert "per-step counterfactual outcome differences" not in stripped
    assert "[XX]" in stripped
    assert "all interventions are structure-preserving" in stripped


def test_claim_scan_allows_boundary_language_but_blocks_positive_claims():
    safe = "This is not external generalization and not deployed KBS validation."
    unsafe = "The method provides deployed KBS validation and external generalization."

    assert scan_text("safe.md", safe) == []
    findings = scan_text("unsafe.md", unsafe)
    assert {finding.pattern for finding in findings} >= {
        "external generalization",
        "deployed KBS validation",
    }


def test_claim_scan_blocks_known_revision_regression_terms():
    text = (
        "The 16-feature Ridge produces independent oracle validation and "
        "audit correctness evidence."
    )

    findings = scan_text("unsafe.tex", text)

    assert {finding.pattern for finding in findings} >= {
        "16-feature",
        "independent oracle",
        "oracle validation",
        "audit correctness",
    }


def test_active_kbs_doi_anchors_are_explicit_and_verified_targets():
    assert ACTIVE_KBS_DOIS == (
        "10.1016/j.knosys.2025.113503",
        "10.1016/j.knosys.2025.113648",
        "10.1016/j.knosys.2024.112410",
    )


def test_information_sciences_source_contains_ciu_granularity_and_adapter_contract():
    manuscript = _information_sciences_main_text()
    references = (
        ROOT / "paper" / "information_sciences_submission" / "final_source" / "references.bib"
    ).read_text(encoding="utf-8")

    assert "coarse trace-level utility anchor" in manuscript
    assert "local representation signals" in manuscript
    assert "causal effect estimates would require a separate identification design" in manuscript.lower()
    assert "Deployment-oriented knowledge-base maintenance and human audit-use protocols remain future validation settings" in manuscript
    assert "fixture-level typed-edge construction only; no deployed workflow validation" in manuscript
    assert "per-step counterfactual outcome differences" not in manuscript
    assert "all interventions are structure-preserving" not in manuscript

    for doi in ACTIVE_KBS_DOIS:
        assert doi in references


def test_information_sciences_source_preserves_main_text_diagnostic_context():
    manuscript = _information_sciences_main_text()

    stress_caption = "SCU component contribution on a structural stress-test fixture"
    kg_stage_section = r"\subsection{Knowledge-Graph Backend Feasibility Study}"

    assert stress_caption in manuscript
    assert kg_stage_section in manuscript
    assert "Evidence Ladder" not in manuscript


def test_information_sciences_source_explicitly_bounds_hyperparameter_and_graph_ablation_claims():
    manuscript = _information_sciences_main_text()
    supplementary = (
        ROOT / "paper" / "information_sciences_submission" / "final_source" / "supplementary.tex"
    ).read_text(encoding="utf-8")
    alpha_beta_grid = (
        ROOT
        / "outputs"
        / "reviewer_v2_experiments"
        / "scu_hyperparameter_sensitivity"
        / "alpha_beta_grid.csv"
    ).read_text(encoding="utf-8")

    assert "gamma/delta and alpha/beta QP sensitivity grids" in manuscript
    assert "supplementary hyperparameter tables" in manuscript
    assert "tab:supp-alpha-beta-sensitivity" not in manuscript
    assert "tab:supp-gamma-delta-sensitivity" not in manuscript
    assert "TF-IDF topical default (0.0515) did not exceed temporal-only edges (0.0596)" in manuscript
    assert "embedding backend (0.0615)" in manuscript

    assert r"\label{tab:supp-alpha-beta-sensitivity}" in supplementary
    assert "0.5,0.0,0.639275217471432" in alpha_beta_grid
    assert "2.0,1.0,0.5572138842322" in alpha_beta_grid
    assert (
        r"\texttt{scu\_hyperparameter\_sensitivity.json}" in supplementary
        or r"\path{scu_hyperparameter_sensitivity.json}" in supplementary
    )
    assert (
        r"\texttt{scu\_hyperparameter\_sensitivity.md}" in supplementary
        or r"\path{scu_hyperparameter_sensitivity.md}" in supplementary
    )
    assert (
        r"\texttt{alpha\_beta\_grid.csv}" in supplementary
        or r"\path{alpha_beta_grid.csv}" in supplementary
    )
    assert (
        r"\texttt{gamma\_delta\_grid.csv}" in supplementary
        or r"\path{gamma_delta_grid.csv}" in supplementary
    )


def test_information_sciences_reports_new_automated_controls_without_human_claim():
    manuscript = _information_sciences_main_text()
    registry = (ROOT / "paper" / "claim_registry.md").read_text(encoding="utf-8")

    assert "same-supervision structure-only Ridge control" in manuscript
    assert "Structural (graph) only" in manuscript
    assert "mathematical variable-dependency DAG" in manuscript
    assert "reverse-position baseline" in manuscript
    assert "windowed calibration variant" in manuscript
    assert "human audit usefulness" in manuscript
    assert "remain future" in manuscript

    assert "three independent raters" not in manuscript
    assert "small three-rater human study" not in manuscript
    assert "M_HUMAN_EVAL_INTERPRETABILITY" not in registry

    assert "M_STRUCTURE_ONLY_BASELINE" in registry
    assert "M_WINDOWED_CALIBRATION" in registry
    assert "M_GRAPH_NECESSITY_DIAGNOSTIC" in registry


def test_submission_lock_has_claim_bounded_submission_policy():
    audit = (ROOT / "paper" / "submission_lock_audit.md").read_text(encoding="utf-8")
    registry = (ROOT / "paper" / "claim_registry.md").read_text(encoding="utf-8")

    assert "submission_status: methodological_submission_possible_with_claim_boundaries" in audit
    assert "Status: **methodological_submission_possible_with_claim_boundaries**." in audit
    assert "downstream PRM training" in audit
    assert "GSM8K/HotpotQA replay" in audit
    assert "production KBS deployment" in audit
    assert "causal identification" in audit
    assert "If PRM800K stratified analysis is blocked" in registry


def test_jiis_source_claims_stay_in_structural_label_boundary():
    manuscript = (
        ROOT / "paper" / "JIIS_submission" / "source" / "manuscript.tex"
    ).read_text(encoding="utf-8").lower()

    assert "structural label extractor" in manuscript
    assert "audit-record representation contract" in manuscript
    assert "illustrative policy consumer" in manuscript
    assert "impact coverage@k" in manuscript
    assert "reachable descendants" in manuscript
    assert "life-saving first" in manuscript
    assert "controlled audit motifs" in manuscript
    assert "native wikidata structural roles fall outside the evaluation target" in manuscript
    assert "robust to arbitrary kg noise" in manuscript
    assert "causal effects were not evaluated" in manuscript
    assert "human usefulness" in manuscript
    assert "reports no evidence of human usefulness" in manuscript
    assert "production effectiveness" in manuscript


def _jiis_manuscript_text() -> str:
    return (
        ROOT / "paper" / "JIIS_submission" / "source" / "manuscript.tex"
    ).read_text(encoding="utf-8")


def _latex_section(text: str, title: str) -> str:
    start = text.index(rf"\section{{{title}}}")
    next_match = re.search(r"\\section\*?\{", text[start + 1 :])
    if not next_match:
        return text[start:]
    end = start + 1 + next_match.start()
    return text[start:end]


def test_jiis_main_text_keeps_legacy_scorer_terms_out_of_method_and_results():
    manuscript = _jiis_manuscript_text()
    method_and_results = "\n".join(
        [_latex_section(manuscript, "Method"), _latex_section(manuscript, "Results")]
    )
    forbidden = (
        r"\wstruct",
        "w_struct",
        r"w_{struct}",
        r"mathbf{w}",
        r"w_{\text",
        "SCU",
        "Ridge",
        "QP",
        "Projection",
        "Spearman",
    )

    for term in forbidden:
        assert term not in method_and_results


def test_jiis_narrative_order_prioritizes_representation_before_policy_consumption():
    manuscript = _jiis_manuscript_text()

    fidelity_idx = manuscript.index("Controlled extraction fidelity")
    policy_idx = manuscript.index("Illustrative policy consumption on controlled substrates")

    assert fidelity_idx < policy_idx
    assert "Spearman" not in manuscript
    assert "Ridge" not in manuscript
    assert "QP" not in manuscript


def test_jiis_supplementary_excludes_legacy_scorer_diagnostics():
    manuscript = _jiis_manuscript_text()
    supplementary = (
        ROOT / "paper" / "JIIS_submission" / "source" / "supplementary.tex"
    ).read_text(encoding="utf-8")

    assert r"\section{Boundary Diagnosis}" not in manuscript
    for legacy in (
        "Spearman",
        "Ridge",
        "QP",
        "SCU",
        "PRM800K",
        "WebQSP",
        "MuSiQue",
        "Failure Taxonomy",
        "Audit Cards",
    ):
        assert legacy not in supplementary
    assert supplementary.count(r"\section{Appendix") == 3


def test_active_file_scope_excludes_superseded_manuscripts_and_plan_docs():
    active = {path.relative_to(ROOT).as_posix() for path in iter_active_files(ROOT)}

    assert "paper/information_sciences_submission/final_source/manuscript.tex" in active
    assert "paper/submission_lock_audit.md" in active
    assert "paper/claim_registry.md" in active
    assert "paper/manuscript.md" not in active
    assert "paper/introduction.md" not in active
    assert "paper/related_work.md" not in active
    assert "paper_review_kbs_20260616.md" not in active
    assert not any(
        path.startswith("paper/information_sciences_submission/editorial_repair_artifacts/")
        for path in active
    )
    assert not any(path.startswith("docs/superpowers/") for path in active)
    assert not any(path.startswith(".omo/") for path in active)
    assert not any(path.startswith(".claude/worktrees/") for path in active)


def test_claim_registry_blocked_wording_column_is_boundary_language():
    text = """| Claim ID | Claim | Status | Artifact owner | Allowed wording | Blocked wording |
|---|---|---|---|---|---|
| `M_X` | Diagnostic claim. | `supported` | `artifact.json` | bounded audit wording | external generalization; PRM training improvement; deployed KBS validation |
"""

    assert scan_text("paper/claim_registry.md", text) == []


def test_active_claim_boundary_scan_is_clean():
    assert scan_active_files(ROOT) == []
