# Implementation Task Tracker

**Companion specification:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)  
**Current state:** Post-TMS 29 implementation, KAP context, primary backtest, and the five-stage fixed-model harness are complete. The final harness candidate is pending student human review. See `docs/INSTRUCTOR_QA_UPGRADE.md`.  
**Selected scope:** Turkish Airlines; Fintables-only numerical fundamentals; FY2024 annual anchor plus six 2025–2026 reports; primary evaluation from 2025 through 25 September 2026. The annual and earlier USD studies remain separate baselines. Presentation/rehearsal follows the final human review.  
**Use:** Check an item only when its output and verification evidence exist. Record owner, evidence path and any blocker under the milestone. Milestones are not fixed calendar deadlines.

## M0 - Scope and feasibility (4-6 hours)

- [ ] M0.1 **ADMINISTRATIVE FOLLOW-UP:** Record names, final deadline, presentation language/duration and any instructor amendments before classroom submission; these details did not block the agreed implementation.
- [x] M0.2 Choose a preferred company from the shortlist, audit its data feasibility, and record selection-date BIST 100 membership evidence and sector rationale.
- [x] M0.3 **COMPLETE: four originals and release metadata verified.** Inspect Fintables access and historical period coverage; verify source values, publication evidence and data-vintage feasibility using representative records.
- [x] M0.4 Identify available MCP host/model access and a feasible local connection route.
- [x] M0.5 Freeze initial company, intended window and exclusions before inspecting strategy returns; create decision log.
- [x] M0.6 Draft the project proposal with research question, methodology, evaluation, deliverables and schedule.

**Exit evidence:** Proposal draft, decision log, preliminary data-coverage inventory, named host/access route. Historical-fundamental gaps have a concrete resolution path.

**Evidence / qualifications:** See docs/ACCEPTANCE.md and docs/DECISIONS.md. Implementation by Codex in the shared workspace; user selected the company and enabled Fintables access. Original annual vintages are verified; interim refresh and real-world execution remain scope limitations.

## M1 - Foundation and early MCP connection (6-10 hours)

**Depends on:** M0.

- [x] M1.1 Initialize repository and proposed Python package structure; preserve the source PDF and planning files.
- [x] M1.2 Create `pyproject.toml`, virtual environment, tested dependency lock, ignore rules and environment-variable example.
- [x] M1.3 Define config models, data contracts, logging, run IDs and source/hash manifest shape.
- [x] M1.4 Add the command-line entry point and minimal test/lint commands.
- [x] M1.5 Implement one tiny MCP tool and confirm a real LLM host discovers and calls it; record tested SDK/host versions.
- [x] M1.6 Document working Windows setup commands and sample non-secret host configuration.

**Exit evidence:** Fresh environment imports the package, basic checks pass, genuine host-to-tool call captured. No future CLI command is documented as working before it exists.

**Evidence / qualifications:** See docs/ACCEPTANCE.md and docs/DECISIONS.md. Implementation by Codex in the shared workspace; user selected the company and enabled Fintables access. Original annual vintages are verified; interim refresh and real-world execution remain scope limitations.

## M2 - Data collection and historical alignment (18-26 hours)

**Depends on:** M0-M1. Fundamental collection and market adapter work can be assigned to different team members once schemas agree.

- [x] M2.1 Implement explicit Yahoo download parameters, column normalization, cache, retries and provenance.
- [x] M2.2 Validate and snapshot stock OHLCV plus corporate actions/adjustment data; verify index symbol, identity and coverage.
- [x] M2.3 Create the Fintables entry template and data dictionary with periods, units, bases, release times, vintages and source references.
- [x] M2.4 Collect income statement, balance sheet, cash flow, all required ratios and supporting calculation inputs.
- [x] M2.5 **COMPLETE: 16 statement pages visually reviewed, 40 identities reconciled, units and comparatives checked.** Independently reread source records against entered values; resolve scaling and period-basis mismatches.
- [x] M2.6 Implement comparable quarter/TTM construction, historical valuation inputs and invalid-value flags.
- [x] M2.7 Create eligible release snapshots and backward availability joins with no initial backfill.
- [x] M2.8 Generate missingness, freshness and complete-history coverage reports; finalize usable dates and record deviations.
- [x] M2.9 Pass V01-V04 and save raw/normalized snapshots and manifest.

