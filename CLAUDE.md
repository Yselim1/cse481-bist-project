# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CSE481 term project. The original THYAO.IS single-ticker research pipeline is still the deepest-worked example, but the repo has grown into a 10-ticker, multi-sector BIST research harness driven by a **locally hosted fine-tuned LLM** (Qwen 2.5 3B + LoRA via Ollama). It imports Fintables financials, caches Yahoo prices, computes technical/fundamental scores, backtests explicit rules, and exposes 21 MCP tools (including a BM25 knowledge-base search for RAG) to the agent.

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
.\.venv\Scripts\python.exe scripts/local_agent.py --smoke --model bist-qwen   # without --model the default is qwen2.5:7b-instruct
.\.venv\Scripts\python.exe scripts/run_harness_experiments.py --backend ollama --model bist-qwen
.\.venv\Scripts\python.exe training/eval/run_baseline.py --model bist-qwen
```

**Presentation (5 scenario traces, live question, submission manifest)** — see `docs/PRESENTATION.md`:
```powershell
.\.venv\Scripts\python.exe scripts/run_presentation_scenarios.py   # outputs/presentation/traces/S1..S5
.\.venv\Scripts\python.exe scripts/ask.py "<question>"              # live question, same code path
.\.venv\Scripts\python.exe scripts/build_rag_kb.py                  # rag/knowledge_base.json
.\.venv\Scripts\python.exe scripts/build_submission.py; .\.venv\Scripts\python.exe scripts/verify_submission.py
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
- **`data/`** — `market.py` (Yahoo wrapper; shape-validated — no hardcoded whitelist), `tms29.py`, `originals.py`, `context.py` (per-ticker KAP paths), `macro.py` (TCMB EVDS + TÜİK CPI release-date aligned; no series are cached under `data/raw/macro/`, so `get_macro_context` returns nulls).
- **`mcp/server.py`** — 21 read-only MCP tools over stdio: the original 10 plus `search_knowledge_base` (RAG) and `get_index_history`, `detect_reversal_events`, `rank_sector_relative_strength`, `test_weekday_pattern`, `calculate_fundamental_change`, `get_macro_context`, `get_news_events`, `get_speech_features`, `check_data_quality`, `build_evidence_bundle`.
- **`harness/evaluation.py`** — Multi-scenario deterministic scoring + §30 metric checks (grader-only; never imported on the agent path).
- **`harness/grounding.py`** — post-hoc audit: every figure in a final answer must match a tool output (stored in each trace; never rewrites the answer).
- **`strategy/label_rules.py`** — single source of the educational-label thresholds; tools return them as `label_rule`, and the dataset builder imports them.
- **`rag.py`** — offline BM25 over `rag/knowledge_base.json` with a point-in-time (`published_at <= as_of`) filter.
- **`reporting.py`** — HTML / Markdown / PDF generation.
- **`io.py`** — JSON serialization and hash verification.

### LLM stack (`scripts/local_agent.py` + `training/`)

