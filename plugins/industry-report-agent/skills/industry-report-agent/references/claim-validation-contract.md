# Claim Validation Contract

## Critical claim ledger

Record every decision-changing claim in `output/analyzed/research_design_results.json`. A critical claim entry must include:

- stable claim ID and exact statement
- scope: geography, period, population/economic layer and unit when relevant
- status: `supported`, `mixed`, `provisional`, or `rejected`
- supporting evidence IDs
- opposing evidence IDs, if found
- counter-search status: `found`, `searched_none_found`, or `not_applicable`
- inference boundary and decision impact

The ledger is the authoritative owner of claim status. Report prose must not upgrade `mixed`, `provisional`, `rejected`, or `inconclusive` findings into unconditional facts.

## Evidence thresholds

- A critical `supported` claim requires deep-read evidence from at least two independent source families.
- A `mixed` claim requires both supporting and opposing evidence.
- A `provisional` claim must state the missing corroboration or scope limitation.
- A `rejected` claim must not be used as a recommendation premise.
- `searched_none_found` means a real counter-search was performed; it does not prove no counterexample exists.

User hypotheses, search snippets, fictional examples and model-generated assumptions never count as supporting evidence.

## Credibility report card

Report transparent dimensions rather than a decorative single score:

- question and active-module coverage
- deep-read/original-body coverage
- primary-source coverage
- source independence and concentration
- freshness metadata coverage
- critical-claim corroboration rate
- counter-search completion rate
- unresolved critical claims
- real-case completion when selected

Always display the critical-claim status distribution as separate counts and rates for `supported`, `mixed`, `provisional`, and `rejected`. `Supported + provisional` or `fully + partially supported` must not be advertised as a single success rate. If a compact summary is needed, lead with the fully supported rate and show every unresolved category beside it.

Do not advertise a fixed number of quality gates unless the implemented report for that run contains exactly that number.