**Exit evidence:** Validated source datasets; every required financial category accounted for; demonstrably available historical inputs for the chosen test window. Missing historical eligibility blocks the primary combined test.

**Evidence / qualifications:** See docs/ACCEPTANCE.md and docs/DECISIONS.md. Implementation by Codex in the shared workspace; user selected the company and enabled Fintables access. Original annual vintages are verified; interim refresh and real-world execution remain scope limitations.

## M3 - Technical and fundamental analysis (12-18 hours)

**Depends on:** M2.

- [x] M3.1 Implement SMA/EMA/RSI/MACD and volume features with documented warm-up conventions.
- [x] M3.2 Implement five-session-confirmed pivots and causal trailing price clustering.
- [x] M3.3 Export dated zone snapshots, support/resistance distances and a diagnostic chart.
- [x] M3.4 Compute/reconcile growth, profitability, leverage, liquidity and valuation metrics.
- [x] M3.5 Implement five-component fundamental score, eligibility/coverage, historical valuation benchmark and reason records.
- [x] M3.6 Implement normalized technical and combined scores; validate complete-history coverage.
- [x] M3.7 Pass V05-V07 and V13; draft report analysis/method sections with real tables.

**Exit evidence:** Verified indicators, zones, financial analysis and explainable score table with sources. Every historical output is causal within the fixed snapshot.

**Evidence / qualifications:** See docs/ACCEPTANCE.md and docs/DECISIONS.md. Implementation by Codex in the shared workspace; user selected the company and enabled Fintables access. Original annual vintages are verified; interim refresh and real-world execution remain scope limitations.

## M4 - Trading strategy (8-12 hours)

**Depends on:** M3.

- [x] M4.1 Encode versioned entry/exit thresholds, weights, freshness, risk and holding rules in configuration.
- [x] M4.2 Implement BUY/SELL/HOLD and persistent position state, with exit precedence and next-session orders.
- [x] M4.3 Save signal reasons and the exact input values/periods for each decision.
- [x] M4.4 Implement the technical-only ablation with shared execution/risk conventions.
- [x] M4.5 Pass V08; inspect synthetic entry, hold, exit, stale-data and conflicting-condition examples.
- [x] M4.6 Predeclare the sensitivity runs, evaluation split and inactivity flags; document sector/threshold rationale.

**Exit evidence:** Testable strategy specification and verified state transitions. No tuning on the final holdout.

**Evidence / qualifications:** See docs/ACCEPTANCE.md and docs/DECISIONS.md. Implementation by Codex in the shared workspace; user selected the company and enabled Fintables access. Original annual vintages are verified; interim refresh and real-world execution remain scope limitations.

## M5 - Backtesting and evaluation (14-20 hours)

**Depends on:** M4.

- [x] M5.1 Implement adjusted-price next-open simulation, cash/units, slippage, fees and final mark-to-market.
- [x] M5.2 Export daily equity, executed orders, closed/open trades and signal-to-fill timing.
- [x] M5.3 Implement stock buy-and-hold and matched BIST index reference with explicit return-basis labels.
- [x] M5.4 Compute required financial metrics plus activity, exposure, costs and unrealized P&L.
- [x] M5.5 Pass V09-V14, including manual gap/cost ledger and always-long benchmark reconciliation.
- [x] M5.6 Run development/validation sensitivity, record all variants and choose a justified frozen configuration.
- [x] M5.7 **COMPLETE: verified original annual sources, fixed parameters and annual/full outputs; source correction after prior results explicitly disclosed.** Freeze inputs/code/config and evaluate the final holdout; label full-period results separately.
- [x] M5.8 Export equity/drawdown, financial/score plots, performance and sensitivity tables; draft results and limitations.

**Exit evidence:** Reproducible gross/net results, holdout and baselines; meaningful numerical/timing checks pass; all data/return-basis limitations disclosed.

