# Findings and how to explain them

**Final study:** THYAO, 2023-2025 trading; verified original annual Fintables statements; financial amounts and returns in nominal TRY. Latest annual period at 2025-12-31 is FY2024, released 2025-02-28 and usable from 2025-03-03.

## Financial business picture

| Metric | TRY millions |
| --- | --- |
| revenue | 745,430.00 |
| gross_profit | 142,908.00 |
| ebitda | 136,256.00 |
| operating_profit | 80,393.00 |
| net_profit | 113,378.00 |
| cash | 95,992.00 |
| financial_debt | 489,939.00 |
| net_debt | 236,664.00 |
| total_assets | 1,399,606.00 |
| equity | 679,887.00 |
| operating_cash_flow | 135,580.00 |
| investing_cash_flow | 10,003.00 |
| financing_cash_flow | -75,360.00 |

Revenue increased **47.79%** to TRY745.43 billion. Derived EBITDA increased **18.08%** to TRY136.256 billion. Revenue grew faster than operating cash earnings: EBITDA margin declined from 22.88% to **18.28%**. This is growth in nominal TRY presentation; it must not be described as real or functional-USD growth.

Parent net profit declined **30.44%** to TRY113.378 billion despite higher revenue. The FY2023 income statement (PDF page 11) shows TRY73.456 billion of net deferred-tax income, including a TRY91.694 billion inflation-adjustment component offset by other deferred-tax expense. FY2024's net deferred-tax income is TRY5.281 billion. This large comparison-base effect is a concrete reason not to interpret the net-profit decline solely as weaker airline operations. Pre-tax profit increased from TRY91.282 billion to TRY121.421 billion. These figures are read from the same Fintables-hosted originals.

Operating cash flow is TRY135.580 billion versus TRY113.378 billion parent earnings. Investing cash flow is a **TRY10.003 billion net inflow**, while capital purchases still consumed TRY43.963 billion. The investing subtotal includes TRY39.515 billion from other asset/investment movements and TRY37.304 billion interest received, as well as outflows. Positive investing cash flow therefore does not mean no capital spending. Financing cash flow is a TRY75.360 billion net outflow. All cash-flow descriptions follow PDF page 13.

Cash is TRY95.992 billion, financial debt TRY489.939 billion and net debt TRY236.664 billion. The net-debt formula subtracts financial investments as well as cash. Net debt/EBITDA is **1.74x**, below the declared 4x threshold. Much of borrowing is aircraft lease debt. Current ratio **1.01x** and quick ratio **0.94x** indicate a small cushion under these simplified definitions; quick ratio removes inventory only and can overstate liquidity where prepayments or other illiquid assets matter.

| Metric | Value |
| --- | --- |
| revenue_growth | 47.79% |
| net_profit_growth | -30.44% |
| ebitda_growth | 18.08% |
| roe | 19.94% |
| roa | 9.26% |
| ebitda_margin | 18.28% |
| net_margin | 15.21% |
| net_debt_ebitda | 1.74 |
| debt_equity | 0.72 |
| current_ratio | 1.01 |
| quick_ratio | 0.94 |
| pe | 3.27 |
| pb | 0.54 |
| ev_ebitda | 4.46 |

ROE **19.94%** narrowly misses the strict >20% point; ROA is **9.26%**. Both use average balances and parent profit. Small rounding or definition changes can matter near thresholds, so the sensitivity evidence and precise definitions are more useful than a confident label.

P/E **3.27x**, P/B **0.54x** and EV/EBITDA **4.46x** use the **31 December 2025 price** with the latest available **FY2024 accounts**. They are not year-end-2024 valuation ratios or proof of undervaluation. The stock close is TRY268.50 and nominal market capitalization is TRY370.53 billion. FX gaps do not invalidate these TRY ratios; the optional USD market-cap column remains missing where FX is missing.

## Final rule decision

The fundamental points are sales growth, leverage and P/E below its prior median: **F=3/5**. Profit growth and ROE do not pass. Technical points are RSI in range and proximity to confirmed support: **T=2/5**. Combined score is **0.48**.

SMA20 is 271.1625 and SMA50 is 276.64, so the required upward trend is absent. RSI is 42.62, but MACD is below its signal and relative volume is only 0.69. The rule returns **HOLD for a flat position**, meaning remain in cash. This is a historical model decision, not an executed order or current recommendation.

## Backtest findings

| Strategy | Return | Max drawdown | Sharpe (rf=0) | Closed trades | Win rate | Exposure | Sessions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| combined | 65.32% | -13.85% | 1.08 | 8 | 87.50% | 20.16% | 749 |
| technical | 61.19% | -13.16% | 1.0 | 11 | 63.64% | 26.70% | 749 |
| buy_hold | 92.73% | -25.61% | 0.75 | 0 | Unavailable | 100.00% | 749 |
| bist100 | 102.24% | -22.86% | 0.97 | — | Unavailable | Unavailable | 746 |

TRY100,000 becomes **TRY165,317.12** under the combined strategy, after modeled costs. It exceeds technical-only return by **4.13 percentage points**, but trails buy-and-hold and BIST100. Its maximum drawdown is slightly deeper than technical-only drawdown, although much smaller than buy-and-hold's drawdown. Thus there is no across-the-board dominance.

The strategy holds a position for **20.16%** of sessions and completes **eight trades**, seven profitable. That small sample limits what the 87.5% win rate can establish. Low exposure reduces participation in sustained stock appreciation and also changes risk. Zero interest on idle cash is consequential in a high-inflation market.

The gross return using the **same executions** is **69.33%**, compared with 65.32% net. Modeled commission totals TRY2,115.87 and slippage TRY1,057.95; their opportunity/compounding effect contributes to the endpoint difference. A fresh zero-cost strategy run can change stop decisions, so it is a different comparison.

| Year | Combined return % | Technical return % | Buy/hold return % | BIST100 return % |
| --- | --- | --- | --- | --- |
| 2023 | 15.26 | 15.48 | 60.29 | 34.15 |
| 2024 | 24.81 | 23.98 | 20.16 | 30.34 |
| 2025 | 8.26 | 6.43 | -2.77 | 14.24 |

Each year starts independently with TRY100,000 and no position, retaining prior feature history. The annual returns therefore need not compound to the continuous full-period result. Predeclared 2023-2024 sensitivities are in `outputs/verified_only/sensitivity.csv`; no winner replaces the baseline.

## What changed from the first analysis

The earlier displayed-USD, current-vintage study returned 26.24% for combined trading. Original TRY statements and real release dates produce different earnings growth, valuation histories and entry/exit decisions. The current analysis does not attribute the whole change to publication dates or claim that verification improved investment performance. It corrects the empirical source basis. Old data, results and model recordings remain preserved.

The conclusion to defend is modest: adding this annual fundamental rule changed trading behavior; in this sample it modestly exceeded technical-only return but lagged long exposure to the stock and index. Source tracing, causal timing, reproducibility and honest interpretation are the project's stronger contributions.
