# Reproducibility

The repository is designed for deterministic, local reproduction. The empirical core uses stored traces and generated outputs under `data/` and `outputs/`; no external API calls are required for Phase 5-7 reproduction.

## Environment Assumptions

Use Python from the local environment with dependencies in `requirements.txt`: `torch`, `transformers`, `datasets`, `peft`, `trl`, `accelerate`, `pandas`, `numpy`, `matplotlib`, `scikit-learn`, `pydantic`, and `jsonlines`. Plotting scripts set matplotlib to the non-interactive `Agg` backend.

## Deterministic Guarantees

The synthetic benchmark records generation configuration with seed 42. Phase 5 runners use deterministic ablation strategies. Phase 6 graph construction and structural interventions are deterministic over stored traces. Phase 7 deterministic random removal uses stable node-id hashing rather than runtime randomness.

## Dataset Versioning and Governance

Dataset provenance is treated as part of the reproducibility contract. Any future external dataset materialization should record dataset name, config, split, source index, revision or commit identifier, and access date. This follows the practical model used by Hugging Face Datasets, where dataset loading can be pinned to a specific revision, and by dataset-documentation work that treats corpus construction choices as part of the research artifact.

Real-task manifest and readiness blockages are therefore retained as diagnostic evidence. Their findings show that split-level consumption, dataset-aware deduplication keys, and marginal contribution reporting are required before fresh validation can be claimed. Governance diagnostic reports are supplied as supplementary material so exclusion logic can be inspected without rerunning any API, replay, or scoring stage.

## Commands

Run the test suite:

```powershell
python -m pytest -q
```

Regenerate the structural diagnostics:

```powershell
python scripts/run_structural_diagnostics.py
```

Regenerate the redundancy and compensation analysis:

```powershell
python scripts/run_redundancy_analysis.py
```

Optional Phase 5 regeneration:

```powershell
python scripts/run_counterfactual_attribution.py
```

## Expected Outputs

Phase 5 should produce `outputs/necessity_scores.jsonl`, `outputs/counterfactual_ablation_results.jsonl`, `outputs/faithfulness_report.json`, `outputs/redundancy_report.json`, `outputs/minimal_subset_report.json`, `outputs/counterfactual_summary.json`, and Phase 5 figures.

Phase 6 should produce `outputs/structural_diagnostics.json`, `outputs/structural_diagnostics.md`, `outputs/reflection_graph.json`, structural necessity JSONL files, `outputs/phase6_sensitivity.json`, and structural figures.

Phase 7 should produce `outputs/redundancy_analysis.json`, `outputs/redundancy_analysis.md`, `outputs/figures/compensation_distribution.png`, `outputs/figures/rerouting_entropy_vs_attribution.png`, `outputs/figures/redundancy_density_histogram.png`, `outputs/figures/bottleneck_examples.png`, `outputs/figures/resilience_curves.png`, and `outputs/figures/distributedness_distribution.png`.

Empirical observations should be read from the regenerated artifacts. Structural interpretations should remain tied to those artifacts. Possible interpretation beyond the deterministic benchmark should be marked as future direction.
