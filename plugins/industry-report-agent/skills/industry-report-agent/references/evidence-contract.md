# Evidence Contract

Use this contract when interpreting the evidence ledger, repairing quality failures, and drafting report claims.

## Evidence states

- `verified_source_body`: the original URL was read successfully. It may support factual claims within the captured text.
- `structured_lead`: a platform backend returned structured fields, but the original body was not deep-read. Use for user-voice signals with attribution; do not treat it as official confirmation.
- `lead_only`: only a title, snippet, or failed URL is available. Use it to find a better source, not as factual support.

`evidence_strength` is a routing hint, not a substitute for judgment:

- `high`: deep-read official, regulatory, or research source.
- `medium`: deep-read secondary source or structured platform result.
- `low`: discovery-only lead.

## Direct sources and discovery sources

`direct_sources` are known primary-document anchors supplied or selected during planning. They improve source quality and retrieval priority, but they are never an exclusive allowlist. Every configured research, focus and competitor query must still run through the available discovery chain.

The evidence ledger records provenance in `source_origins`:

- `direct`: a planned authoritative URL.
- `search`: discovered through Exa, Google, Bing or DuckDuckGo.
- `community`: returned by a selected community/platform backend.

The same URL may carry more than one origin after deduplication. Standard/Deep gates measure search-discovered breadth and search-discovered deep reads separately. A report cannot pass by preloading enough official URLs while discarding the external discovery pool.

## Adaptive candidate discovery

Candidate count is not fixed. Search starts with a small ranked batch and expands only while the next larger batch contributes enough new URLs. Every query records its expansion trace and one stop reason: `novelty_saturated`, `backend_exhausted`, `safety_ceiling_reached`, or `expansion_failed`. The per-mode ceiling prevents an unbounded crawler loop; it is not a desired evidence count.

Before deduplication, classify each returned item as `anchor`, `relevant`, or `rejected_low_relevance` using the configured query, topic and entity. Keep all anchors and relevant items. Preserve low-relevance rejections with their score and reason, but do not promote them into the evidence ledger. If a critical research question is still uncovered after a query saturates, add a narrower targeted query rather than lowering the relevance rule or inflating the batch.

## Required claim handling

For every material claim:

1. Record the supporting `evidence_id` and URL.
2. Quote or paraphrase only content present in `content_excerpt` or a subsequently opened original source.
3. Separate the source's statement from the Agent's inference.
4. Use at least two independent domains for critical claims.
5. Mark a claim provisional when corroboration is unavailable.
6. Reject a precise number when its date, unit, geography, or methodology cannot be established.
7. Treat `user_hypotheses` as search instructions, never as evidence.
8. Infer a trend only from actor-level observations with chronology, denominator and counterexamples; no source needs to state the final synthesis verbatim.

## Quality gate interpretation

Treat failed checks as blockers for a formal report. Repair the underlying evidence:

- `total_evidence`: add targeted queries tied to research questions.
- `deep_read_evidence`: retrieve original bodies or replace inaccessible leads.
- `search_discovered_evidence`: restore the frozen search-discovery pool; direct-source anchors cannot replace it.
- `search_deep_read_evidence`: deep-read independent sources selected from discovery, not only preselected URLs.
- `primary_domains`: add official, regulatory, or research sources and classify their domains in `source_rules`.
- `domain_concentration`: diversify independent domains and remove duplicate syndication.
- `freshness`: add recent dated evidence or narrow the report's time claim.
- `question:*:evidence`: add queries mapped to the uncovered research question.
- `question:*:deep_read`: deep-read at least one original source for every critical question.
- `question:*:cross_source`: corroborate critical questions across independent domains.
- `module:*`: add searches and deep reads tagged to the active dynamic research module.
- `hypothesis:*`: run both support and disconfirm searches for the user-provided lead.
- `trend:*`: add actor timelines and exception searches; one matching actor cannot establish a trend.
- `competitor_coverage`: research missing in-scope competitors or remove them from scope.
- `selected_platform_coverage`: improve the selected platform query; do not add unrelated platforms.

Do not modify a generated quality report by hand. Change the research plan or collection path and rerun the pipeline.
