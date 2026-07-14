# JIIS Frozen Reproduction Archive

This manifest describes `submission_package/reproducibility_archive.zip`, the
frozen input-and-code bundle for the controlled Wikidata maintenance experiment.

## Evidence boundary

The archive reproduces the controlled Wikidata substrate and the reported audit
calculations. The controlled motifs are not native Wikidata role annotations,
and the archive does not add human-audit or production-deployment evidence.

## Frozen inputs

- `data/wdqs_cache.json`: exact WDQS response cache used by the v2 run.
- `data/triples.csv` and `data/triples.jsonl`: frozen extracted triples.
- `data/raw_graph.graphml`: frozen 2,000-node, 6,039-edge substrate.
- `data/audit_overlay.graphml`: directed acyclic audit overlay.
- `traces/motif_manifest.json`: controlled motif manifest.
- `cases/revision_cases.json`: verified revision-difference cases.

The expected WDQS cache SHA-256 is
`9c9b9aec985e87f6d098aa4dd7cbc06875638a7a6298ea61a18c9215668d1cfe`.
The runner prefers the frozen cache and validates this hash, so the reported
substrate can be reproduced without querying the live SPARQL endpoint.

## Code and results

The archive includes the v2 configuration, the CLI entry point, the relevant
`fma` evaluation/graph/visualization modules, locked metrics, revision cases,
and `SHA256SUMS.txt` for every archived file. From the repository root, run:

```powershell
$env:PYTHONPATH = "src"
python scripts/run_wikidata_scientist_audit.py --config configs/wikidata_scientist_audit_v2.yaml
```

The Countries-KG support files additionally include the native binary
Undirected Articulation Point control on direction-collapsed traces. This
baseline is not matched to the gold positive count and targets bottleneck F1
only; it does not alter the cached SC-FMA fields or policy-consumption results.

Python dependencies and package metadata are recorded in `pyproject.toml` and
`requirements.txt` inside the archive.

## Long-term release

The archive accompanies the review submission. Upon acceptance, the same
frozen bundle will be deposited in Zenodo with a persistent DOI and mirrored in
a public GitHub repository. The final article will record the DOI and Git commit.
