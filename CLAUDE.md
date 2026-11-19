# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CSE481 term project. The original THYAO.IS single-ticker research pipeline is still the deepest-worked example, but the repo has grown into a 10-ticker, multi-sector BIST research harness driven by a **locally hosted fine-tuned LLM** (Qwen 2.5 7B + LoRA via Ollama). It imports Fintables financials, caches Yahoo prices, computes technical/fundamental scores, backtests explicit rules, and exposes 19 MCP tools to the agent.

Three studies coexist:
- **Primary THYAO study** (`config/tms29.yaml`): 2025–September 2026, 238 TMS 29 observations, preserved untouched as the "one worked example."
- **Annual baseline** (`config/project.yaml`): FY2020–FY2024 verified-only annuals.
- **Universe 10** (`config/universe10.yaml`): 10 tickers across 5 sectors, used by the four scenario reports and the fine-tuning dataset.

All inference at submission time runs offline through Ollama (`http://localhost:11434`); no cloud LLM calls are made.

## Setup

Python 3.12 is the tested interpreter. The project uses `uv` for dependency management:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install uv==0.12.15
.\.venv\Scripts\uv.exe sync --frozen --extra dev --python .\.venv\Scripts\python.exe
```

`uv.lock` pins all dependencies including MCP SDK v2.2.0 (not FastMCP v1), pandas 3.0.5, and yfinance 1.7.0.

## Common Commands

All commands use the `.venv` interpreter from the project root (PowerShell on Windows):

**Run analysis:**
```powershell
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/tms29.yaml run
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/project.yaml run
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/retrospective.yaml run
```

**Data imports (offline, from cached sources):**
```powershell
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/tms29.yaml import-tms29
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/project.yaml import-originals
```

**Tests and linting:**
```powershell
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\ruff.exe check src tests scripts
```

**MCP server:**
```powershell
.\.venv\Scripts\python.exe -m bist_analytics.mcp.server
```

**Verification scripts:**
```powershell
.\.venv\Scripts\python.exe scripts/verify_mcp.py
.\.venv\Scripts\python.exe scripts/verify_reproduction.py
.\.venv\Scripts\python.exe scripts/run_agent_demo.py --smoke
```

**Local LLM (requires Ollama + `qwen2.5:7b-instruct` or `bist-qwen`):**
```powershell
.\.venv\Scripts\python.exe scripts/local_agent.py --smoke
.\.venv\Scripts\python.exe scripts/run_harness_experiments.py --backend ollama --model bist-qwen
.\.venv\Scripts\python.exe training/eval/run_baseline.py --model bist-qwen
```

**Scenario reports:**
```powershell
.\.venv\Scripts\python.exe scripts/build_scenarios.py
```

**Refresh market data (requires network):**
```powershell
.\.venv\Scripts\python.exe -m bist_analytics.cli fetch --refresh
```

## Architecture

### Data Flow

```
config/tms29.yaml → CLI → build_analysis() → evaluate() → create_report()
                              ↓                    ↓              ↓
                     Cached Yahoo prices    Backtest engine   HTML/PDF/MD
                     Fintables CSV          3 strategies      Charts
                     Technical indicators   vs BIST100
                     Support/resistance
                     Scoring (T+F)
