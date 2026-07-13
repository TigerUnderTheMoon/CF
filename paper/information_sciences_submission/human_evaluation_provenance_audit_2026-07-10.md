# Human-Evaluation Provenance Audit

Date: 2026-07-10

## Decision

The completed rating sheets found under
`.claude/worktrees/information-sciences-submission-fd0833/outputs/`
are not admissible as human-rater evidence. They were produced by automated
model tasks and must not be reported as a human evaluation, expert review,
human adjudication, or human-in-the-loop validation.

The active manuscript must retain the statement that no human-rater experiment
is included.

## Evidence

- `rating_sheet_evaluator_1.csv` was populated by an automated task that wrote
  all 144 ratings programmatically on 2026-07-10 at approximately 15:32 local
  time.
- `rating_sheet_evaluator_2.csv` was replaced by an automated patch containing
  all 144 ratings on 2026-07-10 at approximately 15:32 local time.
- `rating_sheet_evaluator_3.csv` was populated in several automated patches
  between approximately 15:29 and 15:34 local time, including generated
  free-text notes.
- The three files were completed within roughly 10-12 minutes of dispatch
  package creation. No human recruitment record, evaluator identity or
  pseudonymous provenance record, independent assignment record, return
  correspondence, consent/ethics determination, or signed completion
  declaration is present.
- The copied files in `human_eval_package/` have the same SHA-256 hashes as the
  files in the dispatch folders. The resulting agreement statistics therefore
  describe automated ratings, not independent human judgments.

## Manuscript Handling

- Do not cite `human_eval_analysis.json` from either the v2 package or the
  round-1 pilot as human evidence.
- Do not report the apparent condition means, confidence intervals, Wilcoxon
  tests, Cohen kappa values, or Krippendorff alpha values from those files in
  the manuscript.
- Keep `F_HUMAN_AUDIT_USEFULNESS` at `future_validation`.
- Preserve the current abstract, discussion, conclusion, supplementary, and
  submission-manifest wording that human audit usefulness remains future work.

## Requirements for a Valid Rerun

A result can enter the paper only after all of the following are available:

1. Three real evaluators with mathematics or step-annotation experience.
2. Verifiable recruitment provenance and a pseudonymous evaluator ID for each
   rater.
3. Independent distribution of one blinded folder per evaluator, with no
   access to the blinding key, protocol hypothesis, or another rater's sheet.
4. Returned original CSV files plus assignment and completion timestamps.
5. A signed or explicitly confirmed independence/completion declaration.
6. File hashes recorded before analysis and no post-return score editing.
7. Re-analysis from the returned CSV files using the preregistered v2 protocol.
8. Reliability reported before condition effects; any measure with
   Krippendorff alpha below 0.667 remains inconclusive.
9. Bounded wording limited to human-rated prioritization, guidance usefulness,
   and interpretability. The study cannot establish audit correctness, oracle
   validity, production knowledge-base validation, or causal effects.

## Current Status

`BLOCKED_PENDING_REAL_HUMAN_RETURNS`

The clean blank dispatch package is located at
`outputs/human_eval_real_pending/`. It contains three evaluator folders and an
analyst-only folder. All three rating sheets were verified to contain 144 rows
and zero completed ratings at creation.

No manuscript result update is authorized from the existing rating files.
