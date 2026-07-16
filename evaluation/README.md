# Reproducible Evaluation Harness

This directory is a sanitized, reusable version of the harness used to compare industry-research systems. It is deliberately separate from the Agent runtime: the harness freezes inputs, invokes systems, records attempts and artifacts, audits claims, creates anonymous packets, scores a fixed rubric and fails closed when required evidence is incomplete.

It contains no historical report bodies, API keys, local machine paths, task IDs or plugin-cache references.

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

## Real runners

Each system command receives `{input}`, `{output}` and `{sample_id}` placeholders. A compliant runner must write:

```text
<output>/report.md
<output>/metrics.json    # optional but recommended
<output>/run.log         # optional
```

Run systems serially when they share a local model or constrained search backend. Never rewrite a frozen prompt to rescue one system. Runtime plumbing may be repaired, but the failed attempt and repair must remain recorded.

## Human evidence audit

`audit_claims.py` creates five candidate decision-changing claims per completed report with status `pending`. For a real benchmark, an auditor must open the cited page and replace each status with one of:

- `supported`
- `partially_supported`
- `unsupported`
- `contradicted`
- `unverifiable`

`--demo-label-unverifiable` exists only so the bundled fake-runner smoke test can reach a terminal state. The completion validator rejects pending claims.

## Historical aggregate, not a causal claim

The sanitized example in `examples/sanitized-results/aggregate_summary.md` reports the prior end-to-end benchmark with its limitations. Model and search backends differed, so those results must not be presented as a pure architecture ablation.
