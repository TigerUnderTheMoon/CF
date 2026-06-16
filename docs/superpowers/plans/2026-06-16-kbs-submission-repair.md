# KBS Submission Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Increase Knowledge-Based Systems acceptance probability by adding a bounded real-data audit-prioritization analysis, reframing SC-FMA around its supported PRM800K evidence boundary, and making the submission package reviewer-proof without upgrading failed routes.

**Architecture:** Keep PRM800K v3.6/v3.8 as the only positive real-data evidence surface. Add a CPU-only, no-API report generator that reuses the locked PRM800K split and existing SC-FMA variant code to produce step-audit prioritization metrics. Then revise the KBS manuscript to center "auditable verification-step weighting" and move QP from flagship claim to controlled-synthetic variant.

**Tech Stack:** Python 3.11, pytest, NumPy/SciPy, existing `scripts/run_scfma_variants_prm800k.py`, LaTeX/latexmk, existing KBS package verifier.

---

### Task 1: Add PRM800K Audit-Prioritization Evidence

**Files:**
- Create: `src/fma/eval/prm800k_audit_prioritization.py`
- Create: `scripts/run_prm800k_audit_prioritization.py`
- Create: `tests/test_prm800k_audit_prioritization.py`
- Output: `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json`
- Output: `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md`

- [ ] **Step 1: Write metric unit tests**

Test these exact behaviors in `tests/test_prm800k_audit_prioritization.py`:

```python
from fma.eval.prm800k_audit_prioritization import (
    label_mass_at_budget,
    max_label_hit_at_budget,
    ndcg_at_budget,
)


def test_max_label_hit_at_budget_selects_highest_label():
    scores = [0.1, 0.9, 0.2]
    labels = [0.0, 1.0, 0.5]
    assert max_label_hit_at_budget(scores, labels, keep_fraction=1 / 3) == 1.0


def test_max_label_hit_at_budget_detects_miss():
    scores = [0.9, 0.1, 0.2]
    labels = [0.0, 1.0, 0.5]
    assert max_label_hit_at_budget(scores, labels, keep_fraction=1 / 3) == 0.0


def test_label_mass_at_budget_is_normalized():
    scores = [0.9, 0.2, 0.1]
    labels = [0.5, 1.0, 0.5]
    assert label_mass_at_budget(scores, labels, keep_fraction=1 / 3) == 0.25


def test_ndcg_at_budget_is_one_for_perfect_order():
    scores = [0.9, 0.7, 0.1]
    labels = [1.0, 0.5, 0.0]
    assert ndcg_at_budget(scores, labels, keep_fraction=2 / 3) == 1.0
```

Run: `python -m pytest tests/test_prm800k_audit_prioritization.py -q`
Expected before implementation: import failure.

- [ ] **Step 2: Implement metric helpers**

Create `src/fma/eval/prm800k_audit_prioritization.py` with pure functions:

