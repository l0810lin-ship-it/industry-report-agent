# Adaptive Business Model and Unit Economics Contract

## Purpose

Do not force every topic into CPI, LTV/CAC, paid conversion, or any other fixed consumer-app model. First identify how money is made, then select the smallest economic unit, the matching formulas, and the decision thresholds.

## Required classification

Before drafting Chapter 2, classify the topic into one primary revenue engine and any material secondary engines. Record:

- payer, user, buyer and beneficiary
- revenue engine and charging basis
- atomic economic unit
- acquisition, conversion, retention and monetization events
- direct variable costs, shared costs, capital needs and material risk costs
- whether the model is single-engine or hybrid

If the company has several engines, model each separately and reconcile them with a sum-of-parts view. Never average incompatible denominators such as users, orders, seats and projects.

## Metric router

| Revenue engine | Atomic unit | Core revenue equation | Required decision metrics |
|---|---|---|---|
| Advertising / media | impression, active user or advertiser action | `Revenue = impressions / 1,000 × eCPM`; `Impressions = active users × sessions × ad opportunities × fill rate` | DAU/MAU, sessions, ad load, fill rate, eCPM, CTR, CVR, CPC, CPA, advertiser retention, ARPU, traffic/content/creator cost |
| Subscription / paid content | paid user or cohort | `Revenue = paid users × ARPPU`; `Paid users = active users × paid conversion` | paid conversion, ARPPU, gross margin, cohort retention, churn, refund, CAC, LTV, CAC payback, content amortization |
| Marketplace / transaction platform | order or GMV | `Net revenue = buyers × orders per buyer × AOV × take rate + service revenue` | GMV, AOV, take rate, buyer/seller CAC, repeat rate, match/liquidity, subsidy, payment/fulfilment/service/refund cost, contribution margin |
| SaaS / enterprise software | account, contract or seat | `ARR = customers × ACV` or `seats × price per seat` | ACV/ARR, gross margin, GRR, NRR, logo churn, CAC payback, sales cycle, implementation/support cost, expansion revenue |
| Usage / API / cloud | billable unit | `Revenue = billable units × price per unit` | usage growth, price/unit, cost/request or cost/token, gross margin/unit, utilization, rate limit, customer concentration, retention |
| Commerce / D2C | order | `Revenue = traffic × conversion × AOV` | CAC, CVR, AOV, COGS, fulfilment, return/refund rate, contribution margin, repeat purchase, LTV, ROAS/MER, inventory turns |
| Financial services | TPV, AUM, loan or policy | `Revenue = volume × fee/yield` | take rate/yield, funding cost, credit/fraud loss, capital and compliance cost, CAC, retention, contribution margin, risk-adjusted return |
| Licensing / IP / content studio | title, licence or project | `Revenue = commissioned/licensed units × price + royalty` | production/localisation/IP-share/distribution/marketing cost, hit rate, slate economics, recoup waterfall, payback, contribution per title |
| Professional services | project or billable hour | `Revenue = billable capacity × utilization × rate` | utilization, rate, labour/subcontract cost, delivery cycle, backlog, renewal, gross margin/project |
| Hardware + services | device and installed base | `Revenue = units × ASP + installed base × attach rate × service ARPU` | unit margin, channel inventory, attach rate, activation, warranty/returns, replacement cycle, service retention |

`ARPU` means average revenue per user. Do not write `APRU`. `CFA` is not universal; define it explicitly for the topic, for example cost per first action, first acquisition or funded account, before using it.

## Calculation rules

For every selected engine:

1. State the atomic unit and formula before presenting a result.
2. Separate observed inputs, sourced benchmarks, analyst assumptions and unavailable inputs.
3. Build downside, base and upside cases using explicit input changes.
4. Show contribution margin and break-even logic, not only gross revenue.
5. Use cohorts or segments when averages hide retention, price or cost differences.
6. Include working capital, capex, content/IP amortization, regulation, fraud or risk loss when material.
7. Connect the model to Continue / Pivot / Kill thresholds in Chapter 5.

When data is missing, do not invent a number. Output the formula, required inputs, credible proxy range if sourced, break-even threshold, confidence and validation plan. A model with visible gaps is acceptable; a fabricated investment case is not.

## Required Chapter 2 outputs

- business-model classification table
- primary and secondary revenue equations
- unit-economics input ledger with source/evidence status
- downside/base/upside scenario table
- contribution-margin or break-even analysis
- the 3–5 variables that most change the decision
- explicit conclusion on whether the current evidence supports an investment model, a conditional model, or only a validation plan
