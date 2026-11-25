# THYAO project upgrade after the instructor Q&A

**Status date:** 27 September 2026  
**Primary study:** 1 January 2025 to 25 September 2026  
**Company:** Turkish Airlines (`THYAO.IS`)  
**Benchmark:** BIST 100 price index (`XU100.IS`)  
**Financial source:** Fintables-hosted original statements only  
**Context source:** timestamped KAP disclosures viewed through Fintables  

## 1. What changed and why

The instructor clarified three points that materially improve the original implementation:

1. Yahoo Finance is an example rather than a mandatory source. We retained it because the required THYAO, BIST 100, and USD/TRY histories are available and now fully documented through 25 September 2026.
2. KAP disclosures are appropriate timestamped context. We added a separate context layer for financial reports, fleet decisions, investments, and partnerships. This text does not replace numerical fundamentals or alter the strategy.
3. Older nominal statements should not be mixed directly with post-TMS 29 inflation-adjusted statements. The primary study now uses one internally consistent accounting basis from 2025 onward. The older annual study remains a baseline, clearly separated in configuration and output directories.
4. The architecture experiment must hold the model constant and add reliability controls in stages. A five-stage fixed-model harness, deterministic evaluator, evidence gate, state file, memory file, and human-review queue are implemented.

The instructor permits tests from 1 January 2025 to November 2026. The implementation uses all market data available at the status date: 1 January 2025 through the last completed session on 25 September 2026. It can be refreshed to November without changing the design.

## 2. Primary data implementation

### 2.1 Original reports

The primary importer uses a previously verified FY2024 Fintables original as the annual anchor plus six signed-in 2025–2026 Fintables attachments:

| Report | Financial period | Disclosure time (Europe/Istanbul) | Parsed statement pages |
| --- | --- | --- | --- |
| FY2024 anchor | 31 December 2024 | 28 February 2025 08:00 | 9, 10, 11, 13 |
| 2025 Q1 | 31 March 2025 | 28 April 2025 18:20 | 2, 3, 4, 6 |
| 2025 Q2 | 30 June 2025 | 5 August 2025 19:15 | 3, 4, 5, 8 |
| 2025 Q3 | 30 September 2025 | 7 November 2025 08:02 | 2, 3, 4, 7 |
| FY2025 | 31 December 2025 | 4 March 2026 18:55 | 9, 10, 11, 13 |
| 2026 Q1 | 31 March 2026 | 29 April 2026 18:20 | 2, 3, 4, 6 |
| 2026 Q2 | 30 June 2026 | 5 August 2026 08:00 | 3, 4, 5, 8 |

`src/bist_analytics/data/tms29.py` unwraps the validated Fintables byte envelope in memory, reads the four relevant statements from each PDF, parses current and comparative columns, and creates typed observations. The output contains 238 verified rows across 17 metrics and eleven period ends.

Every source record retains:

- the financial period and whether it is YTD, annual, or instant;
- the original million-TRY value and a single scale to full TRY;
- the verified disclosure date;
- the original Fintables attachment URL;
- the Fintables/KAP release-evidence URL;
- the exact statement page;
- the accounting basis; and
- explanatory notes for derived EBITDA, debt, net debt, and share count.

The manifest stores SHA-256 hashes for both the downloaded envelope and PDF payload. A changed source file therefore fails before analysis.

### 2.2 Accounting checks

For the current and comparative column of every report, the importer checks:

- total assets = current assets + non-current assets;
- total assets = total sources;
- gross profit = revenue + signed cost of sales; and
- opening cash + net cash change = closing cash.

There are 56 checks and every residual is zero at the reports' TRY 1 million precision. These checks detect wrong pages, wrong columns, sign errors, and number-format parsing errors.

### 2.3 Same-basis TTM construction

Quarterly income and cash-flow figures are YTD. For an interim period, the analysis reconstructs trailing twelve months as:

`current YTD + prior annual − corresponding prior YTD`

The code filters all inputs to the latest observation's `TMS29-THY-TFRS-consolidated-TRY` basis before applying this formula or calculating year-over-year growth. This prevents the mixing problem described by the instructor.

At 25 September 2026, the latest available period is 30 June 2026. The modeled TTM figures include:

| Metric | TTM or period-end value |
| --- | ---: |
| Revenue | TRY 1,132,505 million |
| Parent net profit | TRY 112,059 million |
| Financial debt | TRY 914,234 million |
| Net debt | TRY 620,378 million |

