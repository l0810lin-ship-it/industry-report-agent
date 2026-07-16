# Frozen comparative evaluation protocol

## Purpose

Compare complete research products on ambiguous real-user prompts and controlled evidence-based prompts while separating execution success, hard metrics, claim support and blinded decision quality.

## Required rules

1. Freeze every prompt byte-for-byte before execution and record SHA-256 in the manifest.
2. Give every system the same prompt for the same case; never add a private rescue instruction.
3. Preserve failed attempts, logs and setup repairs. A retry uses the same prompt.
4. Run serially when systems share a local model, browser, quota or search backend.
5. Keep original report bodies untouched. Scoring code may read them but must not rewrite them.
6. Separate hard metrics from judgment scores.
7. Audit at least five decision-changing claims per successful report; numeric claims take priority.
8. Blind system identity before rubric scoring and unblind only for aggregation.
9. Report model, search backend, elapsed time and setup friction as confounders.
10. Do not claim architecture causality without a same-model, same-budget ablation.

## Completion gate

A benchmark is complete only when:

- every planned sample has terminal status;
- successful samples retain matching frozen input and output hashes;
- hard metrics cover every planned sample;
- each successful report has exactly five non-pending audited claims;
- every successful report has one unique blind score;
- comparison and resume-metric summaries exist;
- `state.json.status` is `completed`;
- `validate_completion.py` returns `valid: true`.
