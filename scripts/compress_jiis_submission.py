"""Compress the JIIS manuscript and restructure supplementary material.

This script is intentionally manuscript-specific.  It rewrites the current
Springer single-TeX JIIS source into a compact journal-submission version while
preserving locked empirical numbers and claim boundaries.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
JIIS = ROOT / "paper" / "JIIS_submission"
SOURCE = JIIS / "source"
PACKAGE = JIIS / "submission_package"
REPORTS = JIIS / "reports"

TITLE = (
    "Dependency-Aware Audit Records for Fixed-Budget Inspection of "
    "Knowledge-Intensive Information Systems"
)

BUILD_SUFFIXES = {
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
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def page_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return len(PdfReader(str(path)).pages)


def extract_environment(tex: str, env: str, label: str) -> str:
    pattern = rf"\\begin\{{{env}\}}(?:\[[^\]]*\])?.*?\\end\{{{env}\}}"
    label_text = rf"\label{{{label}}}"
    for match in re.finditer(pattern, tex, flags=re.S):
        block = match.group(0)
        if label_text in block:
            return block
    return ""


def extract_algorithm(supp: str, label: str) -> str:
    return extract_environment(supp, "algorithm", label)


def extract_table_any(label: str, *sources: str) -> str:
    for source in sources:
        block = extract_environment(source, "table", label)
        if block:
            return block
    return ""


def clean_supplementary_block(block: str) -> str:
    """Remove stale main-text cross-references from migrated supplementary blocks."""
    if not block:
        return block
    replacements = {
        "; see Section~\\ref{sec:why-calibration} for target-dependence caveats": "",
        "; see Section~\\ref{sec:why-calibration} for the weak utility-anchor and bottleneck-protection caveats": "",
        ' Target-dependence caveats are given above and in Table~\\ref{tab:oracle-auto-validation-by-target}.': "",
    }
    for old, new in replacements.items():
        block = block.replace(old, new)
    return block


def richer_source(primary: Path, fallback: Path, table_threshold: int) -> Path:
    """Use the fuller pre-compression source when the working source is compact."""
    if fallback.exists():
        primary_tables = read(primary).count(r"\begin{table}") if primary.exists() else 0
        fallback_tables = read(fallback).count(r"\begin{table}")
        if fallback_tables > primary_tables and fallback_tables >= table_threshold:
            return fallback
    return primary


def clean_builds(directory: Path) -> None:
    if not directory.exists():
        return
    for path in directory.iterdir():
        if path.is_file() and any(path.name.endswith(suffix) for suffix in BUILD_SUFFIXES):
            path.unlink()


def preamble(title: str, supplementary: bool = False) -> str:
    short = "Supplementary Material" if supplementary else "Dependency-Aware Audit Records"
    title_text = f'Supplementary Material for ``{title}"' if supplementary else title
    return rf"""
% !TEX root = ./{"supplementary.tex" if supplementary else "manuscript.tex"}
\documentclass[pdflatex,sn-mathphys-num]{{sn-jnl}}

\usepackage{{graphicx}}
\usepackage{{multirow}}
\usepackage{{amsmath,amssymb,amsfonts}}
\usepackage{{amsthm}}
\usepackage{{booktabs}}
\usepackage{{array}}
\usepackage{{xurl}}
\usepackage{{algorithm}}
\usepackage{{algorithmicx}}
\usepackage{{algpseudocode}}
\usepackage{{makecell}}
\usepackage{{placeins}}
\usepackage{{float}}
\usepackage{{textcomp}}

