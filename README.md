# THYAO research with Python, Fintables and a real MCP agent

CSE481 term project for **Turkish Airlines (THYAO.IS)**. The package imports Fintables financials, caches Yahoo prices, calculates technical/fundamental evidence, backtests explicit rules and exposes the same calculations to an AI host.

**The primary implementation follows the instructor's post-TMS 29 guidance.** It uses 238 verified observations parsed from a FY2024 annual anchor plus six 2025–2026 Fintables-hosted reports, preserves current and comparative vintages, and evaluates 2025 through 25 September 2026. The earlier FY2020–FY2024 annual study remains an independently reproducible baseline. Financial values use their original TRY presentation. See `docs/INSTRUCTOR_QA_UPGRADE.md` for the upgrade and `docs/ORIGINALS_AUDIT.md` for the annual baseline.

## Start here

- `docs/DOWNLOAD_ORIGINALS.md`: receipt status, Fintables attachment links and archive details.
- `docs/INSTRUCTOR_QA_UPGRADE.md`: post-TMS 29 implementation, KAP context, harness design, results, and requirement mapping.
- `docs/LOCAL_MODEL.md`: Ollama + Qwen 2.5 stack for the fully-local agent.
- `docs/LOCAL_SETUP.md`: fresh-machine reproduction (Python env + Ollama + full harness).
- `docs/MODEL_CARD.md`: fine-tuned LoRA adapter — training config, data, §30 limitations.
- `docs/HARNESS_RERUN.md`: five-stage A–E harness re-run instructions with the local model.
- `training/COLAB_RUNBOOK.md`: Colab T4 cell-by-cell QLoRA training walkthrough.
- `outputs/tms29_primary/report.html`: primary 2025–2026 report and charts.
- `output/pdf/originals/`: four standard PDF copies for direct reading; exact original PDF content, with only the download wrapper removed. Rebuild with `scripts/extract_original_pdfs.py`.
- `docs/WALKTHROUGH.md`: source-to-result code tour with a real trade example and findings.

- `outputs/verified_only/report.html`: readable report with charts and results.
- `outputs/verified_only/report.md`: report text.
- `output/pdf/THYAO_Term_Project_Report.pdf`: verified eight-page printable report.
- `notebooks/THYAO_walkthrough.ipynb`: executed nine-code-cell walkthrough, zero errors.
- `outputs/agent/analysis_demo.md` and `.jsonl`: earlier Codex-host explanation and MCP trace (development history; the submission agent is the local `bist-qwen`).
- `docs/DECISIONS.md`: frozen parameters and methodological limitations.
- `docs/DATA_SOURCES.md`: source URLs, units and release/vintage evidence.
- `docs/FINANCIAL_INTERPRETATION.md`: earnings, cash generation, liquidity, valuation and strategy interpretation.
- `outputs/agent/recorded_demo.html`: expandable offline viewer of genuine MCP calls and explanations.
- `TASKS.md`: acceptance status; presentation and rehearsal follow implementation.
- `docs/ACCEPTANCE.md`: requirement mapping and final verification evidence.

## Reproduce offline in the existing environment (PowerShell)

From the project directory:

```powershell
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/tms29.yaml import-tms29
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/tms29.yaml run
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/project.yaml import-originals
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/project.yaml run
.\.venv\Scripts\python.exe scripts/sensitivity.py
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/retrospective.yaml run
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\ruff.exe check src tests scripts
.\.venv\Scripts\python.exe scripts/verify_mcp.py
.\.venv\Scripts\python.exe scripts/verify_reproduction.py
.\.venv\Scripts\python.exe scripts/audit_agent_evidence.py
```

These commands need no network or Fintables login. They regenerate outputs from cached sources. `config/tms29.yaml` selects the primary study; `config/project.yaml` selects the annual baseline; `config/retrospective.yaml` reproduces the earlier USD table study.

To regenerate the executed notebook and PDF, run `scripts/build_notebook.py` and then `scripts/build_pdf.py` with the same Python. The PDF reads the verified-only report and sensitivity outputs. `scripts/build_findings.py` refreshes the source audit, financial interpretation and walkthrough. Poppler is only needed for visual QA, not to create or read the report. `outputs/verification/reproduction.json` records a separate fresh-environment offline comparison of all features, annual/full metrics and daily ledgers.

`scripts/package_project.py` creates `output/THYAO_Implementation_Package.zip` and `SUBMISSION_MANIFEST.json`. It includes source, cached data and deliverables; local environments, caches and authentication files are excluded. The package includes the four originals and their audit. The 1.9 GB merged model file `training/bist_lora.gguf` and the legacy cloud-LLM runs in `outputs/harness_codex_archive/` are left out; the GGUF's hash is recorded under `external_files` in the manifest and the file is provided separately. Presentation slides are in `outputs/deliverables/`. Annual refresh, nominal TRY, small trade sample and execution limitations remain disclosed.

## Fresh setup

