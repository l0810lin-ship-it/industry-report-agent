# Reproducible Evaluation Harness

This directory is a sanitized, reusable version of the harness used to compare industry-research systems. It is deliberately separate from the Agent runtime: the harness freezes inputs, invokes systems, records attempts and artifacts, audits claims, creates anonymous packets, scores a fixed rubric and fails closed when required evidence is incomplete.

It contains no historical report bodies, API keys, local machine paths, task IDs or plugin-cache references.

## Evaluation layers

Use the harness at the smallest layer that can catch the risk introduced by a change.

| Layer | Purpose | Typical command set | Required result |
| --- | --- | --- | --- |
| Smoke | Verify the harness scripts, schemas and completion validator can run end to end. It does not measure research quality. | The bundled `cases.sample.json`, `systems.sample.json` and mock runner. | `validate_completion.py` returns `"valid": true`. |
| Regression | Verify a change to prompts, templates, schemas, scripts, gate logic or packaging did not break frozen-input execution, claim-audit shape, blind scoring or completion checks. | A small fixed case set and one or more real runners relevant to the changed surface. | All planned samples reach terminal state; no pending claims; completion validator passes; diffs in metrics or claim status are reviewed. |
| Full benchmark | Compare complete research systems under a frozen protocol. | The full frozen case set and all planned systems, run serially when resources are shared. | The protocol completion gate passes before any ranking, resume metric or public comparison is reported. |

Do not use the smoke layer to claim model quality. Do not use the regression layer to claim market leadership. Do not use the full benchmark to imply architecture causality unless model, tool budget and source access are controlled.

## What it controls

```text
cases.json + systems.json
→ byte-frozen prompts and SHA-256 hashes
→ serial system execution
→ immutable attempt directories
→ run_manifest.csv + state.json
→ hard_metrics.csv
→ five decision-changing claims per successful report
→ anonymous packets and rubric scores
→ comparison report and completion validator
```

## Quick smoke test

The included mock runners test the harness, not research quality.

```bash
cd evaluation
python3 scripts/run_benchmark.py \
  --cases cases.sample.json \
  --systems systems.sample.json \
  --root .demo

python3 scripts/build_metrics.py --root .demo
python3 scripts/audit_claims.py --root .demo --demo-label-unverifiable
python3 scripts/score_blind.py --root .demo
python3 scripts/summarize.py --root .demo
python3 scripts/validate_completion.py --root .demo
```

The final command must return `"valid": true`. Delete `.demo/` after the smoke test.

## Regression triggers

Run at least the smoke test after any change under `evaluation/`. Run a regression benchmark before publishing when a change touches any of the following:

- runner command construction, retry handling, manifest fields, state handling or hashing;
- claim extraction, claim-audit schema, blind scoring, summary metrics or completion validation;
- Agent prompts, report templates, quality gates, evidence ledger semantics or claim-status wording;
- packaging or installer behavior that changes how a real runner invokes the Agent;
- dependencies, local-model configuration, search backend routing or source retrieval behavior.

Run a full benchmark when changing the evaluation protocol, adding or removing systems, changing the frozen case set, or making claims about comparative performance.

## Real runners

Each system command receives `{input}`, `{output}` and `{sample_id}` placeholders. A compliant runner must write:

```text
<output>/report.md
<output>/metrics.json    # optional but recommended
<output>/run.log         # optional
```

Run systems serially when they share a local model or constrained search backend. Never rewrite a frozen prompt to rescue one system. Runtime plumbing may be repaired, but the failed attempt and repair must remain recorded.

For the Industry Report Agent, the runner should invoke a fresh Agent run for each frozen input and collect the final report plus gate artifacts. The harness may record, copy and score artifacts; it must not draft report prose, patch conclusions or turn a failed gate into a completed result.

## Human evidence audit

`audit_claims.py` creates five candidate decision-changing claims per completed report with status `pending`. For a real benchmark, an auditor must open the cited page and replace each status with one of:

- `supported`
- `partially_supported`
- `unsupported`
- `contradicted`
- `unverifiable`

`--demo-label-unverifiable` exists only so the bundled fake-runner smoke test can reach a terminal state. The completion validator rejects pending claims.

Claim audit is separate from the Agent's own evidence gate. The Agent evidence gate decides whether a report is a valid evidence-backed deliverable. The benchmark claim audit checks whether five decision-changing claims in a completed report are externally supportable for comparison purposes. Passing one layer does not waive the other.

## Historical aggregate, not a causal claim

The sanitized example in `examples/sanitized-results/aggregate_summary.md` reports the prior end-to-end benchmark with its limitations. Model and search backends differed, so those results must not be presented as a pure architecture ablation.
