"""Rebuild the JIIS submission from the full Information Sciences manuscript.

This is the corrective migration path: preserve the full paper body, figures,
tables, and evidence sections from the current Information Sciences source,
while adapting only the venue template, title/framing, claim boundaries, and
the new JIIS audit-case insertion.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "paper" / "information_sciences_submission" / "final_source"
JIIS = ROOT / "paper" / "JIIS_submission"
SOURCE = JIIS / "source"
PACKAGE = JIIS / "submission_package"
REPORTS = JIIS / "reports"
HUMAN = JIIS / "human_eval_pending"
TITLE = "Dependency-Aware Audit Records for Fixed-Budget Inspection of Knowledge-Intensive Information Systems"


BUILD_SUFFIXES = (
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
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def strip_tex_root(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("% !TEX root")
    ).strip()


def sanitize_references(src: Path, dst: Path) -> None:
    text = read(src)
    # Springer bst can emit fragile \burl entries for URLs containing percent signs.
    text = re.sub(r"\n\s*url\s*=\s*\{[^{}]*\},?", "", text)
    write(dst, text)


def normalize_latex(text: str) -> str:
    text = strip_tex_root(text)
    text = text.replace("[pos=ht]", "[ht]")
    text = text.replace("[H]", "[ht]")
    text = re.sub(r"\\bibliographystyle\{[^{}]+\}", "", text)
    text = re.sub(r"\\bibliography\{[^{}]+\}", "", text)
    text = text.replace("\\end{document}", "")
    text = text.replace(
        "Structurally-Calibrated Functional Metacognitive Attribution for Audit Prioritization in Knowledge-Intensive Reasoning",
        TITLE,
    )
    text = text.replace(
        "This paper introduces Structurally-Calibrated Functional Metacognitive Attribution (SC-FMA) as a knowledge representation transformation layer for this setting.",
        "This paper introduces a dependency-aware audit-record framework as a knowledge representation transformation layer for this setting.",
    )
    text = text.replace(
        "SC-FMA transforms intermediate knowledge artifacts into structured audit records",
        "The framework transforms intermediate knowledge artifacts into structured audit records",
    )
    text = text.replace(
        "SC-FMA organizes fixed-budget audit around a structured record.",
        "The audit-record framework organizes fixed-budget audit around a structured record.",
    )
    text = text.replace(
        "Second, it introduces SC-FMA and the SCU objective",
        "Second, it retains the historical SC-FMA implementation and SCU objective as calibration components",
    )
    text = text.replace(
        "Figure~\\ref{fig:overall-framework} gives the high-level knowledge-engineering workflow. SC-FMA sits between raw knowledge artifacts and potential review workflows:",
        "Figure~\\ref{fig:overall-framework} gives the high-level knowledge-engineering workflow. Dependency-aware audit-record construction sits between raw knowledge artifacts and potential review workflows:",
    )
    text = text.replace(
        "\\caption{Knowledge engineering workflow for SC-FMA.",
        "\\caption{Knowledge engineering workflow for dependency-aware audit records.",
    )
    text = text.replace(
        "\\section{Knowledge Engineering Representation Checks}",
        "\\section{Evaluation}",
    )
    text = text.replace(
        "SC-FMA targets a decomposed audit record",
        "The proposed framework targets a decomposed audit record",
    )
    text = text.replace(
        "SC-FMA combines them into a representation layer",
        "The proposed framework combines them into a representation layer",
    )
    text = text.replace("Appendix~\\ref{app:failure-taxonomy}", "the supplementary failure-taxonomy appendix")
    text = text.replace("Appendix \\ref{app:failure-taxonomy}", "the supplementary failure-taxonomy appendix")
    text = text.replace("Appendix~\\ref{app:failure-taxonomy}'s", "the supplementary failure-taxonomy appendix's")
    text = re.sub(
        r"Table~\\ref\{tab:compact-audit-card-case\} gives one compact preview case; the appendix Audit Cards provide fuller trace-level examples\.",
        "Compact Audit Card examples are retained in the supplementary failure-taxonomy appendix.",
        text,
    )
    text = re.sub(
        r"\n\\begin\{table\}\[ht\]\n\\caption\{Compact Audit Card case study: scalar-only view versus SC-FMA decomposition\.\}.*?\\end\{table\}\n",
        "\n",
        text,
        flags=re.S,
    )
    text = re.sub(
        r"Table~\\ref\{tab:variant-policy\} converts the stratified diagnosis into observed development patterns, not a prospectively validated selector\..*?\\end\{table\}\n",
        (
            "The stratified diagnosis yields observed development patterns rather than a prospectively validated selector. "
            "Ridge is the conservative default when the supplied fidelity field is strong; QP-style checks are useful during development when fidelity and structure diverge, but the PRM800K long-trace stratum shows that global QP calibration can be brittle. "
            "The detailed post-hoc variant-selection table is retained in the supplementary material.\n"
        ),
        text,
        flags=re.S,
    )
    text = text.replace(
        "The active anonymous review repository link is supplied in the Elsevier submission metadata. ",
        "",
    )
    text = text.replace(
        "Derived locked-split reports, audit-record outputs, trace-audit checks, validation configurations, and reproduction scripts will be made available through an anonymous review repository during submission and released with the final article where permitted. The review package is intended to contain split manifests, locked JSON/CSV reports, audit-record outputs, source-code entry points, configuration snapshots, and reproduction commands. Full commands, local raw-data expectations, output paths, and scope notes are documented in the supplementary reproducibility checklist.",
        "Derived locked-split reports, audit-record outputs, validation configurations, and reproduction scripts will be made available through an anonymous review repository during submission and released with the final article where permitted.",
    )
    text = text.replace(
        "Causal effect estimates would require a separate identification design.",
        "The framework does not identify causal effects; causal identification would require a separate design.",
    )
    return text


def use_two_column_floats(text: str) -> str:
    """Keep Springer double-column layout without forcing float-page overflow."""
    # The sn-jnl iicol option already makes the article body double-column.
    # Forcing many table*/figure* floats pushes content to extra float pages.
    # Keep local floats here; targeted float polishing can be done manually after
    # visual review without changing the main migration contract.
    return text


def abstract_text() -> str:
    return (
        "Knowledge-intensive information systems expose process annotations, "
        "retrieval checks, entity bindings, graph nodes, and verification records. "
        "Curators inspect these artifacts under fixed audit budgets and need reusable "
        "records that make supplied fidelity fields explicit while showing dependency, "
        "redundancy, bottleneck exposure, and interpretive role. We introduce a "
        "dependency-aware audit-record framework for converting observable process "
        "artifacts into queryable inspection records. The historical SC-FMA module "
        "is retained as an internal calibration component through the "
        "Structurally-Calibrated Utility objective. On a locked PRM800K-derived "
        "process-annotation distribution (4,417 samples; 34,219 labeled artifacts), "
        "the supervised \\wstruct{} fidelity field remains strongest (Spearman "
        "$\\rho=0.611$), while the calibrated Ridge record tracks it with a small "
        "loss ($\\rho=0.604$) and adds decomposed record fields. Graph-derived "
        "features alone reach only $\\rho=0.043$ under the same supervision, and a "
        "mathematical dependency DAG remains below a reverse-position baseline. A "
        "new KG/RAG-style audit simulation shows that direct rule-only records are "
        "strongest when audit targets are explicitly observable, while dependency-aware "
        "records remain competitive with raw-field and diversity baselines. The "
        "evidence supports record organization and fixed-budget visibility, not "
        "production knowledge-base validation, human audit usefulness, cross-domain "
        "transfer, or causal identification."
    )


def audit_case_section() -> str:
    report = json.loads(
        read(REPORTS / "jiis_audit_case" / "jiis_audit_case_report.json")
    )
    methods = report["methods"]

    def row(name: str, label: str) -> str:
        item = methods[name]
        return (
            f"{label} & "
            f"{item['recall_at_budget']['mean']:.3f} & "
            f"{item['ndcg_at_budget']['mean']:.3f} & "
            f"{item['top1_hit']['mean']:.3f} & "
            f"{item['mass_at_budget']['mean']:.3f} \\\\"
        )

    return f"""