- `scripts/local_agent.py` — Python client against Ollama's OpenAI-compatible endpoint (`localhost:11434/v1`); launches the MCP server (with `BIST_CONFIG`, default `config/universe_live.yaml`) as a child process, does harness-side RAG, sends seed + temperature, and writes the full execution trace (`bist-execution-trace/1`).
- `scripts/run_harness_experiments.py --backend ollama` — the 5-stage A–E experiment, local path (submission).
- `training/dataset/build.py` — dataset v3: 400 examples by replaying live MCP tool calls (config/universe_live.yaml; the 5 presentation settings held out; answers copy the tools' precomputed summary / label_by_rule blocks), ~half natural-language questions with the inference system prompt + RAG context, every answer figure grounding-checked; 80/20 stratified split.
- `training/train_unsloth.py` — QLoRA 4-bit via Unsloth (rank 16, alpha 32, 3 epochs, cosine LR 2e-4, effective batch 16, max_len 4096, seed 17) on Colab T4; saves `adapter_model.safetensors`, writes `training/config/hyperparams.json`, exports the merged GGUF from the same run. (`train_lora.py` is the superseded peft/trl recipe.)
- `training/export_gguf.sh` — adapter → GGUF via llama.cpp, loaded through `training/Modelfile.finetuned`.
- `training/eval/run_baseline.py` + `compare.py` — 20-question §30 eval and base-vs-fine-tuned comparison.

### Key Design Constraints

- **Offline reproducibility**: All analysis runs from cached data (`data/raw/`, `data/processed/`). No network calls during backtest or reporting.
- **Vintage policy**: `import-tms29` validates 7 PDF vintages and 56 statement identities before writing observations. No importer overwrites another dataset's output.
- **Strategy parameters are frozen** (see `docs/DECISIONS.md`): stop-loss 8%, max hold 40 sessions, combined score threshold 0.70, fundamentals freshness limit 230 days. These were not selected on 2025 returns.
- **Execution model**: Close-of-day signal → next session open fill. Commission 10 bps + slippage 5 bps. Cash earns zero. Returns are nominal TRY.
- **EMA seeding**: EMAs are SMA-seeded to avoid NaN on startup.

### MCP Tools (21 read-only)

Exposed by `bist_analytics.mcp.server`: `project_status`, `get_context_events`, `get_stock_history`, `calculate_indicators`, `find_support_resistance`, `get_fundamental_metrics`, `calculate_scores`, `run_backtest`, `generate_signal`, `generate_report`, `get_index_history`, `detect_reversal_events`, `rank_sector_relative_strength`, `test_weekday_pattern`, `calculate_fundamental_change`, `get_macro_context`, `get_news_events`, `get_speech_features`, `check_data_quality`, `build_evidence_bundle`, `search_knowledge_base`.

### 8-label action space (frozen in `schemas.py`)

`HOLD · WATCH · INVESTIGATE · POTENTIAL_CATCH_UP_CANDIDATE · TECHNICAL_REVERSAL_CANDIDATE · FUNDAMENTAL_IMPROVEMENT_CANDIDATE · REJECT_SIGNAL · ANALYSIS_UNSAFE`. The gate hard-blocks FUTURE_STATEMENT, LOOK_AHEAD, PRICE_HISTORY_BROKEN, PERIOD_MISMATCH, BACKTEST_LEAKAGE, STALE_FUNDAMENTALS (>2× max age).

### Config Files

- `config/tms29.yaml` — Primary THYAO study (2025–Sep 2026, 238 TMS29 observations)
- `config/project.yaml` — Annual baseline (FY2020–FY2024, verified-only)
- `config/retrospective.yaml` — Earlier USD-basis study
- `config/universe10.yaml` — 10-ticker, 5-sector universe (airlines, banking, steel, retail, telecom); scenario reports + fine-tuning dataset
- `config/universe_live.yaml` — universe10 + 8 more tickers (automotive, holding, energy, 2 more banks); the agent's default for the scenarios and the live question
- `config/bist100_universe.yaml` — 10-ticker manifest with liquidity/sector metadata

### Key Reference Docs

- `docs/PRESENTATION.md` — presentation procedure, trace schema, integrity measures, submission.json
- `docs/DECISIONS.md` — All frozen thresholds and methodological limitations
- `docs/DATA_DICTIONARY.md` — Financial metric definitions and TTM calculation logic
- `docs/WALKTHROUGH.md` — Code tour with a real trade example
- `docs/INSTRUCTOR_QA_UPGRADE.md` — Post-TMS 29 implementation details
- `docs/ACCEPTANCE.md` — Requirement mapping and verification evidence
- `docs/LOCAL_MODEL.md`, `docs/LOCAL_SETUP.md`, `docs/MODEL_CARD.md`, `docs/HARNESS_RERUN.md`, `training/COLAB_RUNBOOK.md` — LLM stack and Phase F/G/H operator guides
