# Submission Lock Audit

Audit date: 2026-05-30  
Repository: `D:\CF`  
Branch: `main`  
HEAD: `7e9e10e39ad3c38c5db8d1e6646d08763e6876a1`  
Scope: read-only submission-readiness audit, with no experiment reruns and no source or artifact mutation.

## Verdict

Status: **not fully locked for submission**.

The repository is close to a submission-lock state for the Phase 5-7 empirical narrative. The main empirical artifacts are present, parseable, and consistent with the manuscript's central claim:

> Reflective reasoning exhibits widespread local utility, but only sparse structural necessity.

However, the submission should not be treated as locked until the blocking items below are resolved.

## Blocking Items

1. `paper/related_work.md` still contains an explicit `TODO: manual bibliography completion` line and citation placeholders such as `[REFLEXION_PLACEHOLDER]`, `[SELF_REFINE_PLACEHOLDER]`, and `[PRM_PLACEHOLDER]`.
2. `README.md` still contains a citation placeholder block. This is not necessarily a paper blocker, but it is a package-readiness blocker if the repository README is included with the submission package.
3. Git status before this audit showed 13 modified paper files:
   - `paper/abstract.md`
   - `paper/appendix.md`
   - `paper/conclusion.md`
   - `paper/experiments.md`
   - `paper/figure_inventory.md`
   - `paper/formalism.md`
   - `paper/introduction.md`
   - `paper/limitations.md`
   - `paper/methodology.md`
   - `paper/paper_outline.md`
   - `paper/related_work.md`
   - `paper/results.md`
   - `paper/terminology.md`
4. Tests were not rerun during this audit because the user requested a read-only audit. Running `pytest` may update local cache files, so the latest test state is not freshly verified in this report.
5. Git reported line-ending warnings for the modified paper files: `LF will be replaced by CRLF the next time Git touches it`. This is not an empirical blocker, but it should be normalized before a final locked submission package if exact diffs matter.

## Non-Blocking Risks

- The paper layer is currently modular Markdown rather than a single compiled manuscript. This is acceptable for drafting, but a venue submission still needs final assembly, formatting, references, and figure numbering.
- The related-work section is intentionally citation-safe, but placeholder references are not submission-ready.
- Phase 7 includes adapter notes stating that CASCADE and BYPASS node rows were reconstructed from `reflection_graph.json` where raw per-node rows were absent or incomplete. This is acceptable if reported transparently, and the current methodology/results text does this at a high level.

## Evidence Checked

### Paper files

The `paper/` directory contains:

- `abstract.md`
- `appendix.md`
- `conclusion.md`
- `experiments.md`
- `figure_inventory.md`
- `formalism.md`
- `introduction.md`
- `limitations.md`
- `methodology.md`
- `paper_outline.md`
- `related_work.md`
- `reproducibility.md`
- `results.md`
- `terminology.md`

Approximate section scale from read-only inspection:

| File | Lines | Words |
|---|---:|---:|
| `abstract.md` | 2 | 186 |
| `appendix.md` | 54 | 461 |
| `conclusion.md` | 6 | 201 |
| `experiments.md` | 22 | 619 |
| `figure_inventory.md` | 37 | 626 |
| `formalism.md` | 88 | 3303 |
| `introduction.md` | 11 | 763 |
| `limitations.md` | 9 | 325 |
| `methodology.md` | 41 | 1159 |
| `paper_outline.md` | 55 | 592 |
| `related_work.md` | 14 | 508 |
| `reproducibility.md` | 28 | 224 |
| `results.md` | 25 | 802 |
| `terminology.md` | 34 | 502 |

### Artifact parse checks

The following key artifacts were present and parseable or readable:

| Artifact | Status |
|---|---|
| `outputs/counterfactual_summary.json` | JSON parse OK |
| `outputs/structural_diagnostics.json` | JSON parse OK |
| `outputs/structural_faithfulness.json` | JSON parse OK |
| `outputs/phase6_sensitivity.json` | JSON parse OK |
| `outputs/redundancy_analysis.json` | JSON parse OK |
| `outputs/redundancy_analysis.md` | present |
| `outputs/phase6_readme.md` | present |
| `outputs/structural_diagnostics.md` | present |

### JSONL row counts

| Artifact | Non-empty rows |
|---|---:|
| `outputs/attribution_records.jsonl` | 800 |
| `outputs/necessity_scores.jsonl` | 2400 |
| `outputs/structural_node_necessity.jsonl` | 2400 |
| `outputs/structural_edge_necessity.jsonl` | 2098 |
| `outputs/structural_subgraph_necessity.jsonl` | 1618 |
| `outputs/ciu_results.jsonl` | 12 |
| `outputs/fma_scores.jsonl` | 3 |
| `outputs/reflection_traces.jsonl` | 12 |