\\subsection{{Independent KG/RAG Audit-Record Case}}
\\label{{sec:jiis-audit-case}}

To align the JIIS version with knowledge-intensive information systems, we add an independent KG/RAG-style audit-record case. The case is a representative trace simulation with observable entity-binding, evidence-support, duplicate-support, dependency-bottleneck, and temporal-conflict fields. Audit targets are generated before method scoring and do not use SCU weights or dependency-aware recommendations. The experiment contains {report['n_traces']:,} traces and {report['n_steps']:,} steps under the same 25\\% fixed budget used by the rest of the paper. They do not establish production knowledge-base validation or human audit usefulness.

\\begin{{table}}[ht]
\\caption{{Independent KG/RAG-style audit-record case under a 25\\% budget. The rule-only record is strongest because several targets are directly observable; this result supports target visibility and record organization, not a superiority or human-usefulness claim.}}
\\label{{tab:jiis-audit-case}}
\\centering
\\small
\\renewcommand{{\\arraystretch}}{{1.06}}
\\begin{{tabular}}{{Z{{0.28\\linewidth}}rrrr}}
\\toprule
\\textbf{{Method}} & \\textbf{{Recall}} & \\textbf{{NDCG}} & \\textbf{{Top-1}} & \\textbf{{Mass}} \\\\
\\midrule
{row('scalar_fidelity', 'Scalar fidelity')}
{row('raw_field_bundle', 'Raw-field bundle')}
{row('position_last_step', 'Position / last-step')}
{row('graph_centrality', 'Graph centrality')}
{row('pagerank_like', 'PageRank-like')}
{row('mmr_diversity', 'MMR diversity')}
{row('rule_only_record', 'Rule-only record')}
{row('dependency_aware_record', 'Dependency-aware record')}
\\bottomrule
\\end{{tabular}}
\\end{{table}}

