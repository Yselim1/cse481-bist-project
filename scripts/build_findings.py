"""Write source audit, findings and implementation walkthrough from the frozen outputs."""

import json

import pandas as pd

from bist_analytics.config import load_config, project_root
from bist_analytics.reporting import md_table


def main():
    root = project_root()
    cfg = load_config()
    out = root/"outputs"/cfg.vintage_policy
    manifest = json.loads((root/"data/raw/fintables/originals/originals_manifest.json").read_text())
    quality = json.loads((out/"quality.json").read_text())
    performance = json.loads((out/"performance.json").read_text())
    features = pd.read_parquet(out/"features.parquet")
    latest = features.iloc[-1]
    annual = json.loads((out/"annual_evaluations.json").read_text())
    orders = pd.read_csv(out/"combined_orders.csv")
    source_table = md_table(pd.DataFrame([{"Report":year,"PDF pages":item["pages"],
        "Published":item["published_at"],"Evidence":f"[release]({item['publication_evidence']})",
        "File":f"THYAO_{year}_original.pdf"} for year,item in manifest["files"].items()]))
    audit = f"""# Original financial statement audit

**Completed 15 September 2026.** The four user-downloaded Fintables attachments supply **136 verified observations**: 17 metrics, two year columns, four report vintages. They cover FY2020-2024. No company financial values were imported from any other provider. KAP supplies publication metadata only where needed.

## Receipt and publication

{source_table}

The original bytes remain in `data/raw/fintables/originals/`. `originals_manifest.json` records each Fintables URL, SHA-256, PDF payload hash, page count and publication evidence. The 2023 release is evidenced on Fintables itself; the other three original report notices were checked in KAP's browser interface. Auditor or board approval dates alone were not substituted for publication dates.

The downloaded files contain a 27-byte Java byte-array envelope before `%PDF-`. The importer recognizes only that exact envelope and validates its declared payload length. It never executes Java or deserializes objects. Original receipts are unchanged. Standard PDF copies in `output/pdf/originals/` contain the exact original PDF payload bytes, with only the wrapper removed; they open directly in a PDF reader. `scripts/extract_original_pdfs.py` verifies their hashes against the original manifest. Page counts are 98, 99, 101 and 101.

## Transcription and reconciliation

For each report, **PDF pages 9, 10, 11 and 13** (printed pages 1, 2, 3 and 5) were rendered and visually read in full. They contain assets, liabilities/equity, income and cash flow respectively. `transcription.json` keeps the current and comparative columns, page mapping and all debt/EBITDA components. Monetary inputs are millions of TRY and become full TRY amounts exactly once. Parent-attributable income is used, rather than the nearby consolidated profit line.

Five independent statement identities were checked for all eight columns: assets equal liabilities plus total equity; asset subtotals; revenue less cost of sales equals gross profit; three cash-flow categories equal net cash change; opening cash plus change equals closing cash. **All 40 residuals are zero.** Negative minority equity is preserved where printed. The balance-sheet cash and cash-flow cash definitions can differ; neither is overwritten to force equality.

Derived definitions:

- EBITDA = gross profit + signed administrative expense + signed selling expense + depreciation/amortization adjustment. No separate R&D row is displayed. It is not EBITDAR or an airline-adjusted earnings measure.
- Financial debt = related/unrelated bank borrowing and lease debt, including current portions of long-term liabilities. Other financial liabilities are a separate excluded line, matching the chosen borrowing definition.
- Net debt = financial debt - balance-sheet cash - current financial investments - noncurrent financial investments. This formula does not imply all investments are immediately liquid.
- Nominal shares = paid capital / TRY1: 1.38 billion units. Treasury shares are not subtracted.

## Currency decision

The originals present financial statements in **millions of TRY**, although THY's functional currency is USD. The currency notes state that income is translated using monthly average rates; the balance sheet uses closing rates and historical equity translation. One annual average rate cannot exactly recover functional-USD income. The final study therefore uses the original TRY presentation, without reverse conversion. Valuation combines raw TRY stock price and nominal shares with TRY earnings/equity/debt.

Nominal TRY sales growth is **not** inflation-adjusted growth or functional-USD growth. Currency translation also affects return on average equity/assets. The earlier Fintables-displayed-USD study remains in `outputs/retrospective/`, with its own `config/retrospective.yaml` and original unverified observations. The source/currency correction happened after those earlier results were seen. The strategy thresholds were held fixed; this is not a controlled comparison isolating one data correction, nor a pristine blind 2025 test.

## Dated comparatives

{md_table(pd.DataFrame(manifest['comparative_revisions']))}

All amounts in the revision table are full TRY. FY2020 figures first enter with the containing FY2021 report in March 2022. Later comparative revisions enter only after their containing report's publication. They never overwrite earlier decisions. FY2023's revised asset balance is used in FY2024's ROA average only after the FY2024 release.

The source policy uses the first stock-session **close strictly after the release date**, even for pre-open releases. The close decision then executes at the following open. Annual snapshot availability is 2022-03-02, 2023-03-02, 2024-04-04 and 2025-03-03. This deliberately conservative convention is consistent across reports. FY2025 annual results were released in 2026 and are unnecessary for trading through 2025.

## Scope of verification

The original annual source gate is closed. This is an annual-refresh strategy, not a complete archive of interim disclosures. The unchanged 460-day freshness rule allows all {quality['fundamental_fresh_sessions']} evaluation sessions; {quality['fundamental_complete_sessions']} of {quality['evaluation_sessions']} sessions have all five score inputs. Early FY2021 profit-growth comparison is unavailable because FY2020 was a loss. Missing values remain unavailable. Original-source hashes are checked every time the pipeline runs.

Source verification does not establish a profitable future strategy, perfect provider prices, executable whole-lot trading, or an unbiased stock-selection experiment. These remain limitations, not unresolved file downloads.
"""
    (root/"docs/ORIGINALS_AUDIT.md").write_text(audit,encoding="utf-8")
    findings = f"""# Findings and how to explain them

**Final study:** THYAO, 2023-2025 trading; verified original annual Fintables statements; financial amounts and returns in nominal TRY. Latest annual period at 2025-12-31 is FY2024, released 2025-02-28 and usable from 2025-03-03.

## Financial business picture

{md_table(pd.read_csv(out/'financial_analysis.csv'))}

Revenue increased **47.79%** to TRY745.43 billion. Derived EBITDA increased **18.08%** to TRY136.256 billion. Revenue grew faster than operating cash earnings: EBITDA margin declined from 22.88% to **18.28%**. This is growth in nominal TRY presentation; it must not be described as real or functional-USD growth.

Parent net profit declined **30.44%** to TRY113.378 billion despite higher revenue. The FY2023 income statement (PDF page 11) shows TRY73.456 billion of net deferred-tax income, including a TRY91.694 billion inflation-adjustment component offset by other deferred-tax expense. FY2024's net deferred-tax income is TRY5.281 billion. This large comparison-base effect is a concrete reason not to interpret the net-profit decline solely as weaker airline operations. Pre-tax profit increased from TRY91.282 billion to TRY121.421 billion. These figures are read from the same Fintables-hosted originals.

Operating cash flow is TRY135.580 billion versus TRY113.378 billion parent earnings. Investing cash flow is a **TRY10.003 billion net inflow**, while capital purchases still consumed TRY43.963 billion. The investing subtotal includes TRY39.515 billion from other asset/investment movements and TRY37.304 billion interest received, as well as outflows. Positive investing cash flow therefore does not mean no capital spending. Financing cash flow is a TRY75.360 billion net outflow. All cash-flow descriptions follow PDF page 13.

Cash is TRY95.992 billion, financial debt TRY489.939 billion and net debt TRY236.664 billion. The net-debt formula subtracts financial investments as well as cash. Net debt/EBITDA is **1.74x**, below the declared 4x threshold. Much of borrowing is aircraft lease debt. Current ratio **1.01x** and quick ratio **0.94x** indicate a small cushion under these simplified definitions; quick ratio removes inventory only and can overstate liquidity where prepayments or other illiquid assets matter.

{md_table(pd.read_csv(out/'ratio_analysis.csv'))}

ROE **19.94%** narrowly misses the strict >20% point; ROA is **9.26%**. Both use average balances and parent profit. Small rounding or definition changes can matter near thresholds, so the sensitivity evidence and precise definitions are more useful than a confident label.

P/E **3.27x**, P/B **0.54x** and EV/EBITDA **4.46x** use the **31 December 2025 price** with the latest available **FY2024 accounts**. They are not year-end-2024 valuation ratios or proof of undervaluation. The stock close is TRY268.50 and nominal market capitalization is TRY370.53 billion. FX gaps do not invalidate these TRY ratios; the optional USD market-cap column remains missing where FX is missing.

## Final rule decision

The fundamental points are sales growth, leverage and P/E below its prior median: **F={int(latest.fundamental_score)}/5**. Profit growth and ROE do not pass. Technical points are RSI in range and proximity to confirmed support: **T={int(latest.technical_score)}/5**. Combined score is **{latest.combined_score:.2f}**.

SMA20 is 271.1625 and SMA50 is 276.64, so the required upward trend is absent. RSI is 42.62, but MACD is below its signal and relative volume is only 0.69. The rule returns **HOLD for a flat position**, meaning remain in cash. This is a historical model decision, not an executed order or current recommendation.

## Backtest findings

{md_table(pd.read_csv(out/'performance_table.csv'))}

TRY100,000 becomes **TRY{performance['combined']['final_equity']:,.2f}** under the combined strategy, after modeled costs. It exceeds technical-only return by **{(performance['combined']['cumulative_return']-performance['technical']['cumulative_return'])*100:.2f} percentage points**, but trails buy-and-hold and BIST100. Its maximum drawdown is slightly deeper than technical-only drawdown, although much smaller than buy-and-hold's drawdown. Thus there is no across-the-board dominance.

The strategy holds a position for **20.16%** of sessions and completes **eight trades**, seven profitable. That small sample limits what the 87.5% win rate can establish. Low exposure reduces participation in sustained stock appreciation and also changes risk. Zero interest on idle cash is consequential in a high-inflation market.

The gross return using the **same executions** is **69.33%**, compared with 65.32% net. Modeled commission totals TRY2,115.87 and slippage TRY1,057.95; their opportunity/compounding effect contributes to the endpoint difference. A fresh zero-cost strategy run can change stop decisions, so it is a different comparison.

{md_table(pd.DataFrame([{'Year':y,'Combined return %':round(v['combined']['cumulative_return']*100,2),'Technical return %':round(v['technical']['cumulative_return']*100,2),'Buy/hold return %':round(v['buy_hold']['cumulative_return']*100,2),'BIST100 return %':round(v['bist100']['cumulative_return']*100,2)} for y,v in annual.items()]))}

Each year starts independently with TRY100,000 and no position, retaining prior feature history. The annual returns therefore need not compound to the continuous full-period result. Predeclared 2023-2024 sensitivities are in `outputs/verified_only/sensitivity.csv`; no winner replaces the baseline.

## What changed from the first analysis

The earlier displayed-USD, current-vintage study returned 26.24% for combined trading. Original TRY statements and real release dates produce different earnings growth, valuation histories and entry/exit decisions. The current analysis does not attribute the whole change to publication dates or claim that verification improved investment performance. It corrects the empirical source basis. Old data, results and model recordings remain preserved.

The conclusion to defend is modest: adding this annual fundamental rule changed trading behavior; in this sample it modestly exceeded technical-only return but lagged long exposure to the stock and index. Source tracing, causal timing, reproducibility and honest interpretation are the project's stronger contributions.
"""
    (root/"docs/FINANCIAL_INTERPRETATION.md").write_text(findings,encoding="utf-8")
    tour = f"""# Implementation walkthrough

The implementation is finished for the agreed one-company annual-refresh scope. This guide follows the path from a downloaded report to a trading decision and result. Start with `README.md` for environment commands, then follow these steps. Presentation slides and rehearsal are the next phase, as requested.

## 1. Read the requirement map

`IMPLEMENTATION_PLAN.md` maps the eight-page course PDF to requirements R01-R19 and the implementation dependencies. `docs/ACCEPTANCE.md` lists the concrete outputs and tests. The project includes Python, Fintables financial analysis, technical indicators, automatic support/resistance, scoring, a strategy, backtesting and a genuine MCP-connected AI explanation. ML is optional and excluded.

## 2. Inspect the frozen decisions

`config/project.yaml` selects THYAO.IS, the original TRY financial dataset, verified-only eligibility, a 2021 market warm-up and 2023-2025 evaluation. `docs/DECISIONS.md` explains each threshold and the later source correction. The strategy was not tuned to achieve the final return. Read the source-correction note before describing 2025 as a holdout.

## 3. Verify the four originals

Open `output/pdf/originals/THYAO_2024_original.pdf`, then PDF pages 9, 10, 11 and 13. Match those pages to `data/raw/fintables/originals/transcription.json`. These readable copies preserve the exact PDF payload; the downloaded receipts, including their small wrapper, remain in `data/raw/fintables/originals/`. Repeat for FY2021-2023 if reviewing the complete source trail. `release_evidence.json` records public release metadata, and `originals_manifest.json` pins exact file hashes. `docs/ORIGINALS_AUDIT.md` explains all 40 reconciliations, the wrapper format, currency decision and revisions.

All historical company financial values come from Fintables-hosted files. Publication metadata from KAP does not replace Fintables financial values. The missing standalone FY2020 attachment is resolved by the FY2020 comparative in the FY2021 original, dated at the later release.

## 4. Rebuild financial observations

Run `.\\.venv\\Scripts\\python.exe -m bist_analytics.cli import-originals`.

`data/originals.py` validates receipts, reconciles statement totals, scales millions once and builds 136 observations. Each row has a metric, period, currency, value, release date, source page and vintage. Both report columns are preserved. For example, FY2024 EBITDA is `(142908 - 18675 - 60283 + 72306) * 1,000,000 = TRY136.256 billion`.

The importer writes `data/processed/fintables_original_observations.csv`. Ordinary analysis checks source hashes; it does not silently reimport changed data. The separate `import-fintables` command rebuilds the earlier USD table dataset only.

## 5. Inspect market inputs

`data/raw/market/` holds THYAO.IS, XU100.IS and TRY=X daily files with request metadata and hashes. `data/market.py` validates prices and normalizes provider columns. Raw close is retained for market capitalization. Adjusted synthetic OHLC is used consistently for indicators and simulation. Dividends are not added twice.

The evaluation has 749 stock sessions and 746 index observations with common first/last dates. Three internal index gaps remain missing. FX is optional for the main TRY valuation and missing FX is never filled. Review `quality.json` rather than assuming exchange calendars match.

## 6. Calculate technical features

`analysis/indicators.py` implements SMA20/50, EMA20/50, RSI14 using Wilder smoothing, MACD12/26/9, relative volume, volume changes and OBV. EMA starts from a simple mean. Warm-up nulls are preserved. `analysis/levels.py` confirms pivots only after five following sessions, then clusters eligible prices from the preceding 252 sessions into zones. A future-confirmed pivot cannot affect an earlier signal.

Inspect `outputs/verified_only/figures/technical.png`, `pivots.csv` and `zones.csv`. A pivot's date and the date it becomes knowable are different columns. This distinction is central to the no-look-ahead requirement.

## 7. Join financial data to the trading calendar

`data/fundamentals.py` assigns the first stock-session close strictly after each publication date. `analysis/fundamentals.py` joins snapshots backward: a trading date can use only already-released observations. Later comparative revisions apply prospectively. FY2024 becomes usable on **2025-03-03**, not on 2024-12-31.

Flows are annual totals; balances are instants. Growth compares like periods. Negative prior-year earnings make profit growth unavailable. ROE/ROA use average balances. P/E and P/B use raw TRY price times nominal shares; EV adds net debt. The 460-day freshness rule measures time since annual earnings became available. This annual strategy intentionally omits interim refreshes.

## 8. Read the score components

`analysis/scoring.py` gives one point per declared condition. Fundamental points: revenue growth >15%, profit growth >15%, ROE >20%, net debt/EBITDA <4 and positive P/E no higher than its prior median. The median uses prior valid observations only, with at least 63; today's value is excluded.

Technical points: SMA20>SMA50, RSI35-55, MACD above signal, relative volume>=1 and support proximity. Combined score is `0.6*T/5 + 0.4*F/5`. Entry also needs F>=3, score>=0.70, fresh/complete financials, trend and support. The final date has F=3, T=2 and combined=0.48. Inspect the `f_` and `t_` columns in `features.csv` to explain every point.

## 9. Follow position state and execution

`strategy/rules.py` returns BUY/SELL/HOLD with a reason. Existing positions can exit for a close-triggered 8% loss, 40-session holding limit, stale/missing/weak fundamentals, trend reversal or RSI>=70. Exits take priority. A flat HOLD means no position; it does not mean retain shares.

`backtest/engine.py` executes a close decision at the next stock-session open with 10 bps commission and 5 bps slippage per side. It records cash, units, fees and trade state. Remaining positions are marked at the final close, without inventing a liquidation trade.

### A real simulated trade

{md_table(orders[['decision_date','execution_date','side','fill_price','commission','reason']].head(2).round(6))}

The first entry decision is 2023-05-10, executed 2023-05-11 at adjusted TRY123.442156. The RSI exit is decided 2023-06-05 and executed 2023-06-06 at TRY160.128893. Cash after exit is TRY129,460.60. These are simulated adjusted units and fills, not actual brokerage orders. Trace the same dates across `features.csv`, `combined_signals.csv`, `combined_orders.csv`, `combined_trades.csv` and `combined_daily.csv`.

## 10. Read the comparisons correctly

{md_table(pd.read_csv(out/'performance_table.csv'))}

Technical-only trading is an ablation with its own T>=4 entry rule and no fundamental exits; combined trading is not necessarily a subset of its trades. Buy-and-hold has an open final position, so closed-trade win rate is unavailable. BIST100 is a price index with no trading costs. Returns are nominal TRY, cash earns zero and Sharpe uses zero risk-free return. Read `docs/FINANCIAL_INTERPRETATION.md` for the business and strategy findings.

## 11. Reproduce the complete result

Run `.\\.venv\\Scripts\\python.exe -m bist_analytics.cli run`, followed by `scripts/sensitivity.py` using the same Python. The run writes features, snapshots, zones, orders, trades, daily ledgers, annual/full metrics, charts and report text to `outputs/verified_only/`. `run_manifest.json` pins source/code/config/lock hashes. Use `--config config/retrospective.yaml run` only to reproduce the separate earlier USD study.

The three calendar-year evaluations each start flat and retain preceding feature history. Do not multiply their returns to infer the continuous backtest. Sensitivity is limited to the predeclared development/validation variants; none is selected using 2025 results.

## 12. Inspect the AI connection

`mcp/server.py` exposes nine read-only tools over stdio. The host calls Python for values, then explains the returned data. It cannot place orders. `scripts/run_agent_demo.py` runs a real signed-in Codex host; `outputs/agent/analysis_demo.jsonl` records calls and responses and `analysis_demo.md` stores its actual explanation. `recorded_demo.html` is an offline viewer, not a live model session.

`scripts/verify_mcp.py` independently compares protocol responses with direct Python. A separate real-host missing-data run asks about 2021-01-15 and an invalid ticker. Missing historical values must remain null and unsupported symbols must fail visibly.

## 13. Verify and review

Run the tests and lint, `scripts/verify_reproduction.py`, `scripts/verify_mcp.py` and `scripts/audit_agent_evidence.py`. The 22 tests cover arithmetic, timing, source envelopes/hashes, original comparative revisions, TRY valuation without FX, next-open costs and position state. Fresh-environment reproduction compares complete features, full/annual results and ledgers. It does not claim external providers are infallible.

`scripts/build_notebook.py` executes all nine walkthrough code cells. `scripts/build_pdf.py` builds the printable report, whose rendered pages are visually checked. `scripts/package_project.py` creates the local ZIP and file manifest. Environments, caches and credentials are excluded.

## 14. Explain the result in one paragraph

“We built an auditable THYAO pipeline using original Fintables annual reports and Yahoo market data. Every financial version has a publication date, and trading decisions execute at the next open. The combined strategy returned 65.32%, modestly above technical-only trading but below stock buy-and-hold and BIST100. Its eight trades and low exposure limit generalization. The main contribution is reproducible, explainable analysis with a real MCP AI agent; the experiment does not establish a future trading advantage.”

## 15. Next phase

Implementation and original-source validation are complete for the agreed scope. Team names, final deadline and presentation duration remain administrative details to supply before submission. Presentation structure, slides and rehearsal are intentionally deferred until the user is ready. No instructor acceptance of methodological exceptions is assumed.
"""
    (root/"docs/WALKTHROUGH.md").write_text(tour,encoding="utf-8")
    print("Wrote original-source audit, findings and implementation walkthrough")


if __name__ == "__main__":
    main()
