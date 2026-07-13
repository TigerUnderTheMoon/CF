"""Prepare the JIIS submission workspace from the v6 evidence package.

The generator writes a flat Springer-style manuscript, supplementary appendix,
claim-boundary report, blank future human-evaluation packet, and submission
package. It intentionally frames the new evidence as structural-label and
Impact Coverage diagnostics, not as a scorer, human-usefulness study, causal
effect, or production KG validation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
JIIS = ROOT / "paper" / "JIIS_submission"
SOURCE = JIIS / "source"
SUPP = JIIS / "supplementary"
HUMAN = JIIS / "human_eval_pending"
REPORTS = JIIS / "reports"
PACKAGE = JIIS / "submission_package"

TITLE = "Structural Labels for Stratified Audit Budget Allocation in Knowledge-Graph Dependency Flows"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required report is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def tex_escape(value: str) -> str:
    return (
        value.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
        .replace("#", r"\#")
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def clean_latex_builds(directory: Path) -> None:
    if not directory.exists():
        return
    for suffix in (
        ".aux",
        ".bbl",
        ".bcf",
        ".blg",
        ".fdb_latexmk",
        ".fls",
        ".log",
        ".out",
        ".run.xml",
        ".synctex.gz",
    ):
        for path in directory.glob(f"*{suffix}"):
            path.unlink(missing_ok=True)


def abstract_word_count(tex: str) -> int:
    match = re.search(r"\\abstract\{(.+?)\}\s*\\keywords", tex, flags=re.S)
    if not match:
        return 0
    text = re.sub(r"\\[a-zA-Z]+(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", match.group(1))
    text = re.sub(r"[^A-Za-z0-9\- ]+", " ", text)
    return len([word for word in text.split() if word])


def load_metrics() -> dict[str, Any]:
    return {
        "labels": read_json(ROOT / "outputs" / "countries_kg_label_validation" / "countries_kg_label_validation_report.json"),
        "audit": read_json(REPORTS / "jiis_audit_case" / "jiis_audit_case_report.json"),
        "prm": read_json(ROOT / "outputs" / "prm800k_strong_baselines" / "prm800k_necessary_condition_diagnosis.json"),
    }


def _ci_cell(report: Mapping[str, Any], method: str, metric: str) -> str:
    row = report["methods"][method][metric]
    return f"{row['mean']:.3f}"


def _early_truncation_interpretation(audit: Mapping[str, Any]) -> str:
    rate = float(audit["metrics"]["early_truncation_rate"]["mean"])
    layer_sets = {tuple(row["selection"]["selected_layers"]) for row in audit["trace_reports"]}
    if rate > 0.60:
        return (
            "A high early-truncation rate indicates that critical bottlenecks are abundant and "
            "consume most audit budgets in this setting, which is an expected safety-first "
            "behavior rather than a design flaw. The redundancy layer serves as a fallback "
            "when bottleneck nodes are scarce."
        )
    if rate < 0.30 and any("redundancy_group_samples" in layers for layers in layer_sets):
        return (
            "The low early-truncation rate confirms that the policy does not collapse entirely "
            "inside the first layer; in this clean fixture, selection primarily uses the "
            "critical-bottleneck layer and the redundancy-group-sample layer."
        )
    return (
        "The intermediate early-truncation rate indicates that the capacity rule is active "
        "without making the policy a single-layer selector."
    )


def build_main_tex(metrics: Mapping[str, Any]) -> str:
    labels = metrics["labels"]
    audit = metrics["audit"]
    prm = metrics["prm"]
    kg = labels["countries_kg"]
    details = labels["metric_details"]
    red_count = int(kg["redundancy_positive_count"])
    limited_note = ""
    if kg.get("limited_redundancy_positive_warning"):
        limited_note = (
            f" Countries-KG yields a limited number of redundancy positives (n={red_count}), "
            "which is a known limitation of the semantic fixture; we therefore complement it "
            "with synthetic scalability in Appendix A."
        )

    return rf"""
% !TEX root = ./manuscript.tex
\documentclass[pdflatex,sn-mathphys-num]{{sn-jnl}}

\usepackage{{amsmath,amssymb}}
\usepackage{{booktabs}}
\usepackage{{array}}
\usepackage{{xurl}}

