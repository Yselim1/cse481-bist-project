# Requirement and implementation acceptance audit

**Audit date: 15 September 2026.** The working software and retrospective research package are implemented. A validated point-in-time financial backtest is **not complete** because original-release Fintables values and several release dates remain unverified. The user has deferred classroom presentation and rehearsal until after implementation. No instructor exception or approval is assumed.

## Requirements from the supplied PDF

IDs and page references correspond to IMPLEMENTATION_PLAN.md, which maps all eight PDF pages.

| ID | Status | Concrete evidence / qualification |
| --- | --- | --- |
| R01 Python/reproducibility | Pass | `src/`, `uv.lock`, config, README, executed notebook; `outputs/verification/reproduction.json` records fresh-environment comparison. |
| R02 BIST100 company | Pass for selection date | User selected THYAO; `data/raw/fintables/membership.json`. Current membership does not prove historical membership. |
| R03 Stock/index OHLCV | Pass with provider gaps disclosed | Three raw market snapshots and metadata; `quality.json`. Missing prices are not filled. Index/stock calendars differ. |
| R04 Indicators/volume | Pass | `analysis/indicators.py`, saved features and technical chart; hand SMA/EMA/RSI/MACD/volume identities and prefix tests. |
| R05 Automatic support/resistance | Pass | `analysis/levels.py`, `pivots.csv`, `zones.csv`; right-window confirmation and prefix tests. |
| R06 Income statement | Pass as retrospective source table | Revenue, gross profit, derived EBITDA, operating profit, parent net profit; Fintables TSVs and normalized CSV. |
| R07 Balance sheet | Pass as retrospective source table | Cash, financial debt, net debt, assets, equity; extra liquidity and capital inputs; documented formulas. |
| R08 Cash flow | Pass as retrospective source table | Signed annual operating/investing/financing cash flows and report table. |
| R09 Growth | Pass within captured basis | Revenue/EBITDA/earnings year-over-year; nonpositive comparison bases remain unavailable. |
| R10 Profitability | Pass within declared definitions | ROE/ROA with average parent equity/assets, EBITDA/net margins. Currency translation and parent-profit conventions disclosed. |
| R11 Leverage/liquidity | Pass within declared definitions | Net debt/EBITDA, debt/equity, current and quick ratios. Quick ratio excludes inventory only. |
| R12 Valuation | Qualified | Raw-price and same-date FX market cap, annual earnings/equity and net debt; P/E/P/B/EV-EBITDA. Inputs are current financial vintages, not verified original history. |
| R13 Fundamental score | Pass as software; qualified historical inputs | Five component points, 626 complete evaluation sessions, explicit missingness and source policy. Strict mode has zero eligible sessions. |
| R14 Combined strategy | Pass | Config, stateful BUY/SELL/HOLD rules, reasons, input snapshots and next-open orders. |
| R15 No-look-ahead backtest | **Partially met** | Causal features, delayed publication join, revision tests and next-open costs pass. Original-release financial values and four actual release dates are unverified. Full historical no-look-ahead claim remains open. |
| R16 Benchmarks/metrics | Pass for labeled retrospective study | Four-way comparison, required return/drawdown/Sharpe/win-rate/difference metrics, costs, exposure, annual holdout and gross counterfactual. |
| R17 Actual MCP AI agent | Pass | Actual Codex smoke/full/missing-data sessions, JSONL calls and actual explanations; `docs/MCP_DEMO.md`; separate stdio equality verification. |
| R18 Visuals/explanation | Pass with explicit limitations | HTML/Markdown/PDF report, three checked charts, actual results tables; conclusions acknowledge underperformance and limited sample. |
| R19 Submission categories | **Pending final presentation and source qualification** | Eight implementation categories supplied; classroom slides and rehearsal deferred by the user. See inventory below. |

## Verification coverage

`scripts/verify_reproduction.py` runs the tests and lint in its calling interpreter, rebuilds both source policies offline, and compares all features, full-period/annual JSON metrics and daily ledgers with the saved snapshot. JSON metrics must match exactly. Daily CSV round-tripping allows 1e-9 TRY absolute / 1e-11 relative tolerance. Source hashes are checked before analysis.

