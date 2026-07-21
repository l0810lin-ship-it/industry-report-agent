# Taxonomy Contract

Use this contract when classifying an assignment before search, selecting research modules, mapping questions to queries, auditing claims and choosing the report structure.

Classification is a routing layer. It decides what evidence must be collected and what quality gates apply. It is not a substitute for evidence.

## Assignment taxonomy

Each run must classify the assignment with these fields:

- `decision_type`: `enter_market`, `launch_product`, `invest_or_allocate`, `defend_position`, `compare_options`, `validate_hypothesis`, `monitor_market`, or `explain_landscape`.
- `user_role`: `founder_operator`, `strategy_team`, `product_team`, `investor_advisor`, `researcher`, or `unknown`.
- `time_horizon`: `near_term_90_days`, `annual_planning`, `multi_year`, or `unspecified`.
- `geographic_scope`: target region or countries, with `cross_border` true or false.
- `deliverable_intent`: `decision_brief`, `management_report`, `board_memo`, `ppt_storyline`, or `benchmark_packet`.

## Research-question taxonomy

Every research question should include a stable ID and one or more `question_types`:

- `market_size`
- `timing`
- `customer_problem`
- `demand_signal`
- `competition`
- `control_points`
- `business_model`
- `unit_economics`
- `go_to_market`
- `geographic_sequence`
- `regulatory_or_platform_risk`
- `technology_shift`
- `right_to_win`
- `validation_plan`

The selected question types determine required evidence. For example, `market_size` requires denominator, unit, geography and period. `competition` requires named actors and control points. `unit_economics` requires revenue engine and atomic economic unit.

## Claim taxonomy

Every critical claim must include one `claim_type`:

- `fact`: a checkable event, product, actor, policy or market condition.
- `metric`: a number, range, share, growth rate, cost, conversion or benchmark.
- `trend`: a pattern inferred across actors or time.
- `causal`: a reason-why statement connecting cause and effect.
- `forecast`: a future expectation or scenario.
- `comparison`: a relative ranking, advantage or disadvantage.
- `recommendation_premise`: a claim required for the final recommendation.
- `assumption`: a model input that is not proven by evidence.

Numeric and recommendation-premise claims take priority in audit. A rejected claim cannot remain a recommendation dependency.

## Source taxonomy

Classify every evidence item by `source_type`:

- `official`
- `regulatory`
- `financial_filing`
- `research_report`
- `reputable_media`
- `company_blog_or_docs`
- `community_or_user_voice`
- `dataset`
- `private_user_document`
- `search_lead`

`search_lead` cannot support a factual claim. `private_user_document` must remain `PRI-*` and cannot satisfy public evidence gates.

## Evidence-status taxonomy

Evidence status must stay separate from claim status:

- `verified_source_body`: original source body was read.
- `structured_lead`: backend returned structured fields, but source body was not read.
- `lead_only`: title, snippet or failed URL only.
- `inaccessible`: source could not be read.
- `stale_for_scope`: source is real but too old for the report's time claim.

## Routing rules

- `enter_market`, `launch_product` and `invest_or_allocate` require market sizing, business model, competition, Right to Win and 90-day validation gates.
- `compare_options` requires a comparable option set, decision criteria, tradeoffs and a single recommended option when evidence supports it.
- `validate_hypothesis` requires both supporting and disconfirming search paths.
- `monitor_market` can output signals and watch items, but must avoid confident strategic recommendations.
- Cross-border assignments require geographic sequencing and trend-inference modules.
- `explain_landscape` may be descriptive, but must still label recommendations as out of scope unless requested.
