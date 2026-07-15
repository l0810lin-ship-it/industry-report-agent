# Market Sizing Contract

## Scope before numbers

Every formal Standard or Deep report must size the market with both top-down and bottom-up methods. Before calculating, define:

- category and excluded substitutes
- geography and base/forecast year
- customer and buyer population
- economic layer: consumer spend, advertiser spend, GMV, gross bookings, net revenue, software spend, licence revenue, or another clearly named layer
- currency, nominal/real treatment and tax treatment when material

Never compare or add different economic layers without an explicit conversion.

## Top-down method

Start from a credible total reported by an official, regulatory, company filing or reputable research source, then narrow it through explicit factors:

`TAM/SAM/SOM = reported total × geographic share × segment share × addressable share × realistic capture factor`

Use only factors relevant to the topic. Cite every decision-changing input. If the source defines the market differently, show the bridge rather than treating it as comparable.

## Bottom-up method

Choose the formula by revenue engine:

- Advertising: `addressable users × usage frequency × ad opportunities × fill rate × eCPM / 1,000`
- Subscription: `addressable users × adoption × paid conversion × annual ARPPU`
- Marketplace: `active buyers × orders per buyer × AOV × take rate`
- SaaS: `target accounts × adoption × seats per account × annual price per seat`
- Usage/API: `customers × annual billable units per customer × price per unit`
- Commerce: `addressable buyers × purchase frequency × AOV`
- Licensing/IP/studio: `addressable titles/projects × commission or hit rate × revenue per title/project`
- Services: `addressable customers × projects per customer × average project value`
- Hardware: `annual addressable units × adoption × ASP + installed base service revenue`

For a hybrid model, calculate each engine separately and sum only after removing overlap.

## Reconciliation

Show both methods in one visible table:

| Method | Formula | Inputs and period | Result/range | Evidence status | Confidence |
|---|---|---|---|---|---|

Calculate the divergence ratio:

`Divergence = abs(top-down - bottom-up) / ((top-down + bottom-up) / 2)`

If divergence is greater than 30%, do not mechanically average the results. Diagnose category scope, economic layer, adoption, price, frequency, overlap or source-year differences and state which method is more decision-useful. Prefer ranges over false precision.

## Scenario and evidence rules

- Provide downside, base and upside cases by changing named inputs, not by applying an unexplained percentage haircut.
- Tag each input as observed, sourced benchmark, assumption or unavailable.
- Attach evidence IDs and URLs to sourced inputs.
- State the sensitivity drivers and the minimum evidence needed to narrow the range.
- If inputs are insufficient, provide the formula and data-acquisition plan; do not omit the section or fabricate a point estimate.

## Mode application

- Flash: include the most decision-relevant sizing route and clearly label it directional; use both routes only when evidence is readily available.
- Standard: both methods, reconciliation, three scenarios and confidence are mandatory.
- Deep: Standard requirements plus segmentation, overlap removal, sensitivity analysis and a reproducible calculation ledger.
