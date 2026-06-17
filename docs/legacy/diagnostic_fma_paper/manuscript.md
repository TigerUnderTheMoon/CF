# Superseded Manuscript Surface

Status: migrated on 2026-06-17.

This file no longer carries the active manuscript text. The previous Markdown
draft was a diagnostic-framework manuscript surface and has been superseded by
the KBS/SC-FMA submission package.

Use these files instead:

- Authoritative manuscript source: `paper/kbs_submission/final_source/manuscript.tex`
- Compiled manuscript PDF: `paper/kbs_submission/final_package/manuscript.pdf`
- Submission manifest: `paper/kbs_submission/final_submission_manifest.md`
- Claim contract: `paper/claim_registry.md`
- Submission lock audit: `paper/submission_lock_audit.md`

Current claim boundary:

- Positive real-data support is limited to PRM800K step-ranking and offline
  audit-prioritization context under the locked split.
- GSM8K and HotpotQA task-specific replay routes remain failed or blocked.
- The package does not claim downstream PRM training gain, task-specific replay
  validation, production deployment validation, or causal identification.

Verification gate:

```powershell
python scripts\verify_kbs_submission_package.py --package-dir paper\kbs_submission\final_package --require-author-metadata --require-pdf-text
pytest -q tests\test_claim_boundaries.py tests\test_kbs_submission_package_verifier.py tests\test_prm800k_audit_prioritization.py tests\test_dvc_contract.py
```

