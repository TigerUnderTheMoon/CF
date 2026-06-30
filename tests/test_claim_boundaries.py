from __future__ import annotations

from pathlib import Path

from scripts.check_claim_boundaries import (
    ACTIVE_KBS_DOIS,
    iter_active_files,
    scan_active_files,
    scan_text,
    strip_fenced_code,
)


ROOT = Path(__file__).resolve().parents[1]


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


def test_kbs_source_contains_ciu_granularity_and_adapter_contract():
    manuscript = (ROOT / "paper" / "kbs_submission" / "final_source" / "manuscript.tex").read_text(
        encoding="utf-8"
    )
    references = (ROOT / "paper" / "kbs_submission" / "final_source" / "references.bib").read_text(
        encoding="utf-8"
    )

    assert "coarse trace-level utility anchor" in manuscript
    assert "local functional attributions rather than causal effect estimates" in manuscript
    assert "does not validate a deployed KBS workflow" in manuscript
    assert "fixture-level typed-edge construction only; no deployed workflow validation" in manuscript
    assert "per-step counterfactual outcome differences" not in manuscript
    assert "all interventions are structure-preserving" not in manuscript

    for doi in ACTIVE_KBS_DOIS:
        assert doi in references


def test_kbs_source_preserves_main_text_diagnostic_context():
    manuscript = (ROOT / "paper" / "kbs_submission" / "final_source" / "manuscript.tex").read_text(
        encoding="utf-8"
    )

    stress_caption = "SCU component contribution on a structural stress-test benchmark"
    kg_stage_section = r"\subsection{Countries-KG Typed-Edge Stage}"

    assert stress_caption in manuscript
    assert kg_stage_section in manuscript
    assert "Evidence Ladder" in manuscript


def test_kbs_source_explicitly_bounds_hyperparameter_and_graph_ablation_claims():
    manuscript = (ROOT / "paper" / "kbs_submission" / "final_source" / "manuscript.tex").read_text(
        encoding="utf-8"
    )
    supplementary = (
        ROOT / "paper" / "kbs_submission" / "final_source" / "supplementary.tex"
    ).read_text(encoding="utf-8")
    alpha_beta_grid = (
        ROOT
        / "outputs"
        / "reviewer_v2_experiments"
        / "scu_hyperparameter_sensitivity"
        / "alpha_beta_grid.csv"
    ).read_text(encoding="utf-8")

    assert "gamma/delta and alpha/beta QP sensitivity grids" in manuscript
    assert "tab:supp-alpha-beta-sensitivity" in manuscript
    assert "TF-IDF topical default (0.0515) did not outperform temporal-only edges (0.0596)" in manuscript
    assert "embedding backend (0.0615)" in manuscript

    assert r"\label{tab:supp-alpha-beta-sensitivity}" in supplementary
    assert "0.5,0.0,0.639275217471432" in alpha_beta_grid
    assert "2.0,1.0,0.5572138842322" in alpha_beta_grid
    assert r"outputs/reviewer\_v2\_experiments/scu\_hyperparameter\_sensitivity/scu\_hyperparameter\_sensitivity.json" in supplementary
    assert r"outputs/reviewer\_v2\_experiments/scu\_hyperparameter\_sensitivity/scu\_hyperparameter\_sensitivity.md" in supplementary
    assert r"outputs/reviewer\_v2\_experiments/scu\_hyperparameter\_sensitivity/alpha\_beta\_grid.csv" in supplementary
    assert r"outputs/reviewer\_v2\_experiments/scu\_hyperparameter\_sensitivity/gamma\_delta\_grid.csv" in supplementary


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


def test_active_file_scope_excludes_superseded_manuscripts_and_plan_docs():
    active = {path.relative_to(ROOT).as_posix() for path in iter_active_files(ROOT)}

    assert "paper/kbs_submission/final_source/manuscript.tex" in active
    assert "paper/submission_lock_audit.md" in active
    assert "paper/claim_registry.md" in active
    assert "paper/manuscript.md" not in active
    assert "paper/introduction.md" not in active
    assert "paper/related_work.md" not in active
    assert "paper_review_kbs_20260616.md" not in active
    assert not any(
        path.startswith("paper/kbs_submission/editorial_repair_artifacts/")
        for path in active
    )
    assert not any(path.startswith("docs/superpowers/") for path in active)
    assert not any(path.startswith(".omo/") for path in active)


def test_claim_registry_blocked_wording_column_is_boundary_language():
    text = """| Claim ID | Claim | Status | Artifact owner | Allowed wording | Blocked wording |
|---|---|---|---|---|---|
| `M_X` | Diagnostic claim. | `supported` | `artifact.json` | bounded audit wording | external generalization; PRM training improvement; deployed KBS validation |
"""

    assert scan_text("paper/claim_registry.md", text) == []


def test_active_claim_boundary_scan_is_clean():
    assert scan_active_files(ROOT) == []