\newtheorem{{theorem}}{{Theorem}}[section]
\newtheorem{{lemma}}[theorem]{{Lemma}}
\newtheorem{{corollary}}[theorem]{{Corollary}}
\newcolumntype{{Z}}[1]{{>{{\raggedright\arraybackslash}}p{{#1}}}}
\newcommand{{\wstruct}}{{\ensuremath{{\mathbf{{w}}_{{\mathrm{{struct}}}}}}}}

\raggedbottom
\begin{{document}}

\title[{short}]{{{title_text}}}

\author*[1]{{\fnm{{Haoran}} \sur{{Ma}}}}\email{{mahaoran0000@foxmail.com}}
\author[1,2]{{\fnm{{Ningning}} \sur{{Wang}}}}\email{{wangningning@bistu.edu.cn}}

\affil*[1]{{\orgdiv{{College of Management Science and Engineering}}, \orgname{{Beijing Information Science and Technology University}}, \orgaddress{{\city{{Beijing}}, \postcode{{102200}}, \country{{China}}}}}}
\affil[2]{{\orgdiv{{Institute of Information Systems, ESG Intelligent Application Innovation Research Center}}, \orgname{{Beijing Information Science and Technology University}}, \orgaddress{{\city{{Beijing}}, \postcode{{102200}}, \country{{China}}}}}}
"""


def manuscript_tex() -> str:
    return (
        preamble(TITLE)
        + r"""
\abstract{Knowledge-intensive information systems expose retrieval checks, entity bindings, process annotations, graph nodes, and verification records. Curators inspect these artifacts under fixed audit budgets and need reusable records that make supplied fidelity fields explicit while showing dependency, redundancy, bottleneck exposure, and interpretive role. We introduce SC-FMA as an artifact representation and audit-record construction framework for converting observable process artifacts into queryable inspection records. The historical metacognitive terminology is retained only as an operational name for secondary inspection over observable artifacts. On a locked PRM800K-derived process-annotation distribution (4,417 samples; 34,219 labeled artifacts), the supervised \wstruct{} fidelity field remains strongest (Spearman $\rho=0.611$), while the calibrated Ridge record tracks it with a small loss ($\rho=0.604$) and adds decomposed record fields. Graph-derived features alone reach only $\rho=0.043$ under the same supervision, and a mathematical dependency DAG remains below a reverse-position baseline. A KG/RAG-style audit simulation shows that direct rule-only records are strongest when audit targets are explicitly observable, while dependency-aware records remain competitive with raw-field and diversity baselines. The evidence supports record organization and fixed-budget visibility, not production knowledge-base validation, human audit usefulness, cross-domain transfer, or causal identification.}

\keywords{knowledge-intensive information systems, audit records, knowledge graphs, retrieval-augmented generation, fixed-budget inspection, process annotation}

\maketitle

\section{Introduction}
\label{sec:introduction}

Knowledge-intensive information systems increasingly expose intermediate artifacts during retrieval, annotation, validation, update, and reuse. These artifacts include retrieved passages, graph nodes, entity bindings, verification records, rule-like operations, process annotations, and reasoning traces. Once exposed, they become knowledge artifacts: objects that must be represented, organized, inspected, and reused across the knowledge lifecycle. The practical difficulty is not only that these artifacts may be noisy or incomplete, but also that they often outnumber the audit capacity available to curators.

Existing methods supply useful signals for this setting. Process-annotation methods attach scalar quality estimates to intermediate artifacts. Local utility methods estimate artifact influence. Graph-based salience methods identify structurally prominent nodes. Fixed-budget knowledge audit requires an additional object: a reusable record that combines supplied fidelity fields with dependency structure and audit interpretation. Such a record helps a curator see whether an artifact provides local evidence, supports a dependency, duplicates earlier support, or exposes a downstream bottleneck.

This paper introduces SC-FMA as an artifact representation and audit-record construction framework for knowledge-intensive systems. The framework transforms observable process artifacts into structured audit records with fidelity, dependency, redundancy, bottleneck, reason, and interpretation fields. In this version, ``metacognitive'' is used only operationally: it denotes engineered secondary inspection of observable attribution-related artifacts, not latent cognitive-state monitoring. The contribution is therefore a knowledge-engineering contribution, not a claim about improving LLM reasoning accuracy.

The paper makes three contributions. First, it formulates fixed-budget audit-record construction for structured knowledge artifacts. Second, it retains the SCU objective as a calibration component that combines fidelity fields, structural dependency, redundancy, and bottleneck roles into decomposed records. Third, it evaluates the representation on a PRM800K process-annotation distribution, a KG/RAG-style audit simulation, a Countries-KG backend feasibility study, rule-derived audit-target retrieval, and controlled synthetic calibration. The evaluation is explicitly bounded: several results show that direct rules or supplied fidelity fields are stronger than graph-derived calibration for ranking, while SC-FMA contributes a reusable record schema and interpretation fields.

The main real-data result is negative in the right way for this framing. On the locked PRM800K route, \wstruct{} is the strongest supervised fidelity field, and SC-FMA Ridge closely tracks rather than improves over it. Same-supervision controls show that graph-derived features alone carry little independent annotation-order signal. These findings make the structural fields organizational and diagnostic on this distribution. They do not support claims of reasoning improvement, universal interpretability, or causal effect estimation.

Figure~\ref{fig:overall-framework} summarizes the workflow: observable knowledge artifacts are normalized, represented as dependency graphs, calibrated through SCU when a supplied fidelity field is available, and emitted as audit records for fixed-budget inspection and knowledge maintenance.

\begin{figure}[!t]
\centering
\includegraphics[width=\linewidth]{figures/fig_overall_framework.pdf}
\caption{Overview of the SC-FMA audit-record construction framework. Observable knowledge artifacts are represented through dependency structure, calibrated against supplied fidelity fields, and emitted as audit records with dependency, redundancy, bottleneck, reason, and interpretation fields.}
\label{fig:overall-framework}
\end{figure}

\section{Related Work}
\label{sec:related-work}

\subsection{Attribution, process signals, and audit records}

Attribution methods ask which parts of an input, computation, or structure matter for a decision. Integrated Gradients~\cite{sundararajan2017axiomatic}, SHAP~\cite{lundberg2017unified}, LIME~\cite{ribeiro2016lime}, and ERASER~\cite{deyoung2020eraser} provide feature-level, local, or extractive explanation signals. Structure-aware explanation adds graph context: network studies show why importance can be non-local or concentrated around bottlenecks~\cite{albert2000error,newman2010networks}, and GNNExplainer selects compact explanatory subgraphs~\cite{ying2019gnnexplainer}. Human-centered XAI further shows that explanations must fit review tasks and organizational routines~\cite{miller2019explanation,arrieta2020explainable,amershi2019guidelines,kaplan2024xai}.

Process supervision supplies artifact-level fidelity fields. PRM800K and process-based feedback show that step annotations can support verifier-guided reasoning systems~\cite{lightman2023verify,uesato2022solving,cobbe2021training}. Chain-of-thought, self-consistency, ReAct, Tree of Thoughts, Reflexion, and Self-Refine expose richer process units that can become audit artifacts~\cite{wei2022cot,wang2022selfconsistency,yao2022react,yao2023tot,shinn2023reflexion,madaan2023selfrefine}. ProcessBench and Math-Shepherd illustrate the need to test scalar step signals against process-verification tasks~\cite{wang2024mathshepherd,zheng2024processbench}. SC-FMA uses such signals as record inputs rather than claiming to replace PRMs or train a new reward model.

\subsection{Knowledge-intensive information systems}

Knowledge engineering has long treated representation, inference, and maintenance-oriented review as coupled design problems~\cite{studer1998knowledge}. Expert systems and cognitive architectures made intermediate states inspectable for rule review and operator analysis~\cite{buchanan1984mycin,lindsay1980dendral,laird2012soar,anderson2004actr}. In information systems, knowledge management and algorithmic accountability emphasize transparency, traceability, and organizational oversight~\cite{dwivedi2021artificial,raji2020closing}.

Modern knowledge-intensive pipelines connect language models with structured knowledge. Knowledge graphs represent entities, relations, constraints, and quality signals~\cite{hogan2021knowledge}. RAG and GraphRAG expose passages, entity graphs, and community summaries as evidence~\cite{lewis2020rag,gao2023ragsurvey,edge2024graphrag}. KG-RAG, knowledge-enhanced language models, and LLM-KG integration expose entity links, triples, and relation paths as reviewable artifacts~\cite{sanmartin2024kgrag,hu2024knowledgeenhanced,pan2024unifying}. Recent KG-quality and LLM-KG studies show why graph-quality signals become part of the audit surface~\cite{yang2025kbllmsurvey,chen2025kgquality,dai2025llmkg}.

Across these settings, the challenge is not simply recovering intermediate evidence. Many systems already expose passages, entity links, relation paths, and verification records. The harder question is how to allocate limited curation budget and preserve reusable records for refinement, update, and maintenance~\cite{paulheim2017knowledge,higgins2008dcc}. SC-FMA targets this record-construction layer.

\section{Method}
\label{sec:methods}

\subsection{Framework Overview}

SC-FMA converts exposed knowledge artifacts into fixed-budget audit records. The input is an observable artifact sequence $T=(s_1,\ldots,s_k)$, where each $s_i$ may be a retrieval check, entity binding, graph relation, verification note, process annotation, or rule-like operation. The output is a record for each artifact plus a budgeted priority view. Each record stores the supplied fidelity field, dependency context, redundancy status, bottleneck status, audit reason, and interpretation.

The pipeline has four stages. First, trace normalization maps heterogeneous system outputs into ordered artifact units with stable identifiers. Second, dependency modeling builds a graph over these units. Third, SCU calibration combines a supplied fidelity field with graph-derived structural fields when such calibration is requested. Fourth, audit-record construction emits machine-readable records that support fixed-budget inspection and later knowledge maintenance. Detailed implementation settings and pseudocode are provided in Supplementary Section S2.

\subsection{Artifact Representation and Dependency Modeling}

Each artifact unit is treated as an observed knowledge artifact rather than as a latent reasoning state. A graph $G=(V,E)$ represents artifact dependencies: nodes correspond to units, temporal edges connect adjacent units, and optional topical or domain-specific edges connect related units. The default implementation uses temporal order and TF-IDF similarity as a lightweight fallback when richer domain edges are unavailable. Semantic embeddings, entity links, knowledge graphs, ontologies, rule-dependency DAGs, and data-lineage graphs can replace the default constructor without changing the record schema.

This substitutability is important for interpretation. In the present evidence package, TF-IDF topical edges add little annotation-order signal over temporal order, while typed KG edges in the Countries-KG fixture substantially change structural-necessity values. These checks support the graph layer as a replaceable construction interface, not as an independently validated reasoning-quality metric. Additional graph-construction variants and sensitivity checks are reported in Supplementary Section S3.

\subsection{Structural Calibration Unit (SCU)}
\label{sec:scu-objective}

SCU is a representation constraint system for fixed-budget audit records. For a sequence with $k$ auditable units, let $\tilde{\mathbf{c}}\in\mathbb{R}^k$ denote a normalized utility or proxy-fidelity field. In the locked PRM800K process-annotation stage, \wstruct{} denotes the output of the frozen Ridge regressor used as this fidelity field. Let $\tilde{\mathbf{n}}$ denote normalized structural necessity from graph perturbation checks, $\mathbf{R}$ a redundancy matrix, and $\mathbf{b}$ a bottleneck indicator. SCU computes calibrated priority values $\mathbf{w}$ on the simplex
\begin{equation}
\mathcal{W}=\{\mathbf{w}\in\mathbb{R}_{+}^{k}: \sum_i w_i = 1\}
\label{eq:scu-feasible-set}
\end{equation}
by minimizing
\begin{equation}
L(\mathbf{w}) =
\alpha\|\mathbf{w} - \tilde{\mathbf{c}}\|_2^2
+ \beta\|\mathbf{w} - \tilde{\mathbf{n}}\|_2^2
+ \gamma\,\mathbf{w}^{\top}\mathbf{R}\mathbf{w}
- \delta\sum_i b_i \log(w_i).
\label{eq:scu}
\end{equation}
The terms encode fidelity preservation, structural alignment, redundancy regularization, and non-zero bottleneck support. Ridge uses a closed-form fidelity-tracking softmax and omits the redundancy and bottleneck terms; QP solves the full constrained program; Projection applies a fast topology-constrained simplex projection~\cite{wang2013projection}. Detailed derivations, KKT conditions, convexity checks, and monotonicity caveats are provided in Supplementary Section S1.

\subsection{Audit Record Construction}

The calibrated priority field is only one field in the audit record. A selected artifact can also report whether its priority was driven mainly by fidelity, structural dependency, redundancy, or bottleneck exposure. This decomposition supports maintenance-oriented interpretation: verify the fidelity field, inspect a dependency chain, consolidate duplicate evidence, or protect a downstream bottleneck.

The record schema separates representation from selector. A system can fill the record with direct rules, raw fields, centrality, diversity selection, or SCU-calibrated values. This matters empirically because the KG/RAG audit simulation shows that direct rule-only records are strongest when targets are explicitly observable. SC-FMA is therefore evaluated as an artifact representation and audit-record framework, not as a universal ranking improvement.

\subsection{Implementation Details}
\label{sec:implementation-details}

The experiments use deterministic splits, fixed seeds, and archived JSON/CSV outputs. The process-annotation stage uses a frozen PRM800K hash split; the \wstruct{} model is trained only on development records and then frozen before locked reporting. SCU weights are selected before test-set reporting within each configuration. The later window-size sweep was conducted after observing long-trace QP failure, so it is reported only as a post hoc coupling diagnostic. Complexity, runtime, and memory details are moved to Supplementary Section S4.

\section{Evaluation}
\label{sec:experimental-results}

The evaluation treats fixed-budget audit as an information-representation task. It asks whether audit records track supplied fidelity fields, whether graph construction changes dependency representations, and whether decomposed records expose audit-target information under a fixed review budget. Table~\ref{tab:evidence-routes} summarizes the evidence stages and their allowed interpretations.

\begin{table}[!t]
\caption{Evaluation stages and claim boundaries.}
\label{tab:evidence-routes}
\centering
\small
\renewcommand{\arraystretch}{1.08}
\begin{tabular}{Z{0.27\linewidth}Z{0.27\linewidth}Z{0.34\linewidth}}
\toprule
\textbf{Stage} & \textbf{Evidence object} & \textbf{Interpretation} \\
\midrule
KG/RAG audit simulation & 600 traces, 4,800 artifacts & Fixed-budget visibility for observable audit targets. \\
PRM800K process annotations & 4,417 samples, 34,219 labeled artifacts & Fidelity tracking and decomposition under a locked in-distribution route. \\
Countries-KG backend & 30 traces, 30 entities, 189 triples & Typed graph-interface feasibility and backend sensitivity. \\
Controlled synthetic calibration & 200 traces per seed, five fixed seeds & Mechanism and ablation checks under designed labels. \\
Supplementary WebQSP/MuSiQue/GSM8K/HotpotQA routes & Fixed-schema, constructed-label, failed, or blocked routes & Boundary and transparency diagnostics only. \\
\bottomrule
\end{tabular}
\end{table}

\subsection{Fixed-Budget Audit Visibility}

The KG/RAG-style audit simulation contains observable entity-binding, evidence-support, duplicate-support, dependency-bottleneck, and temporal-conflict fields. Audit targets are generated before method scoring and do not use SCU weights or dependency-aware recommendations. All methods use the same 25\% budget.

\begin{table}[!t]
\caption{Fixed-budget visibility in the KG/RAG audit simulation.}
\label{tab:jiis-audit-case}
\centering
\small
\renewcommand{\arraystretch}{1.06}
\begin{tabular}{Z{0.28\linewidth}rrrr}
\toprule
\textbf{Method} & \textbf{Recall} & \textbf{NDCG} & \textbf{Top-1} & \textbf{Mass} \\
\midrule
Scalar fidelity & 0.262 & 0.245 & 0.190 & 0.543 \\
Raw-field bundle & 0.642 & 0.636 & 0.553 & 0.536 \\
Position / last-step & 0.000 & 0.000 & 0.000 & 0.541 \\
Graph centrality & 0.462 & 0.437 & 0.343 & 0.565 \\
PageRank-like & 0.487 & 0.442 & 0.318 & 0.542 \\
MMR diversity & 0.654 & 0.644 & 0.558 & 0.539 \\
Rule-only record & \textbf{0.908} & \textbf{0.949} & \textbf{0.922} & \textbf{0.789} \\
Dependency-aware record & 0.637 & 0.625 & 0.543 & 0.537 \\
\bottomrule
\end{tabular}
\end{table}

Table~\ref{tab:jiis-audit-case} gives a deliberately bounded result. Rule-only records are strongest because several targets are directly observable. Dependency-aware records remain close to the raw-field bundle and MMR diversity, but they do not dominate direct rules. The result supports target visibility and record organization. They do not establish production knowledge-base validation or human audit usefulness.

\subsection{Process-Annotation Fidelity Tracking}
\label{sec:prm800k-evidence}

The main real-data check uses the locked PRM800K split for annotation-field tracking and fixed-budget coverage. The stored \wstruct{} field is the strongest fidelity reference, computed by a development-trained Ridge model. SC-FMA Ridge closely tracks this field while exposing decomposition fields; QP and Projection are lower-consistency variants. The archived paired-difference report does not support treating any SC-FMA variant as an annotation-order improvement over \wstruct{} on this route.

\begin{table}[!t]
\caption{PRM800K fidelity tracking and same-supervision controls.}
\label{tab:prm800k-audit}
\centering
\scriptsize
\renewcommand{\arraystretch}{1.05}
\begin{tabular}{Z{0.29\linewidth}cccZ{0.25\linewidth}}
\toprule
\textbf{Field or control} & \textbf{Spearman $\rho$} & \textbf{Mass@25\%} & \textbf{NDCG@25\%} & \textbf{Interpretation} \\
\midrule
\wstruct{} & \textbf{0.611} & \textbf{0.381} & \textbf{0.951} & Strongest supervised fidelity field. \\
SC-FMA Ridge & 0.604 & 0.380 & 0.946 & Close fidelity-tracking decomposition. \\
SC-FMA QP & 0.442 & 0.379 & 0.944 & Full structural-allocation view, not a PRM800K winner. \\
SC-FMA Projection & $-$0.135 & 0.288 & 0.743 & Lower-consistency projection view. \\
Frozen PRM prefix signal & 0.252 & 0.342 & 0.847 & In-distribution reference context. \\
Raw local utility & $-$0.077 & 0.282 & 0.722 & Direct ablation. \\
Graph-only Ridge & 0.043 & -- & -- & Same-supervision topology-only control. \\
Graph + position Ridge & 0.603 & -- & -- & Near-reference result driven by position. \\
\bottomrule
\end{tabular}
\end{table}

The same-supervision controls isolate the source of the signal. Graph-derived features alone reach $\rho=0.043$ with 95\% CI $[0.028,0.057]$. Adding trace-position fields raises the result to $\rho=0.603$ with CI $[0.596,0.609]$, close to \wstruct{} at $\rho=0.611$ with CI $[0.605,0.618]$. Direct mathematical-DAG necessity reaches $\rho=0.535$ and remains below the reverse-position baseline at $\rho=0.568$. Under equal supervision, graph topology therefore carries little independent PRM800K annotation-order signal; structural fields are organizational and interpretive on this distribution.

\subsection{Audit-Record Enrichment and Retrieval}
\label{sec:why-calibration}

The audit-target retrieval stage asks whether decomposition fields make rule-derived audit targets visible under a fixed budget. The scalar-only view receives \wstruct{}, the raw-field view exposes primitive fields, and the SC-FMA view exposes fidelity, necessity, redundancy, bottleneck status, recommended action, and interpretation fields. The lowest-direct-overlap target is weak utility anchor; redundancy, structural over-correction, and bottleneck protection have stronger definitional overlap with exposed fields.

Under the same 25\% budget, the raw-field bundle raises mean rule-target recall from 0.235 to 0.524 and mean NDCG from 0.353 to 0.768. The SC-FMA view further raises mean recall to 0.699 and mean NDCG to 0.978. These aggregate readouts are useful as machine-readable record-visibility checks, but they do not remove the definitional-overlap concern. The bottleneck row is QP-derived and is interpreted as an internal record-consistency check. Field-overlap audits and per-target point estimates are moved to Supplementary Section S3.

\subsection{Controlled Calibration and Ablation}

The controlled synthetic stage tests whether SCU behaves as intended when labels encode structural preferences. It is a mechanism check, not external audit-value evidence.

\begin{table}[!t]
\caption{Controlled calibration and component ablation summaries.}
\label{tab:controlled-ablation}
\centering
\small
\renewcommand{\arraystretch}{1.06}
\begin{tabular}{Z{0.31\linewidth}ccZ{0.32\linewidth}}
\toprule
\textbf{Check} & \textbf{Primary $\rho$} & \textbf{Delta} & \textbf{Interpretation} \\
\midrule
SC-FMA QP vs designed label & \textbf{0.597} $\pm$ 0.064 & +0.114 vs raw utility & Designed structural calibration check. \\
SC-FMA Ridge vs designed label & 0.541 $\pm$ 0.016 & +0.058 vs raw utility & Lightweight fidelity-tracking view. \\
Raw local utility & 0.483 & -- & Direct input baseline. \\
No fidelity term & 0.285 $\pm$ 0.015 & $-$0.225 & Largest component loss. \\
No structure term & 0.484 $\pm$ 0.033 & $-$0.026 & Moderate designed-stage contribution. \\
Stress-test: no bottleneck & 0.541 $\pm$ 0.015 & $-$0.084 & Bottleneck term becomes active under designed stress labels. \\
Stress-test: no redundancy & 0.576 $\pm$ 0.016 & $-$0.049 & Redundancy term matters under high-conflict labels. \\
\bottomrule
\end{tabular}
\end{table}

Table~\ref{tab:controlled-ablation} shows that fidelity remains the dominant component, while structural terms become more useful when labels encode redundancy or bottleneck preferences. This supports the mechanism-bearing role of QP under designed structural conflict, but it does not make QP the default real-data variant. Additional ablations, graph variants, window sweeps, and sensitivity grids are reported in Supplementary Section S3.

\subsection{Failure Modes}
\label{sec:prm800k-error}

Failure analysis identifies when structural calibration helps or hinders process-annotation consistency. Table~\ref{tab:failure-summary} reports the locked multi-label taxonomy.

\begin{table}[!t]
\caption{Failure taxonomy on the locked PRM800K split.}
\label{tab:failure-summary}
\centering
\small
\renewcommand{\arraystretch}{1.08}
\begin{tabular}{Z{0.45\linewidth}rrZ{0.24\linewidth}}
\toprule
\textbf{Failure label} & \textbf{Count} & \textbf{Percent} & \textbf{Record implication} \\
\midrule
\texttt{weak\_utility\_anchor} & 2,420 & 54.79\% & Repair upstream fidelity field. \\
\texttt{structural\_over\_correction} & 2,145 & 48.56\% & Check graph regularization. \\
\texttt{redundancy\_misclassification} & 1,214 & 27.48\% & Consolidate or split duplicated support. \\
\texttt{low\_signal\_or\_tie} & 809 & 18.32\% & Treat ranking as unstable. \\
\texttt{bottleneck\_over\_protection} & 382 & 8.65\% & Inspect QP-derived bottleneck floor. \\
\bottomrule
\end{tabular}
\end{table}

Trace length is a practical limitation for the full QP variant. On short traces, \wstruct{}, Ridge, and QP reach $\rho=0.759$, $0.757$, and $0.734$. On long traces, they drop to $0.447$, $0.430$, and $0.172$. A post hoc windowed diagnostic with $k_w=4$ raises the long-stratum QP result from $0.172$ to $0.385$, but the sweep was conducted after observing the locked-split failure and remains below Ridge and \wstruct{}. Detailed failure cases and audit-card examples are provided in Supplementary Section S5.

\section{Discussion}
\label{sec:discussion}

\subsection{Knowledge lifecycle interpretation}

Knowledge-intensive systems expose artifacts during construction, retrieval, validation, update, and reuse. The useful object for maintenance is not only a score but a record that travels with an artifact after scoring. SC-FMA contributes such a record: it states why an artifact was selected, which neighboring artifacts it depends on, and whether the selected evidence is duplicated or dependency-exposed.

The empirical evidence narrows this interpretation. Ridge remains close to the supplied PRM800K fidelity field, while graph-only controls show weak independent topology signal on that route. The contribution is therefore a reusable audit-record schema and fixed-budget visibility protocol, not a claim that graph calibration improves reasoning correctness or universally outperforms supplied fidelity fields.

\subsection{Audit records for maintenance-oriented analysis}

During maintenance, the audit record links a selected artifact to a practical reading: verify the fidelity field, inspect a dependency chain, consolidate duplicate evidence, or protect a bottleneck. Budget-constrained recall, NDCG, first-selected target, and Mass@25\% match this setting more directly than whole-trace correlation alone. The raw-field control also shows that field exposure explains a large share of the automatic retrieval signal; SC-FMA adds organization and interpretation, but this is not an independent retrieval-win result.

\subsection{Variant guidance and limitations}

Ridge is the conservative default when the supplied fidelity field is strong. QP-style checks are useful during development when fidelity and structure diverge, but the PRM800K long-trace stratum shows that global QP calibration can be brittle. Projection is retained as a lower-cost fallback rather than a preferred evidence route.

The current evidence supports audit-record construction and representation-level knowledge-engineering claims. It does not support production knowledge-base maintenance, human audit usefulness, downstream PRM training, external PRM generalization, or causal identification. SC-FMA does not identify causal effects. Human-in-the-loop comparison between scalar views, raw-field bundles, and SC-FMA records remains future validation.

\section{Conclusions}
\label{sec:conclusions}

This paper presented SC-FMA as an artifact representation and audit-record construction framework for knowledge-intensive information systems. It converts supplied fidelity and structural fields into records with explicit dependency, redundancy, bottleneck, reason, and interpretation fields.

The decisive evidence is bounded. On the locked PRM800K route, SC-FMA Ridge closely tracks but does not improve over the supervised \wstruct{} fidelity field. Graph-only structure is weak under the same supervision, and direct mathematical-DAG necessity remains below a reverse-position baseline. In the KG/RAG audit simulation, rule-only records are strongest when targets are directly observable. These findings support a knowledge-maintenance reading: SC-FMA organizes exposed artifacts into reusable audit records under fixed budgets, while leaving production validation, human audit usefulness, and cross-domain transfer for future work.

\noindent\textbf{Boundary note.} No returned human ratings are available. The blind human-evaluation protocol is prepared, but no returned human ratings are reported.

\section*{Acknowledgments}
The authors thank the College of Management Science and Engineering at Beijing Information Science and Technology University for research support.

\section*{Funding}
This work was supported by the National Social Science Fund of China Project (24BSH018) and the Beijing Natural Science Foundation Project (L252145).

\section*{Declaration of Competing Interest}
The authors declare that they have no conflicts of interest related to this work.

\section*{Declaration of generative AI and AI-assisted technologies in the writing process}
During the preparation of this work, the authors used OpenAI GPT-5 to improve language clarity and assist with LaTeX formatting checks. The tool was not used to design the study, conduct data analysis, generate results, or derive the conclusions. After using this tool, the authors reviewed and edited the content as needed and take full responsibility for the content of the publication.

\section*{Data Availability}
The PRM800K process-annotation dataset, MuSiQue, and WebQSP are publicly available from their original sources. Derived locked-split reports, audit-record outputs, validation configurations, and reproduction scripts will be made available through an anonymous review repository during submission and released with the final article where permitted.

\section*{CRediT authorship contribution statement}
\textbf{Haoran Ma}: Conceptualization, Methodology, Software, Formal analysis, Investigation, Data Curation, Writing -- Original Draft, Visualization. \textbf{Ningning Wang}: Methodology, Validation, Writing -- Review \& Editing, Supervision, Project administration, Funding acquisition.

\bibliography{references}

\end{document}
"""
    )


def supplementary_tex(old_main: str, old_supp: str) -> str:
    moved_tables = {
        "alternative": extract_table_any("tab:alternative-representation-comparison", old_main, old_supp),
        "notation": extract_table_any("tab:notation", old_main, old_supp),
        "complexity": extract_table_any("tab:complexity-summary", old_main, old_supp),
        "memory": extract_table_any("tab:memory-summary", old_main, old_supp),
        "enrichment": extract_table_any("tab:representation-enrichment", old_main, old_supp),
        "category": extract_table_any("tab:audit-category-separation", old_main, old_supp),
        "kg": extract_table_any("tab:kg-pilot", old_main, old_supp),
        "overlap": extract_table_any("tab:target-circularity-audit", old_main, old_supp),
        "per_target": extract_table_any("tab:oracle-auto-validation-by-target", old_main, old_supp),
        "aggregate": extract_table_any("tab:oracle-auto-validation", old_main, old_supp),
        "component": extract_table_any("tab:scu-component-contribution", old_main, old_supp),
        "stress": extract_table_any("tab:scu-stress-test", old_main, old_supp),
        "graph": extract_table_any("tab:graph-construction-analysis", old_main, old_supp),
        "supp_eff": extract_table_any("tab:supp-efficiency", old_supp, old_main),
        "supp_hyper": extract_table_any("tab:supp-hyperparameters", old_supp, old_main),
        "gamma_delta": extract_table_any("tab:supp-gamma-delta-sensitivity", old_supp, old_main),
        "alpha_beta": extract_table_any("tab:supp-alpha-beta-sensitivity", old_supp, old_main),
        "per_size": extract_table_any("tab:per-size", old_supp, old_main),
        "webqsp": extract_table_any("tab:supp-webqsp-diagnostic", old_supp, old_main),
        "musique": extract_table_any("tab:supp-musique-knowledge-audit", old_supp, old_main),
        "independence": extract_table_any("tab:oracle-independence", old_supp, old_main),
    }
    moved_tables = {
        name: clean_supplementary_block(block)
        for name, block in moved_tables.items()
    }
    alg_struct = extract_algorithm(old_supp, "alg:supp-structural-necessity")
    alg_qp = extract_algorithm(old_supp, "alg:supp-scfma-qp")

    return (
        preamble(TITLE, supplementary=True)
        + r"""
\maketitle

\section{S1. Mathematical Details}
\label{sec:s1-math}

This section gives the derivations moved out of the main manuscript. The SCU objective minimizes Eq.~(2) in the main text over the probability simplex, combining fidelity preservation, structural alignment, redundancy regularization, and bottleneck protection.

The Karush--Kuhn--Tucker conditions for the constrained optimization problem are
\begin{align}
\frac{\partial L}{\partial w_i}\bigg|_{\mathbf{w}^*} - \mu_i^* - \lambda^* &= 0, \quad \forall i,\\
\mu_i^* &\ge 0, \quad \forall i,\\
\mu_i^*(w_i^* - \varepsilon) &= 0, \quad \forall i,\\
w_i^* &\ge \varepsilon, \quad \forall i,\\
\sum_{i=1}^k w_i^* &= 1.
\end{align}
Writing $\mathbf{R}_{s}=(\mathbf{R}+\mathbf{R}^{\top})/2$, the quadratic term satisfies $\mathbf{w}^{\top}\mathbf{R}\mathbf{w}=\mathbf{w}^{\top}\mathbf{R}_{s}\mathbf{w}$, so its gradient contribution is $2\gamma\mathbf{R}_{s}\mathbf{w}$. The partial derivative is
\begin{equation}
\partial L / \partial w_i = 2\alpha(w_i - \tilde{c}_i) + 2\beta(w_i - \tilde{n}_i) + 2\gamma(\mathbf{R}_{s}\mathbf{w})_i - \delta b_i / w_i.
\end{equation}

\begin{theorem}[SCU well-posedness]
Let $\mathbf{R}_{s}=(\mathbf{R}+\mathbf{R}^{\top})/2$ and let $\mathcal{T}=\{\mathbf{z}\in\mathbb{R}^{k}:\mathbf{1}^{\top}\mathbf{z}=0\}$ be the tangent subspace of the simplex. Define $\mathbf{H}_{q}=2((\alpha+\beta)\mathbf{I}+\gamma\mathbf{R}_{s})$. If $\alpha,\beta,\gamma,\delta \ge 0$ and $\mathbf{z}^{\top}\mathbf{R}_{s}\mathbf{z}\ge 0$ for every $\mathbf{z}\in\mathcal{T}$, the SCU objective is convex on the relative interior of the simplex. If $\mathbf{z}^{\top}\mathbf{H}_{q}\mathbf{z}>0$ for every nonzero $\mathbf{z}\in\mathcal{T}$, the quadratic part is strictly convex on the feasible subspace and the minimizer is unique.
\end{theorem}

The monotonicity statement used for interpretation is local. For non-redundant artifact-unit pairs with identical redundancy profiles and inputs ordered in the same direction, $\tilde c_i\ge \tilde c_j$ and $\tilde n_i\ge \tilde n_j$ imply the corresponding two-input priority relation before redundancy-induced redistribution. Once redundancy profiles differ, the $\gamma$ term deliberately can violate monotonicity because redundant artifacts compete for the same fixed audit budget.

The two-term objective $L_2(\mathbf{w})=\alpha\|\mathbf{w}-\tilde{\mathbf{c}}\|_2^2+\beta\|\mathbf{w}-\tilde{\mathbf{n}}\|_2^2$ has unconstrained minimizer
\begin{equation}
\hat{\mathbf{w}} = \frac{\alpha\tilde{\mathbf{c}}+\beta\tilde{\mathbf{n}}}{\alpha+\beta}.
\end{equation}
The full QP adds redundancy and bottleneck terms to this fidelity/structure interpolation. These derivations support numerical well-posedness only; empirical validation comes from the staged evaluations in the main manuscript.

\section{S2. Implementation Details}
\label{sec:s2-implementation}

SC-FMA takes normalized artifact sequences, constructs temporal and optional topical or domain-specific edges, computes fidelity and structural fields, and emits audit records. Table~\ref{tab:notation} defines the compact notation used by the objective.

"""
        + moved_tables["notation"]
        + "\n\n"
        + (alg_struct or "")
        + "\n\n"
        + (alg_qp or "")
        + r"""

Table~\ref{tab:supp-hyperparameters} lists the controlled-stage hyperparameter grid. These settings are representation controls rather than universal tuning rules.

"""
        + moved_tables["supp_hyper"]
        + r"""

The reproducibility commands are:
\begin{itemize}
\item \textbf{Same-supervision structure-only control:} \path{python scripts/run_structure_only_baseline.py}. The graph-only result is $\rho=0.043$ (95\% CI $[0.028,0.057]$); adding position gives $\rho=0.603$, compared with $\rho=0.611$ for \wstruct{}.
\item \textbf{Direct graph-necessity diagnostic:} \path{python scripts/run_prm800k_graph_necessity.py}. TF-IDF necessity is undifferentiated ($\rho\approx0$); mathematical-DAG necessity reaches $\rho=0.535$ and remains below reverse position at $\rho=0.568$.
\item \textbf{Windowed QP diagnostic:} \path{python scripts/run_windowed_calibration_analysis.py}. At $k_w=4$, the middle and long trace-length strata rise from $0.321$ to $0.561$ and from $0.172$ to $0.385$, respectively; this is post hoc locked-split failure analysis.
\item \textbf{Oracle auto audit-target validation:} \path{python scripts/run_audit_card_auto_validation.py}. Targets are rule-derived, not human adjudications.
\item \textbf{Human-evaluation boundary:} no human-rater experiment is included in the active evidence package. A valid future study requires real evaluator provenance, original returned CSV files, hashes, declarations, and reliability analysis.
\end{itemize}

\section{S3. Additional Experiments}
\label{sec:s3-additional}

This section retains tables and diagnostic results moved from the main text. They are supplementary evidence only and do not change the manuscript's claim boundary.

\subsection{Output objects and representation enrichment}
"""
        + moved_tables["alternative"]
        + "\n\n"
        + moved_tables["enrichment"]
        + "\n\n"
        + moved_tables["category"]
        + r"""

\subsection{Audit-target retrieval details}

The rule-derived target families differ in definitional overlap with SC-FMA fields. Bottleneck protection is QP-derived and is treated as an internal consistency check, not independent retrieval validation.

"""
        + moved_tables["overlap"]
        + "\n\n"
        + moved_tables["per_target"]
        + "\n\n"
        + moved_tables["aggregate"]
        + r"""

\subsection{Controlled ablations and sensitivity}
"""
        + moved_tables["component"]
        + "\n\n"
        + moved_tables["stress"]
        + "\n\n"
        + moved_tables["per_size"]
        + "\n\n"
        + moved_tables["gamma_delta"]
        + "\n\n"
        + moved_tables["alpha_beta"]
        + r"""

\subsection{Graph and backend diagnostics}
"""
        + moved_tables["graph"]
        + "\n\n"
        + moved_tables["kg"]
        + r"""

The Countries-KG fixture uses 30 deterministic traces over 30 entities and 189 triples. It supports typed backend substitution and exposes structural-necessity sensitivity; it is not production knowledge-graph validation.

\begin{figure}[!t]
\centering
\includegraphics[width=\linewidth]{figures/fig_redundancy_comp.png}
\caption{Redundancy density and compensation analysis. Panel (a) reports per-trace redundancy density; panel (b) reports per-node compensation ratio under PRUNE mode.}
\label{fig:redundancy-comp}
\end{figure}

\subsection{Boundary diagnostics}
"""
        + moved_tables["webqsp"]
        + "\n\n"
        + moved_tables["musique"]
        + "\n\n"
        + moved_tables["independence"]
        + r"""

The WebQSP diagnostic is fixed-schema trace-audit evidence only. MuSiQue is a constructed-label feasibility demonstration because labels and representation features are deterministic functions of step type. Earlier GSM8K and HotpotQA routes failed or were blocked and are retained only for transparency.

\section{S4. Complexity and Efficiency}
\label{sec:s4-complexity}

The main text reports only the reproducibility-critical runtime summary. The detailed asymptotic and memory tables are retained here.

"""
        + moved_tables["complexity"]
        + "\n\n"
        + moved_tables["memory"]
        + "\n\n"
        + moved_tables["supp_eff"]
        + r"""

The process-annotation audit-record construction run over 4,417 traces and 34,219 labeled artifacts completed in 131.57\,s on a 12-core CPU. This value is an archived wall-clock trace, not a comparative efficiency claim against live model-based attribution methods.

\section{S5. Failure Taxonomy}
\label{sec:s5-failure}

The locked PRM800K failure taxonomy is multi-label, so percentages need not sum to 100\%. The main text summarizes these counts; the audit-card templates below preserve detailed examples for future human-in-the-loop study design.

\par\medskip
\refstepcounter{table}\label{tab:failure-taxonomy}
\noindent\textbf{Table~\thetable}\par
\noindent Rule-based failure taxonomy distribution on the locked PRM800K split.
\begin{center}
\small
\renewcommand{\arraystretch}{1.08}
\begin{tabular}{lrr}
\toprule
\textbf{Label} & \textbf{Count} & \textbf{Percentage} \\
\midrule
\texttt{structural\_over\_correction} & 2145 & 48.56\% \\
\texttt{redundancy\_misclassification} & 1214 & 27.48\% \\
\texttt{bottleneck\_over\_protection} & 382 & 8.65\% \\
\texttt{weak\_utility\_anchor} & 2420 & 54.79\% \\
\texttt{low\_signal\_or\_tie} & 809 & 18.32\% \\
\bottomrule
\end{tabular}
\end{center}

Audit Card 1 records bottleneck-protected structural over-correction on trace \texttt{prm800k\_pool\_010077\_26cf715105}: a below-maximum label step receives the largest QP priority-field value because of bottleneck protection. The interpretation is to inspect whether the protected reinterpretation is a true downstream dependency or an over-protected detour.

Audit Card 2 records redundancy over-merging on trace \texttt{prm800k\_pool\_012035\_e6055a1cb2}: high redundancy density causes QP to reallocate mass away from several high-label setup steps. The interpretation is to check whether asymptote identification, intercept checks, and coordinate-swap verification are separate audit units or one redundant cluster.

Audit Card 3 records a weak local-utility anchor on trace \texttt{prm800k\_pool\_006217\_43f4f279ef}: raw local utility assigns the largest signal to a false step, while \wstruct{}, QP, and Ridge prioritize the midpoint-altitude step. The interpretation is to repair the upstream utility anchor and avoid treating raw utility as an independent audit target.

\bibliography{references}

\end{document}
"""
    )


def moved_inventory() -> str:
    return """# Moved or Compressed Content Inventory

## Moved from manuscript to supplementary
- Notation table -> Supplementary Section S2.
- SCU well-posedness theorem, KKT conditions, convexity and monotonicity discussion -> Supplementary Section S1.
- Structural-necessity and QP pseudocode -> Supplementary Section S2.
- Hyperparameter grid and parameter-selection details -> Supplementary Section S2.
- Complexity and memory tables -> Supplementary Section S4.
- Alternative representation table -> Supplementary Section S3.
- Representation enrichment and audit-category separation tables -> Supplementary Section S3.
- Countries-KG detailed backend table -> Supplementary Section S3.
- Field-overlap audit, per-target retrieval, and aggregate retrieval tables -> Supplementary Section S3.
- Controlled component contribution, stress-test, per-size, and sensitivity tables -> Supplementary Section S3.
- WebQSP, MuSiQue, proxy-label independence, and other boundary diagnostics -> Supplementary Section S3.
- Detailed failure cards -> Supplementary Section S5.

## Removed or compressed in manuscript
- Long figure explanations were compressed into short captions and short interpretive text.
- Repeated PRM800K and graph-weakness explanations were consolidated into one evaluation paragraph and one limitations paragraph.
- The old Discussion repeated result-level explanations; it now focuses on knowledge lifecycle, maintenance-oriented audit records, variant guidance, and limitations.

## Preserved in manuscript
- Core SCU equations and variant roles.
- Main PRM800K numbers and same-supervision controls.
- KG/RAG fixed-budget audit results.
- Controlled calibration summary.
- Failure taxonomy counts.
- Explicit claim boundaries.
"""


def sync_package() -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for path in PACKAGE.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    for name in (
        "manuscript.tex",
        "supplementary.tex",
        "manuscript.pdf",
        "supplementary.pdf",
        "references.bib",
        "sn-jnl.cls",
        "sn-mathphys-num.bst",
        "sn-basic.bst",
        "sn-nature.bst",
    ):
        src = SOURCE / name
        if src.exists():
            shutil.copy2(src, PACKAGE / name)
    package_figures = PACKAGE / "figures"
    package_figures.mkdir(parents=True, exist_ok=True)
    for fig in (SOURCE / "figures").glob("*"):
        if fig.is_file():
            shutil.copy2(fig, package_figures / fig.name)
    clean_builds(PACKAGE)


def main() -> int:
    old_main_path = richer_source(
        SOURCE / "manuscript.tex",
        PACKAGE / "manuscript.tex",
        table_threshold=10,
    )
    old_supp_path = richer_source(
        SOURCE / "supplementary.tex",
        PACKAGE / "supplementary.tex",
        table_threshold=8,
    )
    old_main = read(old_main_path)
    old_supp = read(old_supp_path)
    baseline_pages = {
        "manuscript_pages_before": page_count(SOURCE / "manuscript.pdf"),
        "supplementary_pages_before": page_count(SOURCE / "supplementary.pdf"),
    }
    write(REPORTS / "page_count_change_jiis_compression.json", json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **baseline_pages,
        "manuscript_pages_after": None,
        "supplementary_pages_after": None,
        "status": "source_rewritten_pending_compile",
    }, indent=2))
    write(SOURCE / "manuscript.tex", manuscript_tex())
    write(SOURCE / "supplementary.tex", supplementary_tex(old_main, old_supp))
    write(REPORTS / "moved_content_inventory.md", moved_inventory())
    clean_builds(SOURCE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
