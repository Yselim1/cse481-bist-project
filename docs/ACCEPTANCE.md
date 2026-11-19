# Requirement and implementation acceptance audit

**Upgrade audit: 27 September 2026.** The instructor-Q&A primary study is documented in `INSTRUCTOR_QA_UPGRADE.md`: a FY2024 post-TMS 29 anchor plus six 2025–2026 Fintables reports supply 238 verified observations; 13 timestamped KAP context events and a completed five-stage fixed-model harness are included. The annual-refresh audit below remains valid as baseline evidence. Final student review, presentation, and rehearsal remain open.

## Requirements from the supplied PDF

IDs and page references correspond to IMPLEMENTATION_PLAN.md, which maps all eight PDF pages.

| ID | Status | Concrete evidence / qualification |
| --- | --- | --- |
| R01 Python/reproducibility | Pass | `src/`, `uv.lock`, config, README, executed notebook; `outputs/verification/reproduction.json` records fresh-environment comparison. |
| R02 BIST100 company | Pass for selection date | User selected THYAO; `data/raw/fintables/membership.json`. Current membership does not prove historical membership. |
| R03 Stock/index OHLCV | Pass with provider gaps disclosed | Three raw market snapshots and metadata; `quality.json`. Missing prices are not filled. Index/stock calendars differ. |
| R04 Indicators/volume | Pass | `analysis/indicators.py`, saved features and technical chart; hand SMA/EMA/RSI/MACD/volume identities and prefix tests. |
| R05 Automatic support/resistance | Pass | `analysis/levels.py`, `pivots.csv`, `zones.csv`; right-window confirmation and prefix tests. |
| R06 Income statement | Pass | Revenue, gross profit, derived EBITDA, operating profit, parent net profit; original report page 11, transcription and verified normalized CSV. |
| R07 Balance sheet | Pass | Cash, financial debt, net debt, assets, equity; liquidity and capital inputs from original pages 9-10; documented formulas. |
| R08 Cash flow | Pass | Signed annual operating/investing/financing cash flows from original page 13; cash-flow identities reconciled. |
| R09 Growth | Pass within captured basis | Revenue/EBITDA/earnings year-over-year; nonpositive comparison bases remain unavailable. |
| R10 Profitability | Pass within declared definitions | ROE/ROA with average parent equity/assets, EBITDA/net margins. Currency translation and parent-profit conventions disclosed. |
| R11 Leverage/liquidity | Pass within declared definitions | Net debt/EBITDA, debt/equity, current and quick ratios. Quick ratio excludes inventory only. |
| R12 Valuation | Pass within annual inputs | Raw TRY price times nominal shares, divided by available original TRY accounts; P/E/P/B/EV-EBITDA. Main ratios require no FX conversion. |
| R13 Fundamental score | Pass | Five component points, 710 complete evaluation sessions out of 749, explicit missingness and strict source policy. Loss-year comparison bases remain unavailable. |
| R14 Combined strategy | Pass | Config, stateful BUY/SELL/HOLD rules, reasons, input snapshots and next-open orders. |
| R15 No-look-ahead backtest | Pass for declared annual source scope | Causal features, verified release dates, first-session-after-release joins, dated comparative revisions and next-open costs. FY2020 comparatives enter with the FY2021 release. Source/currency correction followed inspection of earlier USD results; the chronological parameter holdout is not a pristine blind experiment. |
| R16 Benchmarks/metrics | Pass for labeled annual-refresh study | Four-way comparison, required return/drawdown/Sharpe/win-rate/difference metrics, costs, exposure, annual evaluation and gross counterfactual. |
| R17 Actual MCP AI agent | Pass | Actual Codex smoke/full/missing-data sessions, JSONL calls and actual explanations; `docs/MCP_DEMO.md`; separate stdio equality verification. |
| R18 Visuals/explanation | Pass with explicit limitations | HTML/Markdown/PDF report, three checked charts, actual results tables; conclusions acknowledge underperformance and limited sample. |
| R19 Submission categories | **Presentation deferred** | Eight implementation categories supplied; classroom slides and rehearsal deferred by the user. See inventory below. |