```python
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MethodAuditSummary:
    method: str
    mean_top1_hit: float
    mean_mass_at_25: float
    mean_mass_at_50: float
    mean_ndcg_at_25: float
    mean_ndcg_at_50: float


def keep_count(n_steps: int, keep_fraction: float) -> int:
    if n_steps <= 0:
        return 0
    return max(1, min(n_steps, int(math.ceil(n_steps * keep_fraction))))


def selected_indices(scores: Sequence[float], keep_fraction: float) -> list[int]:
    scores_array = np.asarray(scores, dtype=float)
    k = keep_count(len(scores_array), keep_fraction)
    if k == 0:
        return []
    order = np.argsort(-scores_array, kind="mergesort")
    return [int(i) for i in order[:k]]


def max_label_hit_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    if labels_array.size == 0:
        return 0.0
    selected = selected_indices(scores, keep_fraction)
    max_label = float(np.max(labels_array))
    return 1.0 if any(float(labels_array[i]) == max_label for i in selected) else 0.0


def label_mass_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    total = float(np.sum(labels_array))
    if total <= 0.0:
        return 0.0
    selected = selected_indices(scores, keep_fraction)
    return float(np.sum(labels_array[selected]) / total)


def ndcg_at_budget(
    scores: Sequence[float],
    labels: Sequence[float],
    *,
    keep_fraction: float,
) -> float:
    labels_array = np.asarray(labels, dtype=float)
    selected = selected_indices(scores, keep_fraction)
    if not selected:
        return 0.0
    gains = np.power(2.0, labels_array[selected]) - 1.0
    discounts = 1.0 / np.log2(np.arange(2, len(selected) + 2))
    dcg = float(np.sum(gains * discounts))
    ideal = np.sort(labels_array)[::-1][: len(selected)]
    ideal_gains = np.power(2.0, ideal) - 1.0
    ideal_dcg = float(np.sum(ideal_gains * discounts))
    return 0.0 if ideal_dcg <= 0.0 else dcg / ideal_dcg


def summarize_audit_prioritization(
    rows: Sequence[Mapping[str, object]],
    *,
    methods: Sequence[str],
) -> list[MethodAuditSummary]:
    summaries: list[MethodAuditSummary] = []
    for method in methods:
        top1_hits: list[float] = []
        mass25: list[float] = []
        mass50: list[float] = []
        ndcg25: list[float] = []
        ndcg50: list[float] = []
        for row in rows:
            labels = row["labels"]
            scores_by_method = row["scores_by_method"]
            if not isinstance(scores_by_method, Mapping) or method not in scores_by_method:
                continue
            scores = scores_by_method[method]
            top1_hits.append(max_label_hit_at_budget(scores, labels, keep_fraction=1.0 / len(labels)))
            mass25.append(label_mass_at_budget(scores, labels, keep_fraction=0.25))
            mass50.append(label_mass_at_budget(scores, labels, keep_fraction=0.50))
            ndcg25.append(ndcg_at_budget(scores, labels, keep_fraction=0.25))
            ndcg50.append(ndcg_at_budget(scores, labels, keep_fraction=0.50))
        summaries.append(
            MethodAuditSummary(
                method=method,
                mean_top1_hit=float(np.mean(top1_hits)) if top1_hits else 0.0,
                mean_mass_at_25=float(np.mean(mass25)) if mass25 else 0.0,
                mean_mass_at_50=float(np.mean(mass50)) if mass50 else 0.0,
                mean_ndcg_at_25=float(np.mean(ndcg25)) if ndcg25 else 0.0,
                mean_ndcg_at_50=float(np.mean(ndcg50)) if ndcg50 else 0.0,
            )
        )
    return summaries
```

Run: `python -m pytest tests/test_prm800k_audit_prioritization.py -q`
Expected: pass.

- [ ] **Step 3: Add the report runner**

Create `scripts/run_prm800k_audit_prioritization.py`. Reuse helpers from `scripts/run_scfma_variants_prm800k.py` to load the same hash-stratified PRM800K split and compute scores for:

`w_struct`, `scfma_ridge`, `scfma_qp`, `scfma_projection`, `raw_local_utility`, `relative_position`, `span_length`, `random`, and `frozen_prm_prefix_score` when `outputs/real_task_v3_8_prm_locked_scoring/locked_prm_scores.jsonl` contains the sample.

Report fields must include:

```json
{
  "claim_boundary": "real_prm800k_audit_prioritization_only",
  "claim_permissions": {
    "audit_prioritization_context": true,
    "downstream_prm_training": false,
    "gsm8k_hotpotqa_replay_validation": false,
    "external_generalization": false
  },
  "n_samples": 4417,
  "n_steps": 34219,
  "methods": [...]
}
```

The markdown summary must state that this is an offline audit-prioritization use case on the PRM800K locked split, not PRM training, not filtering superiority, and not GSM8K/HotpotQA replay evidence.

Run: `python scripts/run_prm800k_audit_prioritization.py --bootstrap-samples 1000`
Expected: JSON and Markdown written under `outputs/real_task_v3_6_prm800k_hash/`.

- [ ] **Step 4: Add report contract tests**

Extend `tests/test_prm800k_audit_prioritization.py` with a tiny synthetic rows fixture and assert:

```python
def test_summary_contains_all_methods():
    rows = [
        {
            "labels": [0.0, 1.0, 0.5],
            "scores_by_method": {
                "w_struct": [0.1, 0.9, 0.2],
                "raw_local_utility": [0.9, 0.1, 0.2],
            },
        }
    ]
    summaries = summarize_audit_prioritization(rows, methods=["w_struct", "raw_local_utility"])
    assert [s.method for s in summaries] == ["w_struct", "raw_local_utility"]
    assert summaries[0].mean_top1_hit == 1.0
    assert summaries[1].mean_top1_hit == 0.0
```