| Planned check | Actual coverage |
| --- | --- |
| V01 source shape/validation | Multilevel ticker selection; empty/duplicate/missing column; nonfinite/zero price; invalid range/volume rejection; frozen live-source validation. |
| V02 units and period arithmetic | Turkish decimal/percentage parsing, negative parentheses, source scale applied once, annual/YTD TTM identity; raw/adjusted price identity. |
| V03 release/revision timing | Release-day exclusion in session alignment, later revision unavailable earlier; unverified values excluded by strict mode. This tests software, not provider-vintage authenticity. |
| V04 incomplete inputs | No initial backfill, staggered financial input availability, unavailable growth without comparison, missing FX left null. |
| V05 indicator arithmetic | SMA/EMA/RSI/MACD hand identities, flat/increasing/decreasing RSI and constant relative volume. |
| V06 causal levels | Correct right-window confirmation, fixed-history prefix invariance and bounded nonchaining clusters. |
| V07 invalid scores | Missing/negative denominator behavior, negative EBITDA cannot earn a leverage point, incomplete F remains null. |
| V08 position rules | Entry/hold/exit, no repeated buy, cooldown after exit, stale-data exit and technical-only independence. |
| V09 execution accounting | Hand next-open gap, two-sided commission/slippage, fixed-execution gross counterfactual, no invented final fill. |
| V10 boundary performance | No trades, always long, constant equity, open final trade, missing execution price rejected. |
| V11 benchmark identity | Zero-cost always-long equity equals initial capital times close/first open; open trades excluded from win rate. |
| V12 metrics | Known cumulative return/drawdown/Sharpe, initial-capital high-water mark, zero-volatility/no-closed-trade nulls. |
| V13 future independence | Technical/zone prefixes, price-future perturbation of past orders, P/E median excludes today/future; release revision fixtures. |
| V14 offline reproducibility | Fresh `.verify-venv` installed from frozen lock; both policies' features, annual/full metrics and ledgers compared. |
| V15 real agent/protocol | Nine read-only tools discovered, eight stdio checks; actual AI sessions and numerical narrative audit. |
| V16 ML | Not applicable: optional ML was excluded from the baseline. |

The test suite contains 19 focused tests. This is targeted coverage of accounting/timing failures, not a claim of exhaustive software testing. Provider correctness, original financial vintages, exact historical FX translation and real-world execution are not proven by unit tests.

## Deliverable inventory (PDF p. 8)

| Category | Location | Status |
| --- | --- | --- |
| Python source / notebook | `src/`, `scripts/`, `tests/`, `notebooks/THYAO_walkthrough.ipynb` | Implemented; notebook has nine executed code cells and zero errors |
| README / setup | `README.md`, `pyproject.toml`, `uv.lock`, `.env.example` | Implemented and fresh-environment checked |
| Proposal | `docs/PROPOSAL.md` | Draft ready; unknown names/deadline not invented |
| Final report | `outputs/retrospective/report.html`, `.md`; `output/pdf/THYAO_Term_Project_Report.pdf` | Eight-page report, visually checked; data qualification remains prominent |
| Fintables table/dataset | `data/raw/fintables/`, `data/processed/fintables_observations.csv`, financial/ratio tables | Captured and normalized; current-vintage limitation |
| Backtest tables | `outputs/retrospective/` and `outputs/verified_only/` | Both modes, baselines, annual tests, sensitivity, orders and ledgers |
| Charts | `outputs/retrospective/figures/` | Technical/levels/RSI/MACD, scores, equity/drawdown |
| MCP demonstration | `outputs/agent/`, `docs/MCP_DEMO.md`, `outputs/verification/mcp_protocol.json` | Real calls and explanations plus failure case; trace is the recorded backup |
| Classroom presentation | Not yet created | Explicitly deferred by user; duration and course details unknown |

## Remaining source work and exact next action

The collection contains 17 metrics for each year 2020-2025. Current table histories may include revisions. Two publication dates are verified (FY2023 and FY2025); four are modeled at the following June 30. FY2025 is outside the trading period and does not affect 2025 signals.

To close the primary historical-validation gate while respecting **Fintables-only** financial sourcing:

1. Obtain the original annual THYAO financial attachments for FY2020-FY2024 **through Fintables**, plus their dated release notices. These years supply warm-up, comparisons and evaluation inputs. The existing FY2023 notice provides timing, not original-value verification.
2. Save them under `data/raw/fintables/originals/`, retaining each Fintables URL and publication date. A current spreadsheet export alone does not prove original vintages; contemporaneous report attachments or a genuine archived export are needed.
3. Reread every required source line independently, reconcile display currency/accounting bases and derive the same ratios. Enter actual dates and verified source references in the financial template. Mark `vintage_verified=true` only after those checks. No other website's company financial values may be substituted.
4. Preserve the current retrospective snapshot, replace the processed observations with verified records, run `run --strict`, then regenerate metrics/report/notebook and the MCP explanation. Compare the revised result honestly; do not preserve the current profit figures as targets.

Fintables' FY2024 attachment opened in its browser PDF viewer, but direct automated download returned HTTP 403 and the viewer did not expose extractable text through the available interface. No protection was bypassed. A user-initiated download of these Fintables originals is the practical next step. This unresolved evidence requirement is distinct from signing in, which succeeded.

An instructor may accept a clearly labeled retrospective educational study, but that acceptance has not been requested or granted here. Keep this audit and the report's qualification visible until the source gate is resolved.

### Attachment follow-up

The signed-in annual menus now provide verified links for FY2021-FY2024; see `DOWNLOAD_ORIGINALS.md`. The FY2020 menu explicitly says `Ek bulunamadı.` (No attachment found). FY2020 comparative values in the FY2021 original may be sufficient for the 2023-2025 study if entered with the FY2021 report's actual publication date and comparable basis. This is a possible documented alternative to a standalone FY2020 report, not a verified completion or permission to backdate values. Files and dates must still be audited after download.
