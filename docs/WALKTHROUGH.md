# Implementation walkthrough

The implementation is finished for the agreed one-company annual-refresh scope. This guide follows the path from a downloaded report to a trading decision and result. Start with `README.md` for environment commands, then follow these steps. Presentation slides and rehearsal are the next phase, as requested.

## 1. Read the requirement map

`IMPLEMENTATION_PLAN.md` maps the eight-page course PDF to requirements R01-R19 and the implementation dependencies. `docs/ACCEPTANCE.md` lists the concrete outputs and tests. The project includes Python, Fintables financial analysis, technical indicators, automatic support/resistance, scoring, a strategy, backtesting and a genuine MCP-connected AI explanation. ML is optional and excluded.

## 2. Inspect the frozen decisions

`config/project.yaml` selects THYAO.IS, the original TRY financial dataset, verified-only eligibility, a 2021 market warm-up and 2023-2025 evaluation. `docs/DECISIONS.md` explains each threshold and the later source correction. The strategy was not tuned to achieve the final return. Read the source-correction note before describing 2025 as a holdout.

## 3. Verify the four originals

Open `output/pdf/originals/THYAO_2024_original.pdf`, then PDF pages 9, 10, 11 and 13. Match those pages to `data/raw/fintables/originals/transcription.json`. These readable copies preserve the exact PDF payload; the downloaded receipts, including their small wrapper, remain in `data/raw/fintables/originals/`. Repeat for FY2021-2023 if reviewing the complete source trail. `release_evidence.json` records public release metadata, and `originals_manifest.json` pins exact file hashes. `docs/ORIGINALS_AUDIT.md` explains all 40 reconciliations, the wrapper format, currency decision and revisions.

All historical company financial values come from Fintables-hosted files. Publication metadata from KAP does not replace Fintables financial values. The missing standalone FY2020 attachment is resolved by the FY2020 comparative in the FY2021 original, dated at the later release.

## 4. Rebuild financial observations

Run `.\.venv\Scripts\python.exe -m bist_analytics.cli import-originals`.

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

| decision_date | execution_date | side | fill_price | commission | reason |
| --- | --- | --- | --- | --- | --- |
| 2023-05-10 | 2023-05-11 | BUY | 123.442156 | 99.9001 | combined_entry |
| 2023-06-05 | 2023-06-06 | SELL | 160.128893 | 129.59019 | rsi_exit |

The first entry decision is 2023-05-10, executed 2023-05-11 at adjusted TRY123.442156. The RSI exit is decided 2023-06-05 and executed 2023-06-06 at TRY160.128893. Cash after exit is TRY129,460.60. These are simulated adjusted units and fills, not actual brokerage orders. Trace the same dates across `features.csv`, `combined_signals.csv`, `combined_orders.csv`, `combined_trades.csv` and `combined_daily.csv`.

## 10. Read the comparisons correctly

| Strategy | Return | Max drawdown | Sharpe (rf=0) | Closed trades | Win rate | Exposure | Sessions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| combined | 65.32% | -13.85% | 1.08 | 8 | 87.50% | 20.16% | 749 |
| technical | 61.19% | -13.16% | 1.0 | 11 | 63.64% | 26.70% | 749 |
| buy_hold | 92.73% | -25.61% | 0.75 | 0 | Unavailable | 100.00% | 749 |
| bist100 | 102.24% | -22.86% | 0.97 | — | Unavailable | Unavailable | 746 |

Technical-only trading is an ablation with its own T>=4 entry rule and no fundamental exits; combined trading is not necessarily a subset of its trades. Buy-and-hold has an open final position, so closed-trade win rate is unavailable. BIST100 is a price index with no trading costs. Returns are nominal TRY, cash earns zero and Sharpe uses zero risk-free return. Read `docs/FINANCIAL_INTERPRETATION.md` for the business and strategy findings.

## 11. Reproduce the complete result

Run `.\.venv\Scripts\python.exe -m bist_analytics.cli run`, followed by `scripts/sensitivity.py` using the same Python. The run writes features, snapshots, zones, orders, trades, daily ledgers, annual/full metrics, charts and report text to `outputs/verified_only/`. `run_manifest.json` pins source/code/config/lock hashes. Use `--config config/retrospective.yaml run` only to reproduce the separate earlier USD study.

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