Run: `python -m pytest tests/test_prm800k_audit_prioritization.py tests/test_ranking.py -q`
Expected: pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/fma/eval/prm800k_audit_prioritization.py scripts/run_prm800k_audit_prioritization.py tests/test_prm800k_audit_prioritization.py outputs/real_task_v3_6_prm800k_hash/audit_prioritization_report.json outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md
git commit -m "feat: add prm800k audit prioritization report"
```

---

### Task 2: Rewrite the KBS Manuscript Around Supported Claims

**Files:**
- Modify: `paper/kbs_submission/main.tex`
- Modify: `paper/kbs_submission/cover_letter.md`
- Modify: `paper/kbs_submission/supplementary_materials.md`
- Later sync: `paper/kbs_submission/final_source/manuscript.tex`

- [ ] **Step 1: Reframe abstract and contribution list**

In `paper/kbs_submission/main.tex`, keep the current title but rewrite the abstract around these fixed claims:

- SC-FMA is an auditable verification-step weighting methodology.
- QP is strongest only on controlled synthetic proxy labels.
- PRM800K real-data evidence is led by `w_struct`; Ridge is the closest SC-FMA approximation.
- The new audit-prioritization report is an offline PRM800K use-case context only.
- GSM8K/HotpotQA replay, downstream filtering, PRM training, and external generalization remain unsupported.

Do not use: `validated downstream`, `PRM training improvement`, `external generalization`, `deployed KBS workflow`, `true causal effect`, `average treatment effect`.

- [ ] **Step 2: Add a reviewer-facing evidence table**

Replace the current evidence-route table with one that has columns:

`Evidence surface`, `Status`, `Allowed claim`, `Forbidden upgrade`.

Rows:

- Synthetic controlled benchmark: method calibration only.
- PRM800K v3.6 locked step-label ranking: `w_struct` real step-ranking only.
- PRM800K v3.8 frozen PRM baseline: in-distribution context only.
- PRM800K audit prioritization: offline audit-prioritization context only.
- Stage 2 holdout: small, stratum-dependent diagnostic.
- GSM8K/HotpotQA replay and filtering: failed or blocked.
- Ontology-aware edge pilot: fixture-level diagnostic KBS extension path only.

- [ ] **Step 3: Add a baseline/fairness ledger table**

Add a main-text table after the Results overview with columns:

`Comparator`, `Role`, `Data/split`, `Fairness status`, `Main use`.

Rows:

- `raw_local_utility`: direct ablation, same PRM800K locked split, pass.
- `span_length`: trivial control, same split, pass.
- `relative_position`: trivial control, same split, pass.
- `random`: sanity control, same split, pass.
- `Frozen PRM prefix score`: in-distribution context, same PRM800K locked split, overlap-limited.
- `SC-FMA Ridge`: recommended approximation, same split, pass.
- `SC-FMA QP`: controlled-synthetic strongest variant, PRM800K downgraded.
- `Math-Shepherd / public PRM literature`: citation-only unless clean non-overlap and protocol-compatible scoring are available.
- `ProcessBench`: citation-only benchmark context unless a future dedicated route is preregistered.

- [ ] **Step 4: Add audit-prioritization results**

Use `outputs/real_task_v3_6_prm800k_hash/audit_prioritization_summary.md` as the source. Add one compact table with the top 4-6 methods and metrics:

`Top-1 max-label hit`, `Label mass@25%`, `NDCG@25%`, `Claim permission`.

If `w_struct` and/or `SC-FMA Ridge` do not beat `relative_position` and `raw_local_utility`, state the negative result and do not call it an improvement. If they do beat those controls, phrase the result as:

`The same locked PRM800K evidence can be read operationally as audit-prioritization context: the method better concentrates high-rated process steps under a fixed review budget. This remains a step-ranking use case, not downstream PRM training or task replay validation.`

- [ ] **Step 5: Strengthen KBS fit without overclaiming**

Move the KBS discussion earlier or expand it into a short subsection before Results. Use this structure:

- Verification-step weighting as a knowledge-structured decision-support problem.
- Graph dependencies, redundancy, and bottlenecks as KBS-relevant structure.
- Ontology-aware edge pilot as a fixture-level interface feasibility check only.
- Future deployed KBS validation requires a real rule engine, ontology reasoner, or KG query workflow.

- [ ] **Step 6: Update cover letter**

Rewrite `paper/kbs_submission/cover_letter.md` to be less defensive:

- Lead with KBS fit and auditable verification-step weighting.
- Mention PRM800K locked step-label evidence and offline audit-prioritization context.
- State claim boundaries in one sentence only.
- Do not spend a full paragraph on failed routes.

- [ ] **Step 7: Update supplementary map**

Add the new audit-prioritization report to `paper/kbs_submission/supplementary_materials.md` as a supplementary data item. Mark it `audit-prioritization context only`.

- [ ] **Step 8: Run claim-boundary scans**

Run:

```powershell
rg -n "validated downstream|PRM training improvement|external generalization|deployed KBS workflow|true causal effect|average treatment effect|globally identifiable causal" paper\kbs_submission
```

Expected: no matches except explicit forbidden-word scan instructions or negative statements that say the claim is not made.

- [ ] **Step 9: Commit Task 2**

```powershell
git add paper/kbs_submission/main.tex paper/kbs_submission/cover_letter.md paper/kbs_submission/supplementary_materials.md
git commit -m "docs: reframe kbs manuscript around supported evidence"
```

---

### Task 3: Refresh Final Package and Verification Artifacts

**Files:**
- Modify: `paper/kbs_submission/final_source/manuscript.tex`
- Modify: `paper/kbs_submission/final_submission_manifest.md`
- Modify: `paper/kbs_submission/format_checklist.md`
- Update generated package files under `paper/kbs_submission/final_package/`

- [ ] **Step 1: Sync final source**

Copy the revised manuscript body from `paper/kbs_submission/main.tex` into `paper/kbs_submission/final_source/manuscript.tex`, preserving final-source author metadata, bibliography path, figure paths, and CAS class settings.

- [ ] **Step 2: Rebuild PDFs**

Run from `paper/kbs_submission/final_source`:

```powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build_manuscript manuscript.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build_supplementary supplementary.tex
```

Then copy:

- `build_manuscript/manuscript.pdf` to `paper/kbs_submission/final_package/manuscript.pdf`
- `build_supplementary/supplementary.pdf` to `paper/kbs_submission/final_package/supplementary.pdf`

Rebuild `latex_source.zip` from final source files, CAS files, bibliography, and `figures/`, excluding auxiliary files.

- [ ] **Step 3: Update package manifest and checklist**

Update `final_submission_manifest.md` and `format_checklist.md` with:

- new page counts,
- new audit-prioritization supplementary item,
- current claim boundary,
- DOCX visual rendering status unchanged unless LibreOffice is installed and checked.

- [ ] **Step 4: Verify package**

Run:

```powershell
python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission\final_package --require-author-metadata --require-pdf-text
python -m pytest tests/test_kbs_submission_package_verifier.py tests/test_prm800k_audit_prioritization.py tests/test_ranking.py -q
```

Expected:

- verifier prints `KBS final submission package check passed`,
- pytest passes,
- no forbidden positive-claim wording appears in `pdftotext` output.

- [ ] **Step 5: Optional visual QA**

If Poppler render tools are available, render first and last pages of `manuscript.pdf` and `supplementary.pdf` to PNG contact sheets. Check title, author block, tables, figures, and no obvious clipping. If LibreOffice is still unavailable, keep DOCX visual rendering marked blocked but structurally checked.

- [ ] **Step 6: Commit Task 3**

```powershell
git add paper/kbs_submission/final_source/manuscript.tex paper/kbs_submission/final_submission_manifest.md paper/kbs_submission/format_checklist.md paper/kbs_submission/final_package paper/kbs_submission/final_source
git commit -m "chore: refresh kbs final submission package"
```

---

### Acceptance Criteria

- The manuscript no longer presents QP as the real-data winner.
- The primary real-data claim remains `w_struct` PRM800K step-label ranking, with Ridge as the closest SC-FMA approximation.
- A bounded PRM800K audit-prioritization analysis exists and is explicitly context-only.
- The paper contains a baseline/fairness ledger that explains why frozen PRM is context-only and why public PRM/ProcessBench comparisons are not upgraded.
- KBS fit is stated as knowledge-structured verification-step weighting, not deployed KBS validation.
- Data availability is more specific if public artifacts are available; otherwise it remains honest and does not imply an archive that does not exist.
- Final package verifier and focused tests pass.

### Assumptions and Defaults

- Default target venue remains Knowledge-Based Systems.
- No online API reruns are part of this repair plan.
- Do not implement conditional replacement, matching, or doubly robust estimation in this repair; they remain future-work/planned components.
- Do not upgrade GSM8K/HotpotQA, v2/v2.1/v2.2/v3/v3.1, downstream filtering, or PRM-training claims.
- If the audit-prioritization metrics are negative or dominated by simple baselines, report that as a limitation and omit any use-case improvement wording.