```

### Source Layout (`src/bist_analytics/`)

- **`pipeline.py`** — Orchestrates the full fetch→parse→analyze→backtest→report flow for the primary ticker, additively loads the 10-ticker universe when `config.universe` is populated.
- **`cli.py`** — Command-line entry point with subcommands: `run`, `fetch` (iterates universe tickers), `import-tms29`, `import-originals`, `import-fintables`, `template`.
- **`config.py`** — Pydantic models. New fields: `universe: list[str]`, `sector_map: dict[str, str]`. Ticker shape validated by regex.
- **`schemas.py`** — `FinancialObservation`; `EDUCATIONAL_LABELS` (8-tuple), `GATE_STATES` (5-tuple), `EvidenceItem`, `EvidenceBundle`, `AgentAnswer`.
- **`analysis/`** — `indicators.py` (SMA/EMA/RSI/MACD/volume + Bollinger, ATR, KAMA, Supertrend), `fundamentals.py`, `levels.py`, `scoring.py`, `reversals.py` (detect_reversal_events), `grouping.py` (sector peer rankings + weekday tests), `gate.py` (5-state quality gate), `evidence.py` (EvidenceBundle builder).
- **`backtest/`** — `engine.py` (order execution, persistent position state, next-open fills), `metrics.py` (Sharpe, drawdown, win rate, exposure, costs).
- **`strategy/rules.py`** — BUY/SELL/HOLD signal generation from scores and indicator state; `INTERNAL_TO_EDUCATIONAL` maps to the 8 labels.
- **`scenarios/`** — Four scenario builders: `sector_laggard`, `weekday_patterns`, `reversal_events`, `fundamental_reaction`. `scripts/build_scenarios.py` runs them.
- **`data/`** — `market.py` (Yahoo wrapper; shape-validated — no hardcoded whitelist), `tms29.py`, `originals.py`, `context.py` (per-ticker KAP paths), `macro.py` (TCMB EVDS + TÜİK CPI release-date aligned).
- **`mcp/server.py`** — 19 read-only MCP tools over stdio: the original 9 plus `get_index_history`, `detect_reversal_events`, `rank_sector_relative_strength`, `test_weekday_pattern`, `calculate_fundamental_change`, `get_macro_context`, `get_news_events`, `get_speech_features`, `check_data_quality`, `build_evidence_bundle`.
- **`harness/evaluation.py`** — Multi-scenario deterministic scoring + §30 metric checks.
- **`reporting.py`** — HTML / Markdown / PDF generation.
- **`io.py`** — JSON serialization and hash verification.

### LLM stack (`scripts/local_agent.py` + `training/`)

- `scripts/local_agent.py` — Python client against Ollama's OpenAI-compatible endpoint (`localhost:11434/v1`); launches the MCP server as a child process and shuttles tool calls.
- `scripts/run_harness_experiments.py --backend ollama` — the 5-stage A–E experiment, local path (submission).
- `training/dataset/build.py` — generates ~400 verified examples by replaying live MCP tool calls, 80/20 stratified split.
- `training/train_lora.py` — QLoRA 4-bit (rank 16, alpha 32, 3 epochs, cosine LR 2e-4) via HuggingFace peft + trl; designed for Colab T4.
- `training/export_gguf.sh` — adapter → GGUF via llama.cpp, loaded through `training/Modelfile.finetuned`.
- `training/eval/run_baseline.py` + `compare.py` — 20-question §30 eval and base-vs-fine-tuned comparison.

### Key Design Constraints

- **Offline reproducibility**: All analysis runs from cached data (`data/raw/`, `data/processed/`). No network calls during backtest or reporting.
- **Vintage policy**: `import-tms29` validates 7 PDF vintages and 56 statement identities before writing observations. No importer overwrites another dataset's output.
- **Strategy parameters are frozen** (see `docs/DECISIONS.md`): stop-loss 8%, max hold 40 sessions, combined score threshold 0.70, fundamentals freshness limit 230 days. These were not selected on 2025 returns.
- **Execution model**: Close-of-day signal → next session open fill. Commission 10 bps + slippage 5 bps. Cash earns zero. Returns are nominal TRY.
- **EMA seeding**: EMAs are SMA-seeded to avoid NaN on startup.

### MCP Tools (19 read-only)

Exposed by `bist_analytics.mcp.server`: `project_status`, `get_context_events`, `get_stock_history`, `calculate_indicators`, `find_support_resistance`, `get_fundamental_metrics`, `calculate_scores`, `run_backtest`, `generate_signal`, `generate_report`, `get_index_history`, `detect_reversal_events`, `rank_sector_relative_strength`, `test_weekday_pattern`, `calculate_fundamental_change`, `get_macro_context`, `get_news_events`, `get_speech_features`, `check_data_quality`, `build_evidence_bundle`.

### 8-label action space (frozen in `schemas.py`)

`HOLD · WATCH · INVESTIGATE · POTENTIAL_CATCH_UP_CANDIDATE · TECHNICAL_REVERSAL_CANDIDATE · FUNDAMENTAL_IMPROVEMENT_CANDIDATE · REJECT_SIGNAL · ANALYSIS_UNSAFE`. The gate hard-blocks FUTURE_STATEMENT, LOOK_AHEAD, PRICE_HISTORY_BROKEN, PERIOD_MISMATCH, BACKTEST_LEAKAGE, STALE_FUNDAMENTALS (>2× max age).

### Config Files

- `config/tms29.yaml` — Primary THYAO study (2025–Sep 2026, 238 TMS29 observations)
- `config/project.yaml` — Annual baseline (FY2020–FY2024, verified-only)
- `config/retrospective.yaml` — Earlier USD-basis study
- `config/universe10.yaml` — 10-ticker, 5-sector universe (airlines, banking, steel, retail, telecom)
- `config/bist100_universe.yaml` — 10-ticker manifest with liquidity/sector metadata

### Key Reference Docs

- `docs/DECISIONS.md` — All frozen thresholds and methodological limitations
- `docs/DATA_DICTIONARY.md` — Financial metric definitions and TTM calculation logic
- `docs/WALKTHROUGH.md` — Code tour with a real trade example
- `docs/INSTRUCTOR_QA_UPGRADE.md` — Post-TMS 29 implementation details
- `docs/ACCEPTANCE.md` — Requirement mapping and verification evidence
- `docs/LOCAL_MODEL.md`, `docs/LOCAL_SETUP.md`, `docs/MODEL_CARD.md`, `docs/HARNESS_RERUN.md`, `training/COLAB_RUNBOOK.md` — LLM stack and Phase F/G/H operator guides