**Evidence / qualifications:** See docs/ACCEPTANCE.md and docs/DECISIONS.md. Implementation by Codex in the shared workspace; user selected the company and enabled Fintables access. Original annual vintages are verified; interim refresh and real-world execution remain scope limitations.

## M6 - MCP AI agent (10-16 hours)

**Depends on:** M1 connection spike and M3-M5 analytics.

- [x] M6.1 Expose core functions through thin typed MCP wrappers with bounded inputs and structured errors.
- [x] M6.2 Return values, units, source periods, dates, warnings and run/artifact identifiers.
- [x] M6.3 Configure agent instructions for tool-based calculations and evidence-linked explanation.
- [x] M6.4 Run a real full analysis request through the chosen host; capture calls and final answer.
- [x] M6.5 Run a missing/stale-data request and verify no financial figures are fabricated.
- [x] M6.6 Pass V15: CLI/MCP numerical equality and manual audit of all numerical narrative claims.
- [x] M6.7 Save a genuine host trace and recorded backup demo; update setup guide and demo script.
- [x] M6.8 Run the instructor's five fixed-model architecture stages; save structured answers, actual tool traces, state, hashes, scores, evidence-gate results and memory.
- [ ] M6.9 **STUDENT REVIEW:** Approve or reject `outputs/harness/memory_human_review.json` using `outputs/harness/HUMAN_REVIEW.md`, then complete `human_review.json`.

**Exit evidence:** Actual agent uses the financial tools, explains their outputs correctly and handles unavailable information honestly. Server-only or mocked demos do not close M6.

**Evidence / qualifications:** See docs/ACCEPTANCE.md and docs/DECISIONS.md. Implementation by Codex in the shared workspace; user selected the company and enabled Fintables access. Original annual vintages are verified; interim refresh and real-world execution remain scope limitations.

## M7 - Final submission and rehearsal (12-18 hours)

**Depends on:** M2-M6.

- [x] M7.1 Complete report and reconcile all reported numbers with saved artifacts.
- [x] M7.2 Complete and execute the walkthrough notebook from a clean kernel.
- [x] M7.3 Verify README environment setup, offline reproduction, online refresh and MCP instructions in a fresh environment.
- [x] M7.4 Finalize proposal, source data/analysis table, results, charts, demo evidence and submission inventory.
- [ ] M7.5 **DEFERRED BY USER.** Prepare the presentation with methodology, findings, limitations and agent demonstration.
- [ ] M7.6 **DEFERRED BY USER.** Rehearse the classroom flow and backup demo within the actual allowed duration.
- [x] M7.7 Audit R01-R19 and all nine PDF deliverable categories; record any instructor-accepted exceptions explicitly.
- [x] M7.8 Freeze the submission version and preserve final manifests, lockfile and reproducibility evidence.

**Exit evidence:** Complete submission package, clean reproduction, accurate report/presentation and accessible demonstration.

**Evidence / qualifications:** See docs/ACCEPTANCE.md and docs/DECISIONS.md. Implementation by Codex in the shared workspace; user selected the company and enabled Fintables access. Original annual vintages are verified; interim refresh and real-world execution remain scope limitations.

## Optional work - Excluded from the current baseline; only after core gates

- [ ] O1.1 Decide whether ML materially helps the research question or is instructor-required.
- [ ] O1.2 Build five-session target with final unlabeled rows removed; verify causal features.
- [ ] O1.3 Implement chronological folds, purged target overlaps/gap, training-only transforms and baseline classifier.
- [ ] O1.4 Evaluate logistic regression and, if warranted, one tree model; pass V16.
- [ ] O1.5 Report classification metrics and an executable financial comparison; preserve holdout discipline.
- [ ] O2.1 Consider a second company only with time for full source-data verification.
- [ ] O2.2 Consider release-aware macro context and predeclared normalized weighting.
- [ ] O2.3 Consider a dashboard that consumes existing analysis outputs.

## Standing acceptance rule

A milestone is complete when its deliverables and exit evidence exist, relevant verification passes, the decision log reflects material changes, and the next milestone can consume its outputs. A profitable result is never an acceptance requirement. An unresolved core requirement remains open even when a fallback demonstration works.

