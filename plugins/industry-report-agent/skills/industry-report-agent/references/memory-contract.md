# Memory Contract

Use this contract before configuring a fresh research run, using private knowledge, or reusing any prior context.

The Agent has memory discipline, not permission to reuse old conclusions. Memory is allowed only when it improves workflow reliability, user fit, traceability or evaluation learning. Market facts, rankings, strategic recommendations and prior evidence counts must be recollected or revalidated for the current scope.

## Memory classes

Every reusable memory item belongs to one class:

- `operational`: tool paths, command patterns, known runtime failures and repair notes. It may be reused across runs when still applicable.
- `user_preference`: delivery style, language, preferred depth, preferred format and review habits. It may shape output form, not factual conclusions.
- `source_cache`: URLs, document fingerprints, parsed private-document metadata and access status. It may accelerate retrieval, but the original source still needs freshness and scope checks.
- `run_context`: the current run's target, questions, selected mode, output formats, assumptions, evidence ledgers and gate reports. It is scoped to one run unless exported as a disclosed source.
- `evaluation_learning`: failed cases, unsupported-claim patterns, retrieval misses, scoring notes and regression lessons. It may improve prompts, gates and rubrics, not become report evidence.
- `conclusion`: prior market facts, market sizes, competitor rankings, recommendations, opportunity scores and strategic judgments. It is blocked for automatic reuse.

## Required fields

Any memory item promoted for reuse must record:

- `memory_id`
- `memory_class`
- `statement`
- `source_run_id` or `source_artifact`
- `created_at`
- `scope`
- `allowed_use`
- `forbidden_use`
- `freshness_policy`
- `confidence`
- `owner`
- `review_status`

## Reuse rules

- Reuse `operational` and `user_preference` memory only when it does not change a factual claim.
- Use `source_cache` as a lead to reopen or revalidate a source, not as final evidence by itself.
- Keep `run_context` inside the current run. If a prior run is supplied by the user, cite it as a disclosed private source and assign `PRI-*`.
- Use `evaluation_learning` to update tests, prompts, schemas or guardrails after human review.
- Never use `conclusion` memory as evidence, even when it came from a high-quality prior report.

## Freshness policy

Set a freshness policy by memory class:

- `operational`: recheck when scripts, plugin version or toolchain changes.
- `user_preference`: keep until user changes it.
- `source_cache`: revalidate before citation; dated sources must match the report's period.
- `run_context`: valid only for the current run unless explicitly archived and disclosed.
- `evaluation_learning`: keep until the underlying prompt, schema or failure mode is resolved.
- `conclusion`: no automatic freshness extension; always recollect or revalidate.

## Promotion and deprecation

New memory starts as an observation. Promote it only after it is stable, useful and safe to reuse. Deprecate or supersede memory when a source expires, a user preference changes, a tool path breaks, a schema changes, or a later evaluation shows that the memory caused a wrong answer.

Do not hide memory use. The final run summary should state which memory classes were reused, which were blocked, and which prior items were only used as retrieval leads.
