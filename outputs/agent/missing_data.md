## THYAO.IS — as of 2021-01-15

**The tools returned HOLD with no existing position, alongside unavailable fundamentals and scores.** This is an academic demonstration; it does not establish an investable advantage.

| BIST tool | Result |
|---|---|
| `get_stock_history` | Actual market session: **2021-01-15**. Adjusted synthetic close: **12.9730215073 TRY**; raw close: **13.279999733 TRY**. |
| `get_fundamental_metrics` | `financial_status: missing`. All financial figures and ratios are **unavailable**, as are the financial period, release/availability date, source, and age. |
| `calculate_scores` | Fundamental, technical, and combined scores—and all component points—are **unavailable**. Fundamental label: `incomplete`. |
| `generate_signal` | **HOLD**, with `holding: false`; reason: `technical_warmup_or_no_support`. This represents staying out under the supplied position state, not an executed order. |

### Historical availability and units

`project_status` identifies **Fintables**, active fundamental currency **TRY**, and policy **`verified_only`**. Prices also use **TRY**, with adjusted synthetic units.

`get_fundamental_metrics` uses publication-lagged fundamentals. Its missing result means no eligible fundamentals were returned for this historical cutoff; **missing values are unavailable, not zero**. A financial period end must not be treated as its release date.

`generate_report` lists annual financial periods **2020-12-31, 2021-12-31, 2022-12-31, 2023-12-31, and 2024-12-31**, with **136 verified vintage rows**, **0 unverified rows**, and **0 assumed-release rows**. Original annual vintages and comparative revisions are dated; interim reports are outside this annual-refresh strategy. These archive statistics do not supply a financial release date or usable figures for **2021-01-15**.

### Costs and validation limits

Tool execution assumptions specify **10 basis points commission per side**, **5 basis points slippage per side**, and **100000 TRY** initial capital. Decisions occur at the close, with execution at the next stock-session open. Taxes and whole-lot execution are not modeled; cash yield and the Sharpe risk-free rate are zero.

The saved report evaluates **2023-01-02 through 2025-12-31**, separately from this historical query. Verified annual source vintages establish data provenance, not validated investment performance. Tools flag single-stock selection/survivorship bias, nominal TRY inflation and currency-translation effects, and differing benchmark/stock return bases. They also identify **2025** as a chronological parameter holdout, not a pristine blind test, because source/currency corrections followed inspection of earlier USD results.

### Bounded invalid-symbol demonstration

`get_stock_history(ticker="INVALID.IS", as_of="2021-01-15")` returned:

> `INVALID_SYMBOL: this case study only supports THYAO.IS`

Local saved report, identified by read-only `generate_report`: [report.md](C:/Users/yavuz/Desktop/CSE481-Term-Project/outputs/verified_only/report.md).

Only BIST MCP tools were called; no outside calculations or file edits were performed.