The result is deliberately bounded. Rule-only records achieve the highest fixed-budget visibility because the targets are generated from observable audit fields. Dependency-aware records are close to the raw-field bundle and MMR diversity, but they do not dominate direct rules. We therefore use this case to show that audit targets can be represented and queried under a shared budget, while keeping human audit usefulness and production deployment as future validation.
"""


def insert_audit_case(evaluation: str) -> str:
    anchor = "\\subsection{Task Definition: Fixed-Budget Knowledge Audit}"
    if anchor not in evaluation:
        return evaluation + "\n\n" + audit_case_section()
    return evaluation.replace(anchor, audit_case_section().strip() + "\n\n" + anchor, 1)


def build_main() -> str:
    sections_dir = OLD / "sections"
    intro = normalize_latex(read(sections_dir / "intro.tex"))
    related = normalize_latex(read(sections_dir / "related.tex"))
    method = normalize_latex(read(sections_dir / "method.tex"))
    evaluation = insert_audit_case(normalize_latex(read(sections_dir / "representation_checks.tex")))
    discussion = normalize_latex(read(sections_dir / "discussion.tex"))
    conclusions = normalize_latex(read(sections_dir / "conclusions.tex"))
    tail_files = [
        "acknowledgments.tex",
        "funding.tex",
        "competing_interest.tex",
        "ai_declaration.tex",
        "data_availability.tex",
        "credit.tex",
    ]
    tail = "\n\n".join(normalize_latex(read(sections_dir / name)) for name in tail_files)
    tail = tail.replace(
        "human-in-the-loop validation should expose SC-FMA records",
        "human-in-the-loop validation should expose dependency-aware audit records",
    )

    preamble = """
% !TEX root = ./manuscript.tex
% JIIS / Springer Nature sn-article manuscript package.
% Full migration from the Information Sciences source; not a compressed rewrite.
\\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}

\\usepackage{graphicx}
\\usepackage{multirow}
\\usepackage{amsmath,amssymb,amsfonts}
\\usepackage{amsthm}
\\usepackage{booktabs}
\\usepackage{array}
\\usepackage{xurl}
\\usepackage{algorithm}
\\usepackage{algorithmicx}
\\usepackage{algpseudocode}
\\usepackage{makecell}
\\usepackage{placeins}
\\usepackage{float}
\\usepackage{textcomp}