Python 3.12 is the tested interpreter. Using a trusted installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install uv==0.12.15
.\.venv\Scripts\uv.exe sync --frozen --extra dev --python .\.venv\Scripts\python.exe
```

`uv.lock` pins dependencies, including MCP 2.2.0, pandas 3.0.5 and yfinance 1.7.0. The project uses MCP SDK v2, not FastMCP v1. No host-specific bundled runtime path is required in the analysis code.

## Data refresh and imports

```powershell
.\.venv\Scripts\python.exe -m bist_analytics.cli fetch --refresh
.\.venv\Scripts\python.exe -m bist_analytics.cli template
```

`fetch --refresh` updates Yahoo THYAO.IS, XU100.IS and TRY=X prices and provenance. Yahoo may revise history, so preserve the submitted snapshot before refreshing. Fintables collection uses authorized tables/exports; no login scraper or bypass is included.

`import-tms29` validates seven PDF vintages, checks 56 statement identities, and writes 238 observations to `data/processed/fintables_tms29_observations.csv`. `import-originals` independently rebuilds the 136-observation annual baseline. `import-fintables` rebuilds the old displayed-USD TSV study. No importer overwrites another dataset. The calculation layer reconstructs TTM flows from same-basis YTD and annual observations. See `docs/DATA_DICTIONARY.md`.

## Method

- Market warm-up from 2021; primary evaluation 2025–25 September 2026. Calendar-year tests restart flat and are reported separately.
- SMA20/50, EMA20/50, RSI14, MACD12/26/9, relative volume, volume change and OBV.
- Five-session-confirmed pivots and trailing price clusters; no future-confirmed zones in earlier decisions.
- Five-point technical/fundamental scores; combined `.6*T/5 + .4*F/5`; explicit missingness and freshness.
- Persistent position state, next-open executions, fees/slippage, close-based stop and holding limit.
- Combined, technical-only, stock buy-and-hold and BIST100 price-index comparison. Cumulative return, drawdown, Sharpe, win rate, exposure, costs and benchmark differences.

See `docs/DECISIONS.md` for all thresholds. Strategy parameters are not selected on 2025 returns. The source/currency correction occurred after the earlier USD results were inspected, so 2025 is a chronological parameter holdout, not a pristine blind test. Cash earns zero; returns are nominal TRY. Missing benchmark sessions stay missing. A zero-cost **strategy rerun** can change stop dates because slippage changes entry prices; it is not a fixed-trade estimate of fees alone.

## Actual MCP AI agent

Twenty-one read-only tools expose status, history, indicators, zones, fundamentals, scores, signal, backtest, saved report and timestamped KAP context, plus the benchmark index, reversal events, sector ranking, weekday tests, fundamental change, macro context, news, speech features, data-quality checks, evidence bundles and a BM25 knowledge-base search (RAG). The scenario tools also return their comparisons precomputed (sector laggard/leader, highest/lowest weekday, best reversal family, the label each rule gives, the price reaction around a statement's publication), so the model copies results instead of computing them. The TCMB/TÜİK macro and speech tools are built, but no data for them is cached in this submission, so they return empty values. Inputs are bounded; outputs contain dates, units, warnings and missing values. No tool trades.

```powershell
.\.venv\Scripts\python.exe -m bist_analytics.mcp.server
```

The submission agent is the locally hosted fine-tuned model `bist-qwen` (Qwen 2.5 3B + LoRA), served by Ollama on localhost; no cloud AI is called:

```powershell
ollama create bist-qwen -f training/Modelfile.finetuned
.\.venv\Scripts\python.exe scripts/run_presentation_scenarios.py      # the five pre-run scenario traces
.\.venv\Scripts\python.exe scripts/ask.py "<question>"                 # live question, same settings
.\.venv\Scripts\python.exe scripts/local_agent.py --smoke --model bist-qwen
```

`ask.py` and the scenario runner use the settings the model was fine-tuned with: no tool schemas (the model writes `<tool_call>` text, as in its training data), the presentation system prompt, knowledge-base context, and a 4,500-character tool-result cap. Each run writes a full execution trace with a figure-grounding audit; see `docs/PRESENTATION.md`. Without `--model` (or `BIST_LOCAL_MODEL`), `local_agent.py` uses the base `qwen2.5:7b-instruct`; it launches the MCP server as a stdio child process and, by default, passes the tools in OpenAI tool-calling format. Tools explicitly advertise read-only, idempotent, closed-world behavior. See `docs/LOCAL_MODEL.md` and `docs/MODEL_CARD.md`. `scripts/run_agent_demo.py` is the earlier Codex CLI runner; its sessions in `outputs/agent/analysis_demo.*` are kept as development history.

`verify_mcp.py` separately checks the real stdio protocol and equality with direct Python output. It does not call an LLM and is labeled accordingly. Host setup and audit: `docs/MCP_DEMO.md`.

## Project layout

`config/` parameters; `data/raw/` sources; `data/processed/` normalized observations; `src/bist_analytics/` code; `tests/` arithmetic/timing checks; `scripts/` reproduction utilities; `notebooks/` walkthrough; `outputs/` results, charts, manifests and traces; `output/pdf/` printable report; `docs/` proposal, source dictionary and acceptance evidence.

Profitability is not an acceptance criterion. Accurate implementation and transparent evidence are.
