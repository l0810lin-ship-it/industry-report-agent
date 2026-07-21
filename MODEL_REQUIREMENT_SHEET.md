# Model Requirement Sheet

## Product Position

Industry Report Agent is an evidence-gated research assistant for management decision support. It helps a user turn an ambiguous company, market, competitor or product question into a scoped research run, public and optional private evidence ledgers, claim-status tracking, market sizing, business-model analysis and a conditional recommendation.

It does not autonomously make strategic decisions for a company. The output is a decision brief or report for human review, with confidence, contrary evidence, unresolved claims and the next validation gate made explicit.

## Target Users

- Founders and operators deciding whether to enter a market, launch a product wedge or continue a pilot.
- Strategy, product and business-analysis teams preparing management memos under evidence constraints.
- Investors, advisors or researchers comparing market attractiveness, competitive control points and execution risk.
- Individual users or small teams who keep source files locally and need a reproducible research workflow without a server-side knowledge base.

## Primary Scenarios

- Market-entry and launch-bet analysis: identify target segment, first product/category wedge, payer, geography, revenue engine and 90-day validation path.
- Competitor and industry-structure analysis: map actors, control points, concentration, substitute threats and right-to-win assumptions.
- Evidence testing of user hypotheses: search for support, counterevidence and scope limits instead of treating the user statement as truth.
- Cross-border or geography sequencing research: compare routes using actor timelines, denominators and exceptions.
- Benchmarking research systems: freeze prompts, run comparable systems, preserve attempts, audit claims and score blind outputs without rewriting reports.
- Classification-routed research: turn ambiguous prompts into explicit decision type, research question types, evidence requirements and report gates before collection.

## Inputs

- User topic or decision question, including target company, industry, region, time horizon and strategic context when available.
- Required research mode: Flash, Standard or Deep.
- Required output format: Markdown, Word and/or PowerPoint.
- Optional private documents in the configured local knowledge directory.
- Optional direct-source URLs, competitor names, hypotheses, geography constraints or business-model assumptions.

Missing mode or format is blocking unless the user explicitly delegates the choice. Missing business context should be handled with stated assumptions when it does not materially change the research direction.

## Outputs

- Run configuration, research plan and estimate.
- Assignment classification covering decision type, user role, time horizon, geography, deliverable intent, question types, routing rationale and required gates.
- Memory-use posture that records which memory classes were reused, blocked or revalidated.
- Private evidence ledger with `PRI-*` IDs when local documents are used.
- Public evidence ledger with `EV-*` IDs, source origins, deep-read status and quality report.
- Claim ledger with supported, mixed, provisional and rejected statuses.
- Market-sizing calculations, business-model classification, unit-economics formulas and input gaps.
- Flash decision brief or Standard/Deep management report, plus selected Word or PowerPoint renderings when requested.
- Gate artifacts: plan, evidence, research-results and deliverable quality reports.
- Evaluation harness artifacts when benchmarking: frozen prompts, manifest, attempt history, hard metrics, claim audit, blind scores, comparison report and completion validator output.

## Quality Indicators

- Intake is complete and provenance is recorded as user-selected or user-delegated.
- Assignment classification is complete before search planning; decision-changing routes have the required question types and gates.
- Memory reuse is limited to operational, user-preference, source-cache, current-run and evaluation-learning classes. Prior conclusions are blocked unless reintroduced as disclosed private sources and revalidated.
- Research plan passes before collection starts.
- Public evidence gate passes with original-body deep reads, independent domains, question coverage and search-discovered breadth. Private evidence cannot satisfy the public-source gate by itself.
- Critical claims cite evidence IDs and URLs, preserve the source/inference boundary and show separate counts for supported, mixed, provisional and rejected claims.
- Standard/Deep reports include both top-down and bottom-up market sizing on the same economic scope, or clearly expose missing inputs and thresholds.
- Business model and unit economics match the actual revenue engine instead of forcing one generic model across industries.
- Recommendation is conditional when evidence is incomplete and includes contrary evidence, non-goals and Continue/Pivot/Kill criteria.
- Evaluation harness completion requires terminal samples, matching input/output hashes, complete hard metrics, exactly five audited claims per successful report, one blind score per successful report and a valid completion check.

## Risks

- Search snippets, `lead_only` records or inaccessible pages being promoted into verified evidence.
- Direct-source lists becoming a biased allowlist that suppresses search discovery.
- Private documents being over-weighted or exported beyond user intent.
- Market-size scope errors such as mixing GMV, consumer spend, advertiser spend and net revenue.
- Unsupported strategic certainty from a small sample, one company case or one source's opinion.
- Benchmark contamination through prompt rescue, report rewriting, identity leakage or causal claims without same-model/same-budget ablations.
- Stale source dates, broken retrieval, platform rate limits or regional access gaps.

## Fallback Behavior

- Ask one blocking intake question when mode or format is missing and not delegated.
- Narrow the scope or recommend the next mode when the selected mode cannot support the requested breadth.
- Use the configured discovery fallback chain when the primary search backend fails, while preserving actual backend metadata.
- Mark claims provisional, mixed or rejected when corroboration or counter-search is insufficient.
- Use `TBD - insufficient evidence` for unresolved launch-bet fields instead of inventing numbers or confident prose.
- Provide an incomplete memo only when the user explicitly asks for one, and list every failed gate and residual limitation.
- For benchmark failures, preserve failed attempts and repair runtime plumbing only; do not change prompts or rewrite outputs to rescue a system.

## Not Supported

- Autonomous approval of investments, market entry, budgets, hiring, legal actions or product launches.
- Claims of expert interviews, enterprise-system access, private databases or internal company data unless actually supplied by the user and disclosed as private evidence.
- Using user hypotheses, fictional examples, search snippets or model assumptions as evidence.
- Replacing management judgment, legal advice, financial advice, medical advice or compliance review.
- Circumventing paywalls, authentication, robots restrictions or source access controls.
- Cloud knowledge-base hosting, enterprise permissions inheritance, telemetry or server-side audit systems in the current local version.
- Reusing a prior report body as a new independent Agent result.
