# Strategy Decision Report Contract

## Mode contracts

The machine-readable source of truth for mode time, scope ceilings, deliverables and format overhead is `../../../scripts/project-template/mode_profiles.json`. Never silently select a mode. A platform ceiling is a maximum, not a quota. When required scope exceeds the selected ceiling, narrow the question or ask the user to move to the next mode.

## Decision architecture

The executive summary must state the decision, why now, Right to Win, decisive evidence, contrary evidence, 90-day actions and management approvals.

For an entry, launch, product or investment decision, the recommendation must also contain a **launch-bet card**. It is not enough to name an abstract platform, capability layer or strategic direction. The card must identify the target market segment, first product/category wedge, target user and triggering job, product surface, concrete product form and user journey, supply acquisition, transaction/fulfilment boundary, revenue model, pilot geography, primary alternative, differentiated advantage, 90-day falsification metric and explicit non-goals.

When evidence cannot support a specific field, write `TBD — insufficient evidence`, name the missing evidence and downgrade the recommendation to conditional. Never hide an unresolved product choice behind phrases such as “platform”, “ecosystem”, “orchestration layer”, “AI capability” or “integrated solution”.

It must also include a compact credibility summary that reports separate counts for fully supported, mixed, provisional and rejected decision-changing claims. Do not combine full and partial/provisional support into one headline percentage.

The five chapters must answer:

1. Is the market attractive, and why is now the right or wrong time?
2. Who has which costly problem, and what economic value can be captured?
3. Who controls the data, distribution, technology, delivery and customer relationship?
4. Why can the target win, and which Build/Buy/Partner option is best?
5. Which single segment and product wedge should management approve, through which product surface and business/transaction loop, with resources, metrics and continue/pivot/kill gates?

Chapter 1 must include a consistent-scope TAM/SAM/SOM calculation using both top-down and bottom-up methods, scenario ranges and reconciliation. Chapter 2 must identify the revenue engine and atomic economic unit before selecting metrics, then show unit economics, contribution or break-even logic, scenarios and data gaps. Use `market-sizing-contract.md` and `business-model-contract.md` as mandatory extensions of this contract.

When the topic spans regions, Chapter 1 must infer recurring entry patterns from comparable actor chronology rather than wait for a proposed route. When concentration or real cases affect the decision, Chapter 3 must show the relevant dynamic modules. Use `research-design-contract.md` and `claim-validation-contract.md`; separate an observed industry pattern from the path recommended for the target.

Keep product plays and prototypes optional. They support the strategic bet; they do not substitute for the decision.

## Narrative substance gate

The canonical Markdown report is validated chapter by chapter. Standard and Deep must satisfy all of the following before handoff:

- each chapter independently contains the decision elements assigned to it; a term appearing elsewhere cannot satisfy the chapter;
- each chapter cites at least one evidence-ledger item, while decision-changing claims still follow the stronger corroboration rules;
- real cases declared complete in `research_design_results.json` appear by name in the report;
- Standard has at least 8,000 non-whitespace characters overall, a 500-character executive summary and 1,000 characters per chapter;
- Deep has at least 18,000 non-whitespace characters overall, an 800-character executive summary and 1,800 characters per chapter.

These are rejection floors for underdeveloped drafts, not writing targets. Repetition, generic framework text, copied source bodies and artificial padding do not count as decision quality. A concise section may exceed the floor through tables, formulas, comparisons and explicit evidence rather than prose volume.

## Evidence discipline

- Separate fact, source claim, inference and recommendation.
- Attach evidence IDs and URLs to decision-changing facts.
- Present the strongest evidence against the recommendation.
- Do not fabricate market sizes, adoption rates, ROI, budgets or KPI targets.
- Do not force CPI, LTV/CAC, paid conversion or consumer-App metrics onto unrelated business models.
- Do not present one actor, one opinion or co-presence across regions as an industry sequence.
- Do not use fictional concepts as observed market cases.
- If evidence is insufficient, issue a conditional recommendation and state the exact evidence needed to remove the condition.
