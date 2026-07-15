# Research Design Contract

## Personal-use boundary

Use public primary sources, public secondary sources, community/user signals and user-provided hypotheses. Do not claim access to expert panels, enterprise systems, private databases or internal company data. A user's informal industry lead is a hypothesis to test, not evidence.

## Hypotheses and inferred trends

Record a user-supplied belief in `user_hypotheses` only when it could change the decision. Each entry must include a stable ID, statement, origin (`user_provided_lead`), and `must_test`.

For every `must_test` hypothesis:

- design at least one supporting search and one disconfirming search
- tag the searches with `hypothesis_ids` and `stance`
- test alternative explanations or routes
- resolve it as `supported`, `partially_supported`, `not_supported`, or `inconclusive`
- never use the user's statement itself as a supporting evidence item

Do not write a prompt that asks the model to “derive”, “prove”, or “reverse-engineer” a preferred conclusion.

Activate `trend_inference` when the task asks for an industry trend, common path, evolution or recurring operating pattern. The Agent may generate a candidate trend even when no source states it verbatim, but that candidate starts as `unverified` and must not be written as an industry fact. Build the test from observable behavior across independent actors, such as launch chronology, country availability, ad spend, localization hiring, partnerships, filings, revenue mix or product changes.

For each inferred trend:

- define the actor population, sample-selection basis, geography, period and observable pattern
- compare at least three independent comparable actors when possible
- show the denominator as `matching / observed sample`, matching actors, non-matching actors and unknown/missing observations
- preserve chronology; co-presence across regions is not proof of sequence
- classify it as `supported_in_sample`, `emerging_signal`, `isolated_case`, `mixed`, or `inconclusive`
- attach evidence IDs to every actor trace and explicitly list counterexamples

Write each `inferred_trends` item with: `id`, `pattern`, `scope`, `actor_population`, `sample_selection_basis`, `classification`, `generalizability`, `actor_traces`, `matching_actor_count`, `non_matching_actor_count`, `unknown_actor_count`, `counterexamples`, and `limitations`. Each actor trace contains `actor`, chronological observations, `matches_pattern` (`true`, `false`, or `null` when unknown), and deep-read `evidence_ids`. Use `supported_in_sample` only when at least three matching actors, more matches than non-matches and at least two independent source families support the chronology. `supported_in_sample` means only that the pattern is supported inside the declared sample; it never means the whole industry has a fixed route. Set `generalizability` to `sample_only` unless representative population coverage is demonstrated and documented.

An industry trend is an analytical inference, not a quotation. It may be useful without an article using the same words, but one actor or one attributed opinion is insufficient. Small or convenience samples must be described as a rough recurring signal, not a settled industry law.

## Dynamic module router

Activate only the modules required by the research questions or hypotheses. Record active module IDs in `research_design.active_modules` and map relevant searches with `module_ids`.

### `market_concentration`

Activate when the task asks whether a market is monopolized, oligopolistic, highly concentrated or controlled by a few players.

Require:

- comparable market shares or a clearly limited proxy
- CR3/CR5, HHI or an explicit explanation of why they cannot be calculated
- control-point evidence covering relevant IP, data, distribution, supply, capital, regulation or switching costs
- a classification of `high`, `moderate`, `fragmented`, or `unconfirmed`

Resource concentration is not automatically market monopoly. If comparable shares are unavailable, use `unconfirmed` and explain what evidence is missing.

### `geographic_sequencing`

Activate for cross-border expansion, country prioritization or claims that one region must precede another.

Do not wait for the user to propose a route, and do not insert any default route. Reconstruct actual entry timelines for at least three comparable companies, products or projects, or use an authoritative dataset that directly records the pattern. Build a matrix of entity, region, first-entry date, operating model, prerequisites and outcome. Identify repeated sequences, exceptions, unknown observations and changes over time; classify the observed pattern as `supported_in_sample`, `recurring_signal`, `mixed`, or `insufficient_evidence`.

Compare regions using only relevant dimensions: market value, acquisition cost, monetization, localization depth, regulation/IP, competition, payment/distribution, operating capability and capital at risk. Require at least two candidate paths, prerequisites for each stage, and a direct answer to “why not enter the largest-value market first?” The answer may be “direct entry is viable.” Separate the descriptive sample finding from the recommended path for the target company. Never hard-code a country or region sequence. Generate possible sequences as unverified candidates and retain `mixed` or `insufficient_evidence` when the evidence does not resolve them.

### `real_case_studies`

Activate when real products, titles, campaigns, transactions, implementations or operating examples materially affect the decision. Use at least three cases in Standard and five in Deep unless credible public cases do not exist; in that situation, return an evidence gap instead of inventing cases.

Select cases using a visible basis such as ranking, revenue, adoption, recency, strategic similarity or contrasting outcome. Adapt the breakdown dimensions:

- content/media: audience, premise, opening hook, pacing, monetization point, creative/distribution pattern
- SaaS: ICP, acquisition, onboarding, value moment, pricing, retention and expansion
- marketplace: supply/demand acquisition, liquidity, frequency, take rate, subsidy and governance
- commerce: traffic, conversion, AOV, contribution margin, repeat and returns
- IP/project business: acquisition, production, success rate, distribution, revenue share and payback

Fictional concepts may support an experiment plan but cannot count as market cases.

### `benchmark_ranges`

Activate when CAC, conversion, ARPU, price, margin, cost, payback, productivity or another numerical baseline changes the decision. Retrieve current comparable ranges rather than embedding fixed numbers in the Agent. Every benchmark must include metric, range/value, unit, geography, period, comparison scope and evidence IDs. Mark incompatible or unavailable benchmarks instead of forcing a number.

### `stress_test`

Activate for Deep mode and whenever the recommendation depends on a fragile assumption. Select at least one topic-relevant stress such as acquisition-cost inflation, regulation, platform policy, copyright, supply interruption, fraud/credit loss, cultural rejection or price compression. Specify trigger, impact, leading signal, response and decision gate.

### `trend_inference`

Use the cross-actor rules above. When a geographic rollout pattern is being inferred, activate both `trend_inference` and `geographic_sequencing`: the first establishes whether the pattern exists, while the second tests whether it is strategically rational and transferable.

## Required research design artifacts

Before collection, run `scripts/validate_research_plan.py`. It writes `output/research_plan_report.json` and blocks missing hypothesis counter-searches or required module coverage.

Before handoff, create `output/analyzed/research_design_results.json` according to the bundled template, then run `scripts/validate_research_results.py`. An inconclusive result can pass when the search and evidence gaps are explicit; an unsupported preferred conclusion cannot.