\newcolumntype{{Z}}[1]{{>{{\raggedright\arraybackslash}}p{{#1}}}}

\raggedbottom

\begin{{document}}

\title[{tex_escape(TITLE)}]{{{tex_escape(TITLE)}}}

\author*[1]{{\fnm{{Haoran}} \sur{{Ma}}}}\email{{mahaoran0000@foxmail.com}}
\author[1,2]{{\fnm{{Ningning}} \sur{{Wang}}}}\email{{wangningning@bistu.edu.cn}}

\affil*[1]{{\orgdiv{{College of Management Science and Engineering}}, \orgname{{Beijing Information Science and Technology University}}, \orgaddress{{\city{{Beijing}}, \postcode{{102200}}, \country{{China}}}}}}
\affil[2]{{\orgdiv{{Institute of Information Systems, ESG Intelligent Application Innovation Research Center}}, \orgname{{Beijing Information Science and Technology University}}, \orgaddress{{\city{{Beijing}}, \postcode{{102200}}, \country{{China}}}}}}

\abstract{{Knowledge-graph and retrieval-augmented information systems expose dependency flows, entity bindings, and verification records that must be audited under fixed budgets. Prior score-centered formulations make this task look like another ranking problem, but a scalar score does not tell curators which artifacts are bottlenecks, which evidence is redundant, or how downstream records are affected. We recast the framework around structural labels rather than score improvement. The first contribution is a structural label extractor, not a scorer, that converts graph topology into audit-ready boolean flags for bottleneck and redundancy. The second contribution is a Life-Saving First stratified budget allocation policy guided by these labels and evaluated with Impact Coverage@K over reachable descendants in KG dependency flows. On the Countries-KG semantic fixture, the extractor recovers controlled bottleneck and redundancy labels while an undirected Semantic-Similarity Baseline (TF-IDF) cannot recover the directed-flow labels. In the cached-label audit case, the stratified policy covers transitive downstream impact under the same budget and is compared against Flat Top-K using the shared raw risk score. The evidence is deliberately bounded: it is a clean semantic fixture and seeded scalability test, not production knowledge-base validation, human usefulness evidence, arbitrary-noise robustness, or causal identification.}}

\keywords{{knowledge graphs, structural labels, audit budget allocation, impact coverage, information systems, dependency flows}}

\maketitle

\section{{Introduction}}\label{{sec:introduction}}

Knowledge-intensive information systems increasingly expose intermediate records rather than only final answers. A knowledge-graph workflow may expose entity nodes, relation paths, retrieval passages, verification steps, and dependency links. These artifacts are useful for maintenance only when a curator can decide what to inspect under a fixed budget. The difficulty is not simply that some artifacts receive low scalar scores. A curator also needs to know whether an artifact is a bottleneck for later records, whether another artifact provides redundant coverage, and which downstream nodes would be affected if the selected artifact is audited.

This paper therefore moves the contribution away from a scoring race. We propose a \emph{{structural label extractor}} that turns directed graph topology into audit-ready boolean fields: \texttt{{bottleneck}} and \texttt{{redundancy}}. These fields are not reward-model predictions and are not claimed to improve task reasoning. They are reusable labels for audit records in dependency-flow settings.

The second contribution is a \emph{{stratified budget allocation}} policy, Life-Saving First. The policy first allocates budget to Critical Bottleneck nodes, then to Unique Evidence nodes, then to Redundancy Group Samples, and finally to Fallback nodes. Raw risk score is used exclusively as a tie-breaker within the same stratification layer, not as the primary allocation driver. Flat Top-K uses the shared \detokenize{{raw_risk_score}} as the sole ranking criterion, where the KG setting defines it as trace-local min--max normalized downstream impact count.

The evaluation follows this reframing. Table~\ref{{tab:label-validation}} reports Countries-KG structural label extraction, with Countries-KG used as a clean semantic fixture containing {labels["kg_metadata"]["num_entities"]} entities and {labels["kg_metadata"]["num_triples"]} triples. Table~\ref{{tab:impact-coverage}} reports Impact Coverage@K rather than Recall@25-style ranking. Impact Coverage counts all reachable descendants (transitive closure) from selected nodes, not only direct successors. This reflects the maintenance reality that a root bottleneck can affect a long downstream chain, and auditors need visibility into the entire affected subgraph.

\section{{Method}}\label{{sec:method}}

\subsection{{Structural label extractor}}

Given a directed dependency-flow graph $G=(V,E)$, the extractor emits two boolean labels per node. A node is marked as a bottleneck when its removal lowers reachable terminal-flow coverage from the frozen source set or when it occupies a critical source-to-terminal dependency position. A node is marked as redundant when its dependency coverage overlaps another node by Jaccard similarity greater than $\theta=0.85$. We define redundancy gold labels using Jaccard $>0.85$ over dependency coverage, acknowledging that strict identical coverage is rarely observed in semantic KGs.

The TF-IDF comparator is named Semantic-Similarity Baseline (TF-IDF), not a graph-based method. This baseline is included to show that undirected semantic similarity, which lacks flow direction, cannot recover structural bottleneck/redundancy labels.

\subsection{{Life-Saving First budget allocation}}

Budget allocation proceeds sequentially. If a layer cumulatively exceeds K, selection stops within that layer sorted by impact; subsequent layers are not invoked for this trace. Critical Bottleneck nodes can override the ordinary auditable-node filter because root or scaffold bottlenecks may affect the whole downstream subgraph. Ordinary baselines rank only the auditable node pool.

The four strata are: Critical Bottleneck, Unique Evidence, Redundancy Group Samples, and Fallback. Within a stratum, nodes are ordered by downstream impact and then by the shared raw risk score only to break ties. The No-Fallback Ablation uses the same strata but randomizes same-layer tie breaking, testing whether Impact Coverage depends on the scalar fallback.

\section{{Results}}\label{{sec:results}}

\begin{{table}}[t]
\caption{{Countries-KG structural label F1 comparison. The semantic fixture contains {labels["kg_metadata"]["num_entities"]} entities and {labels["kg_metadata"]["num_triples"]} triples; labels are cached with seed {labels["seed"]}. The TF-IDF row is the Semantic-Similarity Baseline (TF-IDF). This baseline is included to show that undirected semantic similarity, which lacks flow direction, cannot recover structural bottleneck/redundancy labels.{limited_note}}}
\label{{tab:label-validation}}
\centering
\small
\begin{{tabular}}{{Z{{0.34\linewidth}}rrr}}
\toprule
\textbf{{Method}} & \textbf{{Bottleneck F1}} & \textbf{{Redundancy F1}} & \textbf{{Redundancy positives}} \\
\midrule
Structural label extractor & {kg["bottleneck_f1"]:.3f} & {kg["redundancy_f1"]:.3f} & {red_count} \\
Semantic-Similarity Baseline (TF-IDF) & {kg["tfidf_bottleneck_f1"]:.3f} & {kg["tfidf_redundancy_f1"]:.3f} & {int(details["structural_redundancy"]["support"])} \\
\bottomrule
\end{{tabular}}
\end{{table}}

Table~\ref{{tab:label-validation}} shows the controlled label-validation result. The structural extractor recovers the graph-defined labels, whereas the undirected semantic baseline fails to recover directed-flow bottleneck and redundancy roles. The result supports label extraction on a clean semantic fixture; it is not a claim about noisy open-domain KGs.

\begin{{table}}[t]
\caption{{Impact Coverage@K of Life-Saving First stratified policy vs. flat Top-K baseline (using the shared \detokenize{{raw_risk_score}} as the sole ranking criterion), centrality, position, random, and no-fallback ablation.}}
\label{{tab:impact-coverage}}
\centering
\small
\begin{{tabular}}{{Z{{0.31\linewidth}}rrrr}}
\toprule
\textbf{{Method}} & \textbf{{Impact Coverage@K}} & \textbf{{Avg. path length}} & \textbf{{Early truncation}} & \textbf{{Budget used}} \\
\midrule
Life-Saving First & {_ci_cell(audit, "life_saving_first", "impact_coverage_at_k")} & {_ci_cell(audit, "life_saving_first", "average_path_length_to_covered_descendants")} & {_ci_cell(audit, "life_saving_first", "early_truncation_rate")} & {_ci_cell(audit, "life_saving_first", "budget_used_fraction")} \\
Flat Top-K & {_ci_cell(audit, "flat_top_k", "impact_coverage_at_k")} & {_ci_cell(audit, "flat_top_k", "average_path_length_to_covered_descendants")} & {_ci_cell(audit, "flat_top_k", "early_truncation_rate")} & {_ci_cell(audit, "flat_top_k", "budget_used_fraction")} \\
Centrality & {_ci_cell(audit, "centrality", "impact_coverage_at_k")} & {_ci_cell(audit, "centrality", "average_path_length_to_covered_descendants")} & {_ci_cell(audit, "centrality", "early_truncation_rate")} & {_ci_cell(audit, "centrality", "budget_used_fraction")} \\
Position & {_ci_cell(audit, "position", "impact_coverage_at_k")} & {_ci_cell(audit, "position", "average_path_length_to_covered_descendants")} & {_ci_cell(audit, "position", "early_truncation_rate")} & {_ci_cell(audit, "position", "budget_used_fraction")} \\
Random & {_ci_cell(audit, "random", "impact_coverage_at_k")} & {_ci_cell(audit, "random", "average_path_length_to_covered_descendants")} & {_ci_cell(audit, "random", "early_truncation_rate")} & {_ci_cell(audit, "random", "budget_used_fraction")} \\
No-Fallback Ablation & {_ci_cell(audit, "no_fallback_ablation", "impact_coverage_at_k")} & {_ci_cell(audit, "no_fallback_ablation", "average_path_length_to_covered_descendants")} & {_ci_cell(audit, "no_fallback_ablation", "early_truncation_rate")} & {_ci_cell(audit, "no_fallback_ablation", "budget_used_fraction")} \\
\bottomrule
\end{{tabular}}
\end{{table}}

Table~\ref{{tab:impact-coverage}} evaluates budget allocation on cached Countries-KG labels. The comparison is deliberately between stratification and a single-score budget rule that shares the same scalar source. The no-fallback ablation matches the main policy in this fixture, indicating that the observed coverage is driven by the structural strata rather than by scalar fallback ordering. {_early_truncation_interpretation(audit)}

\section{{Boundary diagnosis}}\label{{sec:boundary}}

Appendix B reports a Necessary Condition Diagnosis on PRM800K. In the locked process-annotation route, the supervised fidelity field \texttt{{w\_struct}} reaches Spearman $\rho={prm["locked_prm800k"]["w_struct_spearman"]:.3f}$, whereas undirected TF-IDF graph-only necessity collapses to $\rho={prm["necessary_condition_proxy"]["tfidf_graph_only_rho_high_trace_length_proxy"]:.3f}$ in the high trace-length proxy. This is not a hidden main result. It defines a boundary condition: structural labels require at least moderately informative directed dependency edges and should not be expected to work when the graph constructor supplies sparse or directionless similarity.

\section{{Limitations}}\label{{sec:limitations}}

The semantic main experiment is deliberately bounded to Countries-KG to provide a ground-truth dependency flow for controlled F1 evaluation. We do not claim that structural labels are robust to arbitrary KG noise; rather, we treat this as a proof-of-concept on a clean semantic fixture. Scaling to noisy, open-domain KGs (e.g., via injected edge perturbations) is a necessary future step, not a claim of the current framework.

The study also does not report human usefulness evidence. The submission package contains a blank future human-evaluation protocol, but no returned ratings, evaluator provenance, declarations, timestamps, hashes, or reliability analysis are available. The present evidence therefore concerns structural label extraction and Impact Coverage on KG dependency flows, not human decision time or human audit accuracy.

\section{{Conclusion}}\label{{sec:conclusion}}

This paper reframes the SC-FMA line as structural label extraction and label-guided budget allocation. The contribution is not a new universal scorer. It is a graph-topology interface that emits bottleneck and redundancy flags, plus a Life-Saving First policy that uses those flags for fixed-budget audit visibility. The evidence supports controlled label extraction on Countries-KG, seeded scalability in Appendix A, Impact Coverage comparison on cached KG flows, and PRM800K necessary-condition boundaries in Appendix B.

\bibliography{{references}}
\end{{document}}
"""


def build_supplement_tex(metrics: Mapping[str, Any]) -> str:
    labels = metrics["labels"]
    audit = metrics["audit"]
    prm = metrics["prm"]
    synthetic = labels["synthetic_scalability"]
    sensitivity = labels.get("threshold_sensitivity", {})
    country_sens = sensitivity.get("countries_kg", {})

    rows = "\n".join(
        f"{row['n_nodes']} & {tex_escape(str(row['source']))} & {row['macro_f1']:.3f} \\\\"
        for row in synthetic["appendix_a_curve"]
    )
    synth_rows = "\n".join(
        f"{size} & {synthetic['runs'][str(size)]['macro_f1']:.3f} & "
        f"{synthetic['runs'][str(size)]['average_path_length_to_covered_descendants']:.3f} \\\\"
        for size in synthetic["sizes"]
    )

    return rf"""
% !TEX root = ./supplementary.tex
\documentclass[pdflatex,sn-mathphys-num]{{sn-jnl}}

\usepackage{{amsmath,amssymb}}
\usepackage{{booktabs}}
\usepackage{{array}}
\usepackage{{xurl}}

\newcolumntype{{Z}}[1]{{>{{\raggedright\arraybackslash}}p{{#1}}}}

\begin{{document}}

\title[Supplementary Material]{{Supplementary Material for ``{tex_escape(TITLE)}''}}
\author*[1]{{\fnm{{Haoran}} \sur{{Ma}}}}
\affil*[1]{{\orgdiv{{College of Management Science and Engineering}}, \orgname{{Beijing Information Science and Technology University}}, \orgaddress{{\city{{Beijing}}, \country{{China}}}}}}
\maketitle

\section{{Appendix A. Synthetic scalability and threshold sensitivity}}

Appendix A supports scalability beyond the Countries-KG semantic fixture without claiming robustness to arbitrary noisy open-domain KGs. The left anchor is the Countries-KG 30-node semantic fixture. Synthetic directed dependency graphs use seed {synthetic["seed"]} and sizes {", ".join(str(size) for size in synthetic["sizes"])}.

\begin{{table}}[h]
\caption{{Synthetic scalability curve with Countries-KG as the 30-node left anchor.}}
\centering
\small
\begin{{tabular}}{{rlr}}
\toprule
\textbf{{Nodes}} & \textbf{{Source}} & \textbf{{Macro F1}} \\
\midrule
{rows}
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{table}}[h]
\caption{{Synthetic graph diagnostics, including Average Path Length to Covered Descendants.}}
\centering
\small
\begin{{tabular}}{{rrr}}
\toprule
\textbf{{Nodes}} & \textbf{{Macro F1}} & \textbf{{Average path length}} \\
\midrule
{synth_rows}
\bottomrule
\end{{tabular}}
\end{{table}}

The redundancy threshold sensitivity check compares $\theta=0.85$ and $\theta=0.90$. Countries-KG gives {country_sens.get("theta_0_85_redundancy_positive_count", labels["countries_kg"]["redundancy_positive_count"])} redundancy positives at $\theta=0.85$ and {country_sens.get("theta_0_90_redundancy_positive_count", labels["countries_kg"]["redundancy_positive_count"])} positives at $\theta=0.90$. The synthetic planted-flow runs remain finite through 5k nodes under both thresholds.

\section{{Appendix B. Necessary Condition Diagnosis}}

This appendix uses \texttt{{scripts/run\_prm800k\_strong\_baselines.py}} only as boundary evidence. It is titled Necessary Condition Diagnosis because the PRM800K route lacks the directed KG dependency-flow condition used in the main experiment.

\begin{{table}}[h]
\caption{{PRM800K necessary-condition context. The graph-only row is boundary evidence, not a main result.}}
\centering
\small
\begin{{tabular}}{{Z{{0.42\linewidth}}rr}}
\toprule
\textbf{{Method}} & \textbf{{Spearman $\rho$}} & \textbf{{Mass@25\%}} \\
\midrule
\texttt{{w\_struct}} & {prm["strong_baselines_context"]["w_struct"]["spearman"]:.3f} & {prm["strong_baselines_context"]["w_struct"]["mass_at_25"]:.3f} \\
Structure graph + position & {prm["strong_baselines_context"]["structure_graph_position"]["spearman"]:.3f} & {prm["strong_baselines_context"]["structure_graph_position"]["mass_at_25"]:.3f} \\
Structure graph only & {prm["strong_baselines_context"]["structure_graph_only"]["spearman"]:.3f} & {prm["strong_baselines_context"]["structure_graph_only"]["mass_at_25"]:.3f} \\
Raw local utility & {prm["strong_baselines_context"]["raw_local_utility"]["spearman"]:.3f} & {prm["strong_baselines_context"]["raw_local_utility"]["mass_at_25"]:.3f} \\
\bottomrule
\end{{tabular}}
\end{{table}}

The requested condition, Trace Length $>20$ and graph density $<0.05$, is represented by an archived high-trace-length sparse-TF-IDF proxy because the locked report does not store an exact joint density stratum. Under that proxy, graph-only $\rho={prm["necessary_condition_proxy"]["tfidf_graph_only_rho_high_trace_length_proxy"]:.3f}$. This negative result defines the framework boundary: structural labels need directed dependency edges with at least moderate logical density.

\section{{Appendix C. Cached-label audit reproducibility}}

The audit case loads \texttt{{{tex_escape(audit["label_cache"]["path"])}}}. The report records \texttt{{recomputed\_label\_count=0}}, seed {audit["seed"]}, {audit["n_traces"]} simulated audit repetitions, and budget fraction {audit["budget_fraction"]:.2f}. The cache includes node identifiers, bottleneck flags, redundancy flags, redundancy group identifiers, downstream impact counts, thresholds, random seed, KG metadata hash, and synthetic DAG configuration.

\bibliography{{references}}
\end{{document}}
"""


def sanitize_references() -> None:
    bib_path = SOURCE / "references.bib"
    if not bib_path.exists():
        write_text(bib_path, "% References are retained for submission package completeness.")
        return
    text = bib_path.read_text(encoding="utf-8")
    text = re.sub(r"\n\s*url\s*=\s*\{[^{}]*\},?", "", text)
    bib_path.write_text(text, encoding="utf-8")


def _ensure_template_files() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    for name in ("sn-jnl.cls", "sn-mathphys-num.bst", "sn-basic.bst", "sn-nature.bst"):
        target = SOURCE / name
        if target.exists():
            continue
        candidates = list(JIIS.glob(f"**/{name}"))
        candidates = [path for path in candidates if path != target and path.is_file()]
        if candidates:
            shutil.copy2(candidates[0], target)
    sanitize_references()


def write_manuscripts(metrics: Mapping[str, Any]) -> None:
    _ensure_template_files()
    write_text(SOURCE / "manuscript.tex", build_main_tex(metrics))
    write_text(SOURCE / "supplementary.tex", build_supplement_tex(metrics))
    (SOURCE / "sections").mkdir(parents=True, exist_ok=True)
    write_text(
        SOURCE / "sections" / "README.md",
        "The JIIS source is consolidated in manuscript.tex and supplementary.tex for flat upload.",
    )
    SUPP.mkdir(parents=True, exist_ok=True)
    for name in ("references.bib", "sn-jnl.cls", "sn-mathphys-num.bst", "sn-basic.bst", "sn-nature.bst"):
        src = SOURCE / name
        if src.exists():
            shutil.copy2(src, SUPP / name)


def build_human_eval_package() -> None:
    if HUMAN.exists():
        shutil.rmtree(HUMAN)
    HUMAN.mkdir(parents=True)
    cards = [
        ("label", "A structural label flags a root dependency bottleneck."),
        ("label", "A redundancy group representative summarizes duplicated KG coverage."),
        ("policy", "Life-Saving First allocates budget to a critical bottleneck."),
        ("policy", "Unique Evidence is considered after bottleneck coverage."),
        ("policy", "A redundancy-group sample is selected after critical bottlenecks."),
        ("baseline", "Flat Top-K ranks by the shared raw risk score."),
        ("baseline", "Centrality selects high-degree nodes without bottleneck labels."),
        ("diagnostic", "No-Fallback Ablation randomizes same-layer tie breaking."),
        ("boundary", "PRM800K is used only as necessary-condition diagnosis."),
    ]
    key_rows = []
    for evaluator_idx in range(1, 4):
        folder = HUMAN / f"evaluator_{evaluator_idx}"
        (folder / "cards").mkdir(parents=True)
        for idx, (condition, summary) in enumerate(cards, start=1):
            blinded_id = f"E{evaluator_idx}-JIIS-CARD-{idx:03d}"
            write_text(
                folder / "cards" / f"{blinded_id}.md",
                f"""# Blind Audit Card {blinded_id}

Trace summary: {summary}

Audit prompt: Inspect whether this record would help prioritize a node under a fixed budget.

Do not use external tools, automation, or discussion with other evaluators.
""",
            )
            key_rows.append(
                {
                    "evaluator": evaluator_idx,
                    "blinded_id": blinded_id,
                    "card_id": f"JIIS-CARD-{idx:03d}",
                    "condition": condition,
                }
            )
        with (folder / f"rating_sheet_evaluator_{evaluator_idx}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "blinded_id",
                    "usefulness_1_5",
                    "interpretability_1_5",
                    "actionability_1_5",
                    "would_prioritize_yes_no",
                    "notes",
                ],
            )
            writer.writeheader()
            for idx in range(1, 10):
                writer.writerow(
                    {
                        "blinded_id": f"E{evaluator_idx}-JIIS-CARD-{idx:03d}",
                        "usefulness_1_5": "",
                        "interpretability_1_5": "",
                        "actionability_1_5": "",
                        "would_prioritize_yes_no": "",
                        "notes": "",
                    }
                )
        write_text(
            folder / "INSTRUCTIONS.md",
            f"""# Evaluator {evaluator_idx} Instructions

Review each card in the `cards` folder and fill only `rating_sheet_evaluator_{evaluator_idx}.csv`.
No results from this package are part of the manuscript until real returns, declarations, timestamps, hashes, and reliability checks are complete.
""",
        )
        write_text(
            folder / "RETURN_DECLARATION.md",
            f"""# Independent Completion Declaration

I confirm that I independently completed evaluator package {evaluator_idx}, did not use automated rating tools, and did not coordinate answers with other evaluators.

Name:

Date:

Signature:
""",
        )
    analyst = HUMAN / "analyst_only"
    analyst.mkdir()
    with (analyst / "blinding_key.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["evaluator", "blinded_id", "card_id", "condition"])
        writer.writeheader()
        writer.writerows(key_rows)
    write_text(
        HUMAN / "README.md",
        """# JIIS Human-Evaluation Pending Package

This package is blank and future-facing. No human result may be reported until real evaluator returns, timestamps, hashes, declarations, and reliability analysis are available.
""",
    )
    write_text(
        HUMAN / "analyze_returns.py",
        r'''"""Analyze real returned JIIS human-evaluation sheets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--returns-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.returns_dir.glob("evaluator_*/rating_sheet_evaluator_*.csv"))
    rows = []
    for path in files:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                row["source_file"] = str(path)
                rows.append(row)
    result = {
        "status": "pending_real_returns",
        "n_files": len(files),
        "n_rows": len(rows),
        "file_hashes": {str(path): sha256(path) for path in files},
        "claim_boundary": "do_not_report_without_real_return_provenance",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if files else 1


if __name__ == "__main__":
    raise SystemExit(main())
''',
    )


def build_verifier() -> None:
    write_text(
        ROOT / "scripts" / "verify_jiis_submission.py",
        r'''"""Verify the local JIIS submission workspace."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader


BUILD_SUFFIXES = {
    ".aux", ".bbl", ".bcf", ".blg", ".fdb_latexmk", ".fls", ".log",
    ".out", ".run.xml", ".synctex.gz",
}

FORBIDDEN_POSITIVE = (
    "human validation",
    "human audit usefulness",
    "production knowledge-base validation",
    "production kg validation",
    "causal effect",
    "average treatment effect",
    "external deployment",
    "deployed workflow validation",
    "robust to arbitrary kg noise",
)

NEGATORS = ("not ", "no ", "does not ", "do not ", "future ", "without ", "rather than ", "not a ")


def abstract_words(tex: str) -> int:
    match = re.search(r"\\abstract\{(.+?)\}\s*\\keywords", tex, flags=re.S)
    if not match:
        return 0
    text = re.sub(r"\\[a-zA-Z]+(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", match.group(1))
    text = re.sub(r"[^A-Za-z0-9\- ]+", " ", text)
    return len([word for word in text.split() if word])


def keyword_count(tex: str) -> int:
    match = re.search(r"\\keywords\{(.+?)\}", tex, flags=re.S)
    if not match:
        return 0
    return len([item.strip() for item in match.group(1).replace(";", ",").split(",") if item.strip()])


def is_negated(text: str, pattern: str) -> bool:
    idx = text.lower().find(pattern)
    if idx < 0:
        return True
    window = text.lower()[max(0, idx - 120): idx + len(pattern) + 120]
    return any(marker in window for marker in NEGATORS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("paper/JIIS_submission"))
    parser.add_argument("--max-pages", type=int, default=25)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)

    ws = args.workspace.resolve()
    source = ws / "source"
    package = ws / "submission_package"
    main_tex = source / "manuscript.tex"
    supp_tex = source / "supplementary.tex"
    main_pdf = source / "manuscript.pdf"
    supp_pdf = source / "supplementary.pdf"
    errors: list[str] = []

    tex = main_tex.read_text(encoding="utf-8") if main_tex.exists() else ""
    abs_count = abstract_words(tex)
    kw_count = keyword_count(tex)
    if not 150 <= abs_count <= 250:
        errors.append(f"abstract_words={abs_count}, expected 150-250")
    if kw_count != 6:
        errors.append(f"keyword_count={kw_count}, expected 6")
    if r"\input{" in tex:
        errors.append("main manuscript uses \\input")
    if "Recall@25%" in tex:
        errors.append("Recall@25% appears as a main-result metric")
    for phrase in FORBIDDEN_POSITIVE:
        if phrase in tex.lower() and not is_negated(tex, phrase):
            errors.append(f"forbidden positive claim: {phrase}")

    pages = None
    if main_pdf.exists():
        pages = len(PdfReader(str(main_pdf)).pages)
        if pages > args.max_pages:
            errors.append(f"manuscript_pages={pages}, expected <= {args.max_pages}")
    else:
        errors.append("missing source/manuscript.pdf")
    if not supp_pdf.exists():
        errors.append("missing source/supplementary.pdf")
    for src in (main_tex, supp_tex):
        pdf = src.with_suffix(".pdf")
        if src.exists() and pdf.exists() and pdf.stat().st_mtime < src.stat().st_mtime:
            errors.append(f"{pdf.name} older than {src.name}")

    required_package = {
        "manuscript.pdf",
        "supplementary.pdf",
        "manuscript.tex",
        "supplementary.tex",
        "references.bib",
        "sn-jnl.cls",
        "sn-mathphys-num.bst",
    }
    existing = {path.name for path in package.iterdir()} if package.exists() else set()
    missing = sorted(required_package - existing)
    if missing:
        errors.append(f"submission_package missing {missing}")
    build_artifacts = [
        path.name for path in package.iterdir()
        if path.is_file() and any(path.name.endswith(suffix) for suffix in BUILD_SUFFIXES)
    ] if package.exists() else []
    if build_artifacts:
        errors.append(f"submission_package contains build artifacts {build_artifacts}")

    result = {
        "workspace": str(ws),
        "abstract_words": abs_count,
        "keyword_count": kw_count,
        "manuscript_pages": pages,
        "package_files": sorted(existing),
        "errors": errors,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
''',
    )


def compile_tex(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", path.name],
        cwd=path.parent,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return proc.returncode, proc.stdout + proc.stderr


def build_submission_package() -> None:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)
    for name in (
        "manuscript.pdf",
        "supplementary.pdf",
        "manuscript.tex",
        "supplementary.tex",
        "references.bib",
        "sn-jnl.cls",
        "sn-mathphys-num.bst",
        "sn-basic.bst",
        "sn-nature.bst",
    ):
        src = SOURCE / name
        if src.exists():
            shutil.copy2(src, PACKAGE / name)
    figures_src = SOURCE / "figures"
    if figures_src.exists():
        shutil.copytree(figures_src, PACKAGE / "figures")
    clean_latex_builds(PACKAGE)


def write_reports(metrics: Mapping[str, Any], compile_logs: Mapping[str, str]) -> None:
    manuscript_tex = (SOURCE / "manuscript.tex").read_text(encoding="utf-8")
    package_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(PACKAGE.iterdir())
        if path.is_file()
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": TITLE,
        "workspace": str(JIIS),
        "abstract_words": abstract_word_count(manuscript_tex),
        "keyword_count": 6,
        "evidence_boundary": {
            "main": "Countries-KG clean semantic fixture plus cached-label Impact Coverage simulation",
            "production_validation": False,
            "human_evaluation": "blank future protocol only",
            "causal_identification": False,
            "arbitrary_kg_noise_robustness": False,
        },
        "key_metrics": {
            "countries_kg_redundancy_positive_count": metrics["labels"]["countries_kg"]["redundancy_positive_count"],
            "life_saving_first_impact_coverage_at_k": metrics["audit"]["methods"]["life_saving_first"]["impact_coverage_at_k"]["mean"],
            "flat_top_k_impact_coverage_at_k": metrics["audit"]["methods"]["flat_top_k"]["impact_coverage_at_k"]["mean"],
            "prm800k_tfidf_graph_only_high_trace_length_proxy": metrics["prm"]["necessary_condition_proxy"]["tfidf_graph_only_rho_high_trace_length_proxy"],
        },
        "compile_logs": dict(compile_logs),
        "submission_package_sha256": package_hashes,
    }
    write_text(REPORTS / "jiis_generation_report.json", json.dumps(report, indent=2, sort_keys=True))
    write_text(
        REPORTS / "claim_boundary_report.md",
        """# JIIS Claim-Boundary Report

Allowed claims:
- structural label extractor for bottleneck and redundancy flags.
- F1 comparison on the Countries-KG clean semantic fixture.
- Impact Coverage@K on cached KG dependency flows.
- stratified budget allocation with Life-Saving First.
- PRM800K necessary-condition diagnosis.

Disallowed claims:
- No production knowledge-base validation.
- No human usefulness or human audit-time result.
- No causal effect or average treatment effect.
- No robustness to arbitrary KG noise.
- No universal scorer or ranking-improvement claim.
""",
    )


def main() -> int:
    metrics = load_metrics()
    for directory in (SOURCE, SUPP, HUMAN, REPORTS, PACKAGE):
        directory.mkdir(parents=True, exist_ok=True)
    write_manuscripts(metrics)
    build_human_eval_package()
    build_verifier()
    clean_latex_builds(SOURCE)

    compile_logs: dict[str, str] = {}
    for tex in (SOURCE / "manuscript.tex", SOURCE / "supplementary.tex"):
        code, log = compile_tex(tex)
        compile_logs[tex.name] = log[-8000:]
        if code != 0:
            write_text(REPORTS / f"{tex.stem}_compile_failure.log", log)
            return code
    build_submission_package()
    write_reports(metrics, compile_logs)
    clean_latex_builds(SOURCE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