Net debt follows the Fintables company-summary convention for this dataset: bank and lease debt minus cash and current financial investments. The older annual baseline used a different documented convention that also subtracted non-current investments; the studies are kept separate.

## 3. Timestamped KAP context layer

`data/raw/kap/thyao_context_events.csv` contains 13 reviewed events with exact timezone-aware timestamps, category, title, concise summary, source URL, and evidence status. It includes the six financial reports and seven company events:

- Air Europa talks, accepted offer, agreement, and Spanish approval;
- the September 2025 Boeing fleet disclosure;
- the April 2026 biofuel investment; and
- the September 2026 Boeing 737 MAX order.

`src/bist_analytics/data/context.py` validates the schema and source domain, rejects duplicate IDs, and returns only events known by a requested instant. A boundary test proves that the 23 September 2026 event is absent one second before 18:19 Istanbul time and present at that timestamp.

The MCP server exposes `get_context_events`. Context is evidence for explaining what was happening around a date. It is deliberately absent from technical points, fundamental points, entry rules, exit rules, and order generation. This implements the instructor's stated objective: text is timestamped contextual evidence, not a substitute for numerical financial data.

## 4. Primary backtest implementation

`config/tms29.yaml` freezes the primary experiment:

- market warm-up from 1 January 2021;
- evaluation from 1 January 2025 to exclusive 26 September 2026;
- verified post-TMS 29 observations in TRY;
- maximum financial age of 230 days;
- the same technical, scoring, cost, slippage, stop, and holding assumptions used by the baseline.

The market cache contains 1,436 THYAO sessions, 1,430 BIST 100 sessions, and 1,491 USD/TRY dates from 2021 through 25 September 2026. The run manifest records source/code hashes and the exact configuration.

Signals are decided at the close and executed at the next THYAO open. Pivots become available only after their right-hand confirmation window. Financial observations become available at the first THYAO close strictly after their publication date. These timing rules prevent obvious look-ahead bias.

### 4.1 Primary results

| Case | Cumulative return | Maximum drawdown | Sharpe (rf=0) | Closed trades | Exposure |
| --- | ---: | ---: | ---: | ---: | ---: |
| Combined | -11.03% | -13.66% | -0.76 | 4 | 6.64% |
| Technical-only | 6.42% | -15.45% | 0.29 | 13 | 34.55% |
| THYAO buy-and-hold | 5.29% | -24.40% | 0.25 | 0, one open | 100% |
| BIST 100 price index | 30.85% | -17.06% | 0.76 | — | — |

The combined rule underperformed the BIST 100 by 41.88 percentage points. It made only four trades and had 6.64% exposure, yet still lost money. The result does not establish predictive power or an investable advantage. It shows that the strict financial filter substantially reduced participation and selected poor entry periods in this sample.

On 25 September 2026, the model has:

- latest financial period: 30 June 2026;
- financial availability date: 6 August 2026;
- fundamental score: 1/5;
- technical score: 3/5;
- combined score: 0.44;
- close: TRY 290.75;
- SMA20: 294.1375;
- SMA50: 303.52;
- RSI14: 45.57; and
- flat-position rule action: `HOLD`, reason `trend_filter`.

Here `HOLD` means no new position while flat. It is not an instruction to hold a real portfolio position.

## 5. Five-stage harness experiment

The implementation compares the instructor's exact sequence:

1. **Raw LLM** — no project tools; the prompt requires null rather than guessed facts.
2. **LLM + Tools** — read-only MCP tools supply fundamentals, indicators, scores, signal, backtest, and context.
3. **Tools + Stateful Harness** — the same model and tools receive immutable as-of, evaluation-window, and position state; run state and hashes are persisted.
4. **+ Evidence/Quality Gate** — the candidate must exactly match seven numerical facts, dates, financial period, signal, context event, actual tool calls, and the no-advice rule.
5. **+ Memory + Human Review** — reviewed project constraints are injected from `data/harness/memory.json`; a human-review record must approve or reject the gated candidate.

All stages use `gpt-6-luna` with low reasoning effort and the same question. `data/harness/answer.schema.json` forces a directly comparable result shape. `src/bist_analytics/harness/evaluation.py` scores numerical exactness, evidence coverage, temporal validity, constraint compliance, unsupported tool claims, and overall gate status. `scripts/run_harness_experiments.py` saves the answer, full JSONL trace, stderr, SHA-256 hashes, state transitions, scores, comparison, and review queue.

