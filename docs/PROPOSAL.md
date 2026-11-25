# Project proposal

| | |
| --- | --- |
| **Course** | CSE481 Engineering Economics |
| **Team members** | Yavuz Selim Gezginci 20210808028 |
| **Instructor** | Doç. Dr. Alper Özcan |
| **Submission deadline** | 30.11.2026 |

## Title and question

**Explainable analysis of Turkish Airlines using Python, Fintables and an MCP AI agent.** Does an annual financial filter change the exposure, risk, trading activity and returns of a technical strategy for THYAO.IS? Compare combined trading with technical-only trading, buy-and-hold and BIST100. Do not assume that additional financial inputs improve returns.

## Scope

The user selected Turkish Airlines. It has accessible financial history, significant lease/debt exposure, foreign-currency reporting and cyclical profitability. Selection-date BIST100 membership is documented. This is one selected company, not an unbiased stock-selection experiment.

Use 2021–2022 price warm-up and 2023–2025 evaluation, reserving 2025 from parameter selection. Use FY2021-2024 original Fintables-hosted annual statements, including FY2020 comparatives, and apply release-aware historical alignment. No company financial values are substituted from another provider.

## Methodology

1. Validate prices, corporate actions, missing dates and currency conventions; preserve files and hashes.
2. Import financial records with period, annual/YTD/quarter type, units, source, publication and vintage status.
3. Calculate SMA, EMA, RSI, MACD and volume. Confirm pivots after the right window becomes observable; cluster only eligible trailing prices.
4. Calculate growth, profitability, leverage, liquidity and valuation; expose score components and missingness.
5. Encode explicit stateful rules with next-open execution and declared costs.
6. Report full-period/annual results, risk, activity and benchmarks; publish predeclared 2023–2024 sensitivity variants without optimizing the holdout.
7. Expose the same Python calculations through read-only MCP. Demonstrate a genuine AI host and test absent data/invalid requests.

## Data limitation

The completed implementation uses four original reports with 136 verified observations and actual publication dates. Comparative revisions enter only when released. The original TRY presentation is nominal and exchange-rate-sensitive. Annual refresh omits interim reports; one stock, few trades and simplified execution limit inference. Source/currency correction followed inspection of the earlier USD study, so 2025 is a chronological parameter holdout rather than a pristine blind test.

## Deliverables and sequence

Package, lockfile, CLI, source and normalized data, executed notebook, analysis charts/tables, strategy, backtests, report, actual MCP trace/answer, setup guide and acceptance audit. Presentation preparation/rehearsal follows implementation as requested. ML is excluded from the core scope.

Scope/source audit -> tested foundation -> data/analysis -> strategy/accounting -> baselines/sensitivity -> MCP demo -> report/notebook/clean reproduction -> presentation review. These are dependencies, not an eight-week calendar schedule.