### Figure inventory

`outputs/figures/` contains 31 PNG files. All figure files listed in `paper/figure_inventory.md` were present and non-empty during this audit.

Primary paper figures identified by the manuscript layer:

- `outputs/figures/structural_diagnostics_attribution_vs_necessity.png`
- `outputs/figures/redundancy_density_histogram.png`
- `outputs/figures/resilience_curves.png`

Supplementary Phase 6-7 figures are also present, including compensation, rerouting, bottleneck, distributedness, graph-size, node-necessity, edge-necessity, motif, compression, and structural-influence figures.

## Claim Consistency Check

The manuscript's central empirical story is consistent with stored outputs:

### Phase 5

`outputs/counterfactual_summary.json` reports:

- `num_traces`: 800
- `num_ablations`: 2400
- `mean_necessity`: 0.0636
- `mean_necessity_normalized`: 0.1217
- `faithfulness_pearson`: 0.1583
- `faithfulness_spearman`: 0.1459
- `faithfulness_rank_agreement`: 0.5767
- `redundancy_ratio`: 0.1454
- `traces_with_redundancy`: 303

### Phase 6

`outputs/structural_diagnostics.json` reports:

- `num_graphs`: 800
- `num_phase5_scores`: 2400
- `num_source_nodes`: 800
- mean zero structural necessity fraction: 0.6779

Alignment values:

| Mode | Pearson | Spearman | Zero structural necessity fraction |
|---|---:|---:|---:|
| PRUNE | 0.0753 | 0.0596 | 0.6779 |
| CASCADE | 0.0523 | 0.0512 | 0.6779 |
| BYPASS | 0.0917 | 0.0623 | 0.6779 |

These values match the paper's weak-alignment and zero-inflation narrative.

### Phase 7

`outputs/redundancy_analysis.json` reports:

- graph count: 800
- node count: 2400
- edge count: 2098
- redundancy density / average redundancy degree: 0.3842
- distributedness global index: 0.2976
- bottleneck count: 191
- bottleneck rarity: 0.9204
- PRUNE compensation mean ratio: 0.0084
- CASCADE compensation mean ratio: 0.0000
- BYPASS compensation mean ratio: 0.0152
- mean rerouting breadth: 0.0100
- mean rerouting depth: 0.0100
- mean rerouting entropy: 0.0000

Resilience AUCs:

| Removal order | AUC |
|---|---:|
| sequential | 0.4840 |
| deterministic random | 0.5098 |
| attribution-first | 0.4761 |
| necessity-first | 0.1488 |

These values support the manuscript's refined conclusion: moderate redundancy exists, but compensation and distributedness are weak, and sparse bottlenecks carry the stronger topology-sensitive signal.

## Terminology and Framing Audit

The paper layer generally follows the repository's required framing:

- Uses operational/proxy language for `attribution_score`, `structural_necessity`, `compensation_ratio`, and `distributedness_index`.
- Separates local utility from topology-sensitive necessity.
- Explicitly states no causal identifiability in `paper/formalism.md`.
- Avoids presenting Phase 7 compensation as intentional or agentic adaptation.
- Treats process supervision as future direction, not as a completed PRM contribution.

Important caution:

- Some legacy phrasing around "counterfactual" and "intervention-based" remains, but the current formalism constrains it as operational trace perturbation rather than formal causal identification.

## Reproducibility Audit

`paper/reproducibility.md` identifies these commands:

```powershell
python -m pytest -q
python scripts/run_structural_diagnostics.py
python scripts/run_redundancy_analysis.py
python scripts/run_counterfactual_attribution.py
```

This audit did not execute them. The stored artifact set is internally consistent, but a final lock should include a fresh test/run verification if file mutation is permitted.

## Lock Conditions

Recommended conditions before declaring submission lock:

1. Replace all bibliography placeholders in `paper/related_work.md`.
2. Decide whether `README.md` citation placeholders are allowed in the submitted repository/package; if not, replace them too.
3. Normalize or accept the CRLF/LF behavior for all modified paper files.
4. Stage or otherwise freeze the 13 modified paper files after final review.
5. If permitted, run `python -m pytest -q` and record the result.
6. If permitted, rerun or dry-verify Phase 6/7 reproduction commands and record that regenerated values match stored artifacts.
7. Assemble the final manuscript format with numbered figures, final citations, and venue-specific bibliography.

## Final Lock Recommendation

Do **not** mark the manuscript as fully locked today. Mark it as:

> Empirical evidence locked; submission package pending bibliography, git freeze, and final verification.

This is a strong near-lock state: the core stored results are coherent and the paper's central claim is appropriately conservative. The remaining blockers are packaging, citation, and final verification issues rather than empirical-result inconsistencies.