The live external run was completed after explicit user authorization. No synthetic LLM outputs were used. The raw LLM correctly returned null rather than guessing and scored 0% numerical exactness and 0% evidence coverage. Every tool-enabled stage scored 100% numerical exactness, 100% evidence coverage, valid point-in-time dates, full constraint compliance, and no unsupported tool claim. This particular case therefore shows the large benefit of tools; state, gate, and memory preserved the correct result rather than improving a tool answer that was already exact. The value of the evidence gate is still concrete: it rejected an earlier misconfigured annual-dataset run before the configuration was corrected.

The fifth stage remains `pending_human_review` after a successful model run. This is intentional: software cannot honestly claim that a human reviewed its own output. The student completes the review by checking the saved candidate, scores, evidence trace, clarity, limitations, and presentation suitability.

## 6. Requirements comparison

| Homework/Q&A requirement | Implementation evidence | Status |
| --- | --- | --- |
| Select BIST 100 company | THYAO selection and membership evidence | Complete |
| Reliable market and index history | Yahoo snapshot, dates, adjustments, hashes, missing-session policy | Complete |
| Technical indicators | SMA, EMA, RSI, MACD, volume measures | Complete |
| Automatic support/resistance | causal confirmed pivots and trailing clustering | Complete |
| Fintables financial analysis | FY2024 anchor plus six later reports, 238 verified rows | Complete |
| Avoid incompatible accounting-period mixing | single basis filter and same-basis TTM reconstruction | Complete |
| Growth, profitability, leverage, liquidity, valuation | calculated snapshots with explicit denominator policy | Complete |
| Explainable scoring and signals | five technical and five fundamental points; explicit rules | Complete |
| Bias-aware backtest | publication lag, pivot confirmation, next-open execution | Complete |
| Benchmarks and metrics | technical ablation, buy-and-hold, BIST 100; return/risk/trade metrics | Complete |
| KAP/news context | 13 exact-timestamp events plus read-only MCP tool | Complete |
| Speech-to-text | instructor allows selected examples; no approved recording supplied | Optional extension |
| MCP AI agent | read-only bounded tools using the same calculation layer (ten at this upgrade; 20 in the final submission) | Complete |
| Five harness architectures | fixed-model traces, state, gate, memory, scores, review queue | Complete; final student review pending |
| Machine learning | original brief treats this as optional | Not selected |
| Presentation | requested after implementation | Next phase |

## 7. Reproduction

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/tms29.yaml import-tms29
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/tms29.yaml run
.\.venv\Scripts\python.exe -m pytest
```

The first two commands need no network with the cached inputs. A deliberate market refresh uses:

```powershell
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/tms29.yaml fetch --refresh
```

After explicit approval for external model transmission, the architecture experiment uses:

```powershell
.\.venv\Scripts\python.exe scripts\run_harness_experiments.py
```

Primary results are under `outputs/tms29_primary/`. Annual baseline results are under `outputs/annual_baseline/`. Harness evidence is under `outputs/harness/`.

## 8. Verification completed

- 27 automated tests pass.
- The seven-vintage import produces 238 verified observations.
- All 56 financial-statement identities reconcile.
- Exact reviewed June 2026 values match the normalized dataset.
- Context timestamp boundaries are tested.
- The quality gate accepts exact, fully evidenced output and rejects an altered return.
- The primary and annual-baseline pipelines both reproduce successfully from the shared 2021–2026 market cache.
- Primary reports, figures, ledgers, quality files, and run manifests are generated.

## 9. Presentation points to emphasize later

The strongest presentation story is architectural reliability:

1. The source problem was solved with original Fintables attachments and hash-addressed evidence.
2. The TMS 29 comparability problem was solved by a separate accounting basis and same-basis TTM construction.
3. Look-ahead risks were addressed at three layers: financial release timing, pivot confirmation, and next-open execution.
4. KAP text was treated as timestamped context, never as invented numerical data.
5. The strict combined strategy reduced risk and exposure but did not beat the benchmark; this is an honest result.
6. The harness experiment measures how tools, state, evidence gates, memory, and human review change reliability while holding the model fixed.

The result should be presented as a reproducible engineering and financial-analysis system, not as a profitable trading recommendation.