\\newtheorem{theorem}{Theorem}[section]
\\newtheorem{lemma}[theorem]{Lemma}
\\newtheorem{corollary}[theorem]{Corollary}
\\newcolumntype{Z}[1]{>{\\raggedright\\arraybackslash}p{#1}}
\\newcommand{\\wstruct}{\\ensuremath{\\mathbf{w}_{\\mathrm{struct}}}}

\\raggedbottom
\\begin{document}

\\title[Dependency-Aware Audit Records]{@@TITLE@@}

\\author*[1]{\\fnm{Haoran} \\sur{Ma}}\\email{mahaoran0000@foxmail.com}
\\author[1,2]{\\fnm{Ningning} \\sur{Wang}}\\email{wangningning@bistu.edu.cn}

\\affil*[1]{\\orgdiv{College of Management Science and Engineering}, \\orgname{Beijing Information Science and Technology University}, \\orgaddress{\\city{Beijing}, \\postcode{102200}, \\country{China}}}
\\affil[2]{\\orgdiv{Institute of Information Systems, ESG Intelligent Application Innovation Research Center}, \\orgname{Beijing Information Science and Technology University}, \\orgaddress{\\city{Beijing}, \\postcode{102200}, \\country{China}}}

\\abstract{@@ABSTRACT@@}

\\keywords{knowledge-intensive information systems, audit records, knowledge graphs, retrieval-augmented generation, fixed-budget inspection, process annotation}

\\maketitle
"""
    preamble = preamble.replace("@@TITLE@@", TITLE).replace("@@ABSTRACT@@", abstract_text())
    declarations_note = """
\\noindent\\textbf{Boundary note.} No returned human ratings are available. The blind human-evaluation protocol is prepared, but no returned human ratings are reported; extended cards, runtime metadata, and reproducibility notes are retained in the supplementary material.
"""
    manuscript = "\n\n".join(
        [
            preamble,
            intro,
            related,
            method,
            evaluation,
            discussion,
            conclusions,
            declarations_note,
            tail,
            "\\bibliography{references}",
            "\\end{document}",
        ]
    )
    return use_two_column_floats(manuscript)


def build_supplementary() -> str:
    old = read(OLD / "supplementary.tex")
    old = old.replace("[pos=ht]", "[ht]").replace("[H]", "[ht]")
    match = re.search(r"\\maketitle\s*(.*)\\bibliographystyle\{[^{}]+\}\s*\\bibliography\{references\}\s*\\end\{document\}", old, flags=re.S)
    if match:
        body = match.group(1)
    else:
        body = re.search(r"\\begin\{document\}(.*)\\end\{document\}", old, flags=re.S).group(1)
    body = strip_tex_root(body)
    preamble = """
% !TEX root = ./supplementary.tex
\\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}
\\usepackage{graphicx}
\\usepackage{multirow}
\\usepackage{amsmath,amssymb,amsfonts}
\\usepackage{booktabs}
\\usepackage{array}
\\usepackage{xurl}
\\usepackage{algorithm}
\\usepackage{algorithmicx}
\\usepackage{algpseudocode}
\\usepackage{makecell}
\\usepackage{float}
\\newcolumntype{Z}[1]{>{\\raggedright\\arraybackslash}p{#1}}
\\newcommand{\\wstruct}{\\ensuremath{\\mathbf{w}_{\\mathrm{struct}}}}
\\raggedbottom
\\begin{document}
\\title[Supplementary Material]{Supplementary Material for ``@@TITLE@@''}
\\author*[1]{\\fnm{Haoran} \\sur{Ma}}\\email{mahaoran0000@foxmail.com}
\\author[1,2]{\\fnm{Ningning} \\sur{Wang}}\\email{wangningning@bistu.edu.cn}
\\affil*[1]{\\orgdiv{College of Management Science and Engineering}, \\orgname{Beijing Information Science and Technology University}, \\orgaddress{\\city{Beijing}, \\postcode{102200}, \\country{China}}}
\\affil[2]{\\orgdiv{Institute of Information Systems, ESG Intelligent Application Innovation Research Center}, \\orgname{Beijing Information Science and Technology University}, \\orgaddress{\\city{Beijing}, \\postcode{102200}, \\country{China}}}
\\maketitle
"""
    preamble = preamble.replace("@@TITLE@@", TITLE)
    appendix = normalize_latex(read(OLD / "sections" / "appendix.tex"))
    extra = """
\\section{JIIS audit-case reproducibility note}
The independent JIIS audit case is generated by \\path{scripts/run_jiis_audit_case.py}. Its locked outputs are stored under \\path{paper/JIIS_submission/reports/jiis_audit_case}. The case is a representative trace simulation for fixed-budget audit-record visibility and does not constitute production knowledge-base validation or human audit evidence.

\\section{Variant-selection development note}
The main article summarizes the observed variant-selection evidence. Table~\\ref{tab:variant-policy-supp} records the post-hoc development patterns used to interpret Ridge, QP, and Projection variants. These thresholds are not a prospectively validated selector.

\\begin{table}[ht]
\\caption{Observed Ridge/QP development patterns derived from the stratified analysis. Thresholds are post-hoc development-set heuristics from the present evidence package, not a prospectively validated selection rule.}
\\label{tab:variant-policy-supp}
\\centering
\\small
\\renewcommand{\\arraystretch}{1.08}
\\begin{tabular}{Z{0.32\\linewidth}Z{0.42\\linewidth}Z{0.16\\linewidth}}
\\toprule
\\textbf{Setting} & \\textbf{Development check} & \\textbf{Recommendation} \\\\
\\midrule
Well-aligned fidelity field, as in process-annotation distributions & Fidelity-field annotation-order consistency is high on development data (roughly $\\rho \\ge 0.50$ here), and Ridge remains within about 0.02 Spearman of that field. & Ridge \\\\
Weak or structurally blind fidelity field & Fidelity consistency is low (roughly $\\rho < 0.30$), simple feature averaging fails, or stress-test/component ablations show structural-term removals changing development Spearman by at least 0.03. & Evaluate QP first \\\\
Unclear structure or runtime-critical setting & Structural checks are immature, or iterative QP calibration exceeds the available runtime budget. & Ridge; Projection as fast fallback \\\\
\\bottomrule
\\end{tabular}
\\end{table}
"""
    return "\n\n".join([preamble, extra, body, appendix, "\\bibliography{references}", "\\end{document}"])


def clean_builds(directory: Path) -> None:
    for suffix in BUILD_SUFFIXES:
        for path in directory.glob(f"*{suffix}"):
            path.unlink(missing_ok=True)


def compile_tex(tex: Path) -> tuple[int, str]:
    clean_builds(tex.parent)
    proc = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex.name],
        cwd=tex.parent,
        text=True,
        capture_output=True,
        timeout=240,
    )
    return proc.returncode, proc.stdout + proc.stderr


def build_package() -> None:
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
    for figure in sorted((SOURCE / "figures").glob("*")):
        if figure.is_file():
            shutil.copy2(figure, PACKAGE / figure.name)
    clean_builds(PACKAGE)


def page_count(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def main() -> int:
    SOURCE.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (SOURCE / "figures").mkdir(exist_ok=True)
    for fig in (OLD / "figures").glob("*"):
        if fig.is_file():
            shutil.copy2(fig, SOURCE / "figures" / fig.name)
    for name in ("sn-jnl.cls", "sn-mathphys-num.bst", "sn-basic.bst", "sn-nature.bst"):
        if not (SOURCE / name).exists():
            shutil.copy2(JIIS / "source" / name, SOURCE / name)
    sanitize_references(OLD / "references.bib", SOURCE / "references.bib")
    write(SOURCE / "manuscript.tex", build_main())
    write(SOURCE / "supplementary.tex", build_supplementary())

    logs: dict[str, str] = {}
    for name in ("manuscript.tex", "supplementary.tex"):
        code, log = compile_tex(SOURCE / name)
        logs[name] = log[-12000:]
        if code != 0:
            write(REPORTS / f"{Path(name).stem}_full_rebuild_failure.log", log)
            return code
    build_package()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(OLD),
        "target": str(JIIS),
        "migration": "full_information_sciences_body_to_jiis_springer_template",
        "manuscript_pages": page_count(SOURCE / "manuscript.pdf"),
        "supplementary_pages": page_count(SOURCE / "supplementary.pdf"),
        "manuscript_chars": len(read(SOURCE / "manuscript.tex")),
        "package_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(PACKAGE.iterdir())
            if p.is_file()
        },
        "compile_logs_tail": logs,
    }
    write(REPORTS / "jiis_full_migration_report.json", json.dumps(report, indent=2))
    clean_builds(SOURCE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