## Verification coverage

`scripts/verify_reproduction.py` runs the tests and lint in its calling interpreter, rebuilds both source policies offline, and compares all features, full-period/annual JSON metrics and daily ledgers with the saved snapshot. JSON metrics must match exactly. Daily CSV round-tripping allows 1e-9 TRY absolute / 1e-11 relative tolerance. Source hashes are checked before analysis.

| Planned check | Actual coverage |
| --- | --- |
| V01 source shape/validation | Multilevel ticker selection; empty/duplicate/missing column; nonfinite/zero price; invalid range/volume rejection; frozen live-source validation. |
| V02 units and period arithmetic | Turkish decimal/percentage parsing, negative parentheses, source scale applied once, annual/YTD TTM identity; raw/adjusted price identity; original TRY valuation without FX. |
| V03 release/revision timing | Release-day exclusion, later revision unavailable earlier, strict exclusion of unverified values; actual original-report values and revision-boundary tests. Source authenticity also has a separate documentary audit. |
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

The test suite contains 22 focused tests. Separate source review visually checked 16 statement pages and reconciled 40 balance, profit and cash-flow identities exactly. Hash checks cover originals, transcription, release evidence and normalized data. This is targeted coverage, not exhaustive testing or proof of provider infallibility or real-world execution.

## Deliverable inventory (PDF p. 8)

| Category | Location | Status |
| --- | --- | --- |
| Python source / notebook | `src/`, `scripts/`, `tests/`, `notebooks/THYAO_walkthrough.ipynb` | Implemented; notebook has nine executed code cells and zero errors |
| README / setup | `README.md`, `pyproject.toml`, `uv.lock`, `.env.example` | Implemented and fresh-environment checked |
| Proposal | `docs/PROPOSAL.md` | Draft ready; unknown names/deadline not invented |
| Final report | `outputs/verified_only/report.html`, `.md`; `output/pdf/THYAO_Term_Project_Report.pdf` | Printable report and source/method qualifications; visual QA recorded separately |
| Fintables table/dataset | `data/raw/fintables/originals/`, `data/processed/fintables_original_observations.csv`, financial/ratio tables | Four originals, verified dates, 136 observations, 17 metrics, dated comparative revisions |
| Backtest tables | `outputs/retrospective/` and `outputs/verified_only/` | Both modes, baselines, annual tests, sensitivity, orders and ledgers |
| Charts | `outputs/verified_only/figures/` | Technical/levels/RSI/MACD, scores, equity/drawdown |
| MCP demonstration | `outputs/agent/`, `docs/MCP_DEMO.md`, `outputs/verification/mcp_protocol.json` | Real calls and explanations plus failure case; trace is the recorded backup |
| Classroom presentation | Not yet created | Explicitly deferred by user; duration and course details unknown |

## Completed original-source gate and remaining scope

The user's FY2021-FY2024 downloads are retained unchanged under `data/raw/fintables/originals/`. Their Fintables URLs, SHA256 hashes, PDF pages, publication notices, identities and comparative changes are recorded in `docs/ORIGINALS_AUDIT.md` and `originals_manifest.json`. All company financial values come exclusively from these Fintables-hosted documents; KAP is used only for release metadata.

The FY2021 original supplies FY2020 comparatives, available from March 2022. A separate FY2020 attachment is unnecessary for this declared study. FY2025 annual statements were unavailable during the 2025 trading period and are excluded. The original TRY presentation is preserved because a single annual FX rate cannot exactly reverse monthly income translation. No further downloads are needed for the implemented annual scope.

Earlier USD results and explanations are preserved in `outputs/archive_pre_originals/` and the separate retrospective configuration. They document the correction history. Strategy thresholds were unchanged; the correction is not a controlled experiment isolating one input.

The remaining user-deferred phase is presentation preparation and rehearsal. Administrative fields such as student names and the submission deadline remain unfilled. Any later expansion to quarterly reports, inflation-adjusted outcomes or other stocks is additional research, not a hidden requirement for the completed annual implementation.
