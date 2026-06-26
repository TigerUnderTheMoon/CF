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

    assert "trace-level coarse utility anchor" in manuscript
    assert "does not prove that each step has an independent outcome-grounded CIU" in manuscript
    assert "validated_kbs_workflow=false" in manuscript
    assert "per-step counterfactual outcome differences" not in manuscript
    assert "all interventions are structure-preserving" not in manuscript

    for doi in ACTIVE_KBS_DOIS:
        assert doi in references


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
