# Frozen comparative evaluation protocol

## Purpose

Compare complete research products on ambiguous real-user prompts and controlled evidence-based prompts while separating execution success, hard metrics, claim support and blinded decision quality.

## Evaluation layers

1. Smoke: run the bundled sample cases and mock systems to prove the harness can produce a valid terminal artifact set. This layer validates plumbing only.
2. Regression: run a small fixed case set against the changed real runner or Agent surface after changes to prompts, templates, gates, schemas, runner commands, dependencies or retrieval behavior. This layer catches behavioral drift and artifact-contract breakage.
3. Full benchmark: run the complete frozen case set and all planned systems before reporting comparative performance, resume metrics or public claims.

Each layer inherits the required rules below. A higher layer may not rewrite prompts, reports or claim labels produced by a lower layer to manufacture a pass.

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
11. Preserve each system's native output and gate artifacts. A harness may freeze input, invoke a runner, record attempts, hash outputs, extract claims and score packets; it must not author conclusions or repair report prose.
12. Keep evidence quality separate from execution success. A completed runner process is not evidence that a report passed the Agent evidence gate or the human claim audit.

## Claim audit

Every successful report needs exactly five decision-changing claims for audit. Numeric claims, market-size claims, recommendation premises, risk claims and competitor/control-point claims take priority.

Audit status values are:

- `supported`
- `partially_supported`
- `unsupported`
- `contradicted`
- `unverifiable`

The auditor should open the cited source when available, record the source access status and avoid upgrading a claim based on a snippet alone. `unverifiable` is a terminal benchmark status, not a positive evidence signal.

## Evidence gates

The harness completion validator checks benchmark artifact integrity. It does not replace the Industry Report Agent evidence gates.

For Agent outputs, report the Agent gate statuses separately when available:

- `research_plan_report.json`
- `raw/quality_report.json`
- `research_results_quality_report.json`
- `deliverable_quality_report.json`

An Agent report whose internal gate failed may still be preserved as a benchmark output, but it must be labeled as a failed-gate output and cannot be presented as a completed Agent deliverable. Private evidence, user hypotheses, snippets and `lead_only` records cannot satisfy public-source evidence quality.

## Regression triggers

Run smoke after any harness file change. Run regression before publishing or comparing results when changes touch:

- benchmark runner command construction, retry logic, manifest fields, hashing or state handling;
- claim extraction, claim-audit schema, scoring, summary metrics or completion validation;
- Agent prompts, report templates, mode profiles, quality gates, evidence ledger semantics or claim-status language;
- packaging, installer behavior or custom-agent launcher behavior that changes how the runner invokes the Agent;
- dependencies, local model setup, search backend routing, source retrieval or deep-read behavior.

Run a full benchmark when changing the frozen case set, adding or removing systems, changing the protocol itself, or making comparative performance claims.

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
