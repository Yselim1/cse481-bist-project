## THYAO.IS — as of 2025-12-31

**Rule signal: HOLD with `holding=false`**, meaning remain out of the position. `generate_signal` identifies the blocking reason as `trend_filter`; this is an academic rule output, not an executed order.

### Evidence

- **Technical:** Actual market date is **2025-12-31**. Adjusted and raw close were **TRY 268.50**, below fast/slow SMAs of **271.1625 / 276.64**. RSI was **42.6210**, MACD histogram **−0.0781**, and relative volume **0.6947**, consistent with weak trend and momentum. Support/resistance were **TRY 267.75 / 269.8642**, with `in_zone=false`; pivots require five subsequent sessions for confirmation before use. Sources: `get_stock_history`, `calculate_indicators`, `find_support_resistance`.
- **Fundamental:** The active annual financial period is **2024-12-31**, available from **2025-03-03**, aged **303 days**. Revenue growth was **0.477861**, net-profit growth **−0.304442**, ROE **0.199408**, net-debt/EBITDA **1.736907**, and P/E **3.268094**. Growth, leverage and valuation earned rule points; profit growth and ROE did not. Fundamental score was **3**, labelled **neutral**; technical score **2**, combined score **0.4800**. Sources: `get_fundamental_metrics`, `calculate_scores`.

### Backtest

Requested interval: **2023-01-01 to exclusive 2026-01-01**. Actual observations: **2023-01-02–2025-12-31**, with **749** stock sessions and **746** benchmark sessions (**3** missing).

Values below are tool-returned **decimal ratios**, rounded for display; returns are cumulative.

| Strategy / baseline | Return | Max drawdown | Zero-risk-free Sharpe | Closed-trade win rate |
|---|---:|---:|---:|---:|
| Combined | 0.653171 | −0.138531 | 1.077510 | 0.875000 |
| Technical | 0.611860 | −0.131559 | 0.995015 | 0.636364 |
| THYAO buy-and-hold | 0.927259 | −0.256145 | 0.750385 | Unavailable |
| BIST100 price index | 1.022394 | −0.228609 | 0.965241 | Unavailable |

Source: `run_backtest`, corroborated by `generate_report`. Combined and technical strategies closed **8** and **11** trades respectively. Buy-and-hold had **0** closed trades and **1** open trade; its missing win rate is not zero.

### Units, costs and validation limits

Both price and financial currencies are **TRY**; financial amounts use TRY units and stock execution uses adjusted synthetic units. Returns are nominal TRY, with **zero cash yield**. Initial capital is **TRY 100,000**; commission is **10 bps per side**, slippage **5 bps per side**. Decisions occur at close with next stock-session open execution. Stock results include modeled costs; BIST100 is a cost-free price-index baseline. Taxes and whole-lot execution are not modeled.

The **`verified_only`** policy uses publication-lagged annual statements and dated comparative revisions. `generate_report` records **136 verified observations**, **0 unverified rows**, and **0 assumed-release rows**, covering annual periods **2020–2024**. Interim reports are outside this annual-refresh strategy.

**Verified source vintages do not validate investment performance.** The strategies showed smaller drawdowns but lower cumulative returns than both baselines. Small trade samples, stock-selection/survivorship bias, differing benchmark return bases, inflation and currency translation limit interpretation. Source/currency corrections followed inspection of earlier USD results, so **2025 is a chronological parameter holdout, not a pristine blind test**. These results establish no investable advantage.

`generate_report` retrieved the existing report without writing files: [Local report](C:/Users/yavuz/Desktop/CSE481-Term-Project/outputs/verified_only/report.md).