## THYAO.IS as of 2021-01-15

**The tool returned HOLD with no existing position, while all scores and historical fundamentals were unavailable.** This is an academic demonstration, not investment advice.

| BIST MCP tool | Result |
|---|---|
| `get_stock_history` | Actual market session: **2021-01-15**. Adjusted synthetic close: **12.9730215073 TRY**; raw close: **13.279999733 TRY**. |
| `get_fundamental_metrics` | Status: `missing`. All financial figures and ratios were null. Financial period, availability date, age and source were also unavailable. |
| `calculate_scores` | Fundamental, technical and combined scores, including their components, were unavailable. Fundamental label: `incomplete`. |
| `generate_signal` | With `holding=false`: **HOLD**, reason `technical_warmup_or_no_support`. No order was executed. |

### Historical availability and assumptions

- **Missing means unavailable, not zero.** No financial period or actual release date can be assigned to this as-of result.
- `generate_report` lists stored financial periods from **2020-12-31 through 2025-12-31**. Having a stored period does not establish its availability on **2021-01-15**.
- Fundamentals use **Fintables-displayed USD**; market prices use **TRY**. No currency conversion or outside calculation was performed.
- The vintage policy is **retrospective**: historical financial vintages are unverified and may contain revisions. Some releases use an assumed **following-June-30** date rather than a verified publication date. Strict mode excludes unverified inputs. These results do **not** establish point-in-time validation.

### Costs and execution

The tools specify **10 bps commission per side**, **5 bps slippage per side**, and **100,000 TRY** initial capital. Decisions occur at the close, with execution modeled at the next stock-session open. Whole-lot execution and taxes are not modeled; returns are nominal TRY, with zero cash yield and zero-risk-free Sharpe assumptions.

### Bounded invalid-symbol demonstration

`get_stock_history(ticker="INVALID.IS", as_of="2021-01-15")` returned `isError=true`:

> INVALID_SYMBOL: this case study only supports THYAO.IS

### Local report

`generate_report` read the existing [retrospective report](C:/Users/yavuz/Desktop/CSE481-Term-Project/outputs/retrospective/report.md). Its performance period is **2023-01-02 through 2025-12-31**, so it is not a report of performance as of the requested date. The tools also flag single-stock selection/survivorship bias and differing stock/index return bases.