# Presentation procedure and submission

This covers the course's presentation rules: five pre-run scenarios with full execution
traces, one live unseen question, the academic-integrity rules, and a single
`submission.json` manifest.

## 1. Pre-prepared question-answer examples (five scenarios)

The questions are in `presentation/scenarios.json`. They are written as a user would ask
them and never name a tool:

| id | scenario | ticker / range |
|---|---|---|
| S1 | sector laggard / catch-up | banking sector, 63 sessions to 2025-12-31 |
| S2 | day-of-week pattern | EREGL.IS, 2025-01-01 → 2025-12-31 |
| S3 | technical reversal events | TCELL.IS, 120 sessions to 2025-12-31 (reworded once; see `wording_note`) |
| S4 | fundamental change + price reaction | THYAO.IS as of 2025-12-31 |
| S5 | unsafe analysis (future horizon) | BIMAS.IS as of 2027-03-31 |

```powershell
# GPU (4 GB laptop RTX 3050 or larger): flash attention + 8-bit KV cache keep the whole
# 16k-context model on the GPU. Without these it still runs, partly on the CPU.
$env:OLLAMA_FLASH_ATTENTION = "1"; $env:OLLAMA_KV_CACHE_TYPE = "q8_0"
ollama serve                                                   # if not already running
.\.venv\Scripts\python.exe scripts\run_presentation_scenarios.py
```

Results of the submitted run (`bist-qwen`, temperature 0, seed 17; one tool call each):

| id | tool the model chose | label and key figures | grounded |
|---|---|---|---|
| S1 | `rank_sector_relative_strength` | HOLD: ISCTR.IS relative_vs_sector −0.0422 | all |
| S2 | `test_weekday_pattern` | WATCH: Mon highest 0.002940, Wed lowest −0.004426, smallest p 0.238 | all |
| S3 | `detect_reversal_events` | TECHNICAL_REVERSAL_CANDIDATE: 35 events; supertrend_flip_up mean_forward_5d 0.0207 | all |
| S4 | `calculate_fundamental_change` | WATCH: revenue_qoq 0.0741, net_profit_qoq 0.0446, published 2025-11-10, 5-session reaction −0.0708 | all |
| S5 | `calculate_fundamental_change` | ANALYSIS_UNSAFE: DATE_OUT_OF_SNAPSHOT | no figures |

**How the agent talks to the model on this path.** The fine-tuning conversations contain
`<tool_call>{json}</tool_call>` text and no tool schemas. So the presentation path
(`run_presentation_scenarios.py`, `ask.py`) sends no schemas and parses that text
(`tool_schemas=False`, recorded as `harness.tool_protocol` in each trace). It trims tool
results to 4,500 characters, the cap the training data used, and caps each model turn at
1,536 tokens. When Ollama added its 21-tool schema block, the fine-tune chained unrelated tools.

Outputs go to `outputs/presentation/`: `traces/S1..S5.trace.json`, `index.json`, and
`traces.html`, a readable view to open in class.

Each trace (`schema_version: bist-execution-trace/1`) records:

* **model**: Ollama name, digest, family, parameter size, quantization, Ollama version,
  Modelfile parameters, base model and adapter SHA-256 (from `submission.json`)
* **sampling**: temperature 0.0, seed 17, max_tokens 1536, top_p, num_ctx; the seed is sent to Ollama on every call
* **harness**: config file, tool protocol, tool-result cap, max turns, git commit
* **system_prompt**, **user_prompt**, and **user_message_sent** (the question plus the retrieved knowledge-base context)
* **retrieval**: the `search_knowledge_base` call the harness made, its arguments and its hits
* **steps[]**: every model turn and tool call in order. Each has `started_at`/`finished_at`
  timestamps and a duration. Tool calls also record `arguments`, a `date_range` pulled from
  them, the full `result` with its SHA-256, and whether the model saw a truncated copy.
* **final_answer**: the model's text, never edited
* **grounding_audit**: every figure in the answer and the tool value it matches (or not)

## 2. Live question

```powershell
.\.venv\Scripts\python.exe scripts\ask.py "<the instructor's question>"
```

It uses the same code path, system prompt, seed, temperature, config
(`config/universe_live.yaml`) and RAG settings as the five scenarios. Tool calls print as
they happen. The trace is saved to `outputs/presentation/live/<timestamp>.trace.json`, and
`scripts/run_presentation_scenarios.py --render-only` can be adapted to view it.

Coverage for unseen questions:
* **prices** for 18 tickers in 8 sectors: airlines, automotive, banking (4), energy,
  holding, retail, steel, telecom. Cached daily data runs from 2021-01-04 to 2026-10-30.
* **fundamentals** for THYAO only. For any other ticker the fundamental tools return
  `available: false`, and the model was trained to say so and label INVESTIGATE.
* a ticker that isn't cached, or a date after today: `check_data_quality` returns
  HARD_BLOCK (PRICE_HISTORY_BROKEN / FUTURE_STATEMENT), so the label is ANALYSIS_UNSAFE.

Expect about 20–30 s per question with the model fully on a 4 GB GPU (settings above), or
35–45 s when part of it runs on the CPU.

Re-running gives the same tool calls, labels and figures. On the GPU the wording can differ
slightly between runs (for example "1 session after publication" vs "1 session from
publication"): flash attention does not guarantee bit-identical floating-point sums, so seed 17
at temperature 0 is reproducible in substance, not byte for byte. The submitted traces are the
record; their `harness.git` field names the clean commit they ran on.

Known weak spot from a dry run: on a sector question the conclusion was right, but the
explanation quoted another sector's figures. Those figures are in the tool output, so the
grounding audit passes them. Read sector answers before presenting them.

## 3. Academic integrity: how the code meets each rule

* **No predetermined answers.** The agent path (`scripts/local_agent.py`, `scripts/ask.py`,
  `scripts/run_presentation_scenarios.py`, `src/bist_analytics/mcp/server.py`) has no
  question-to-answer mapping. `presentation/scenarios.json` holds questions plus a
  reviewer-only `expected_behaviour` note, which the runner never sends to the model.
* **Only the submitted model's output.** The final answer is stored exactly as Ollama
  returned it. The model digest in each trace must match the served `bist-qwen` digest in
  `submission.json`, and `scripts/verify_submission.py` checks this.
* **No figures absent from tool outputs.**
  * `src/bist_analytics/harness/grounding.py` audits every figure in the answer against
    the tool results in the same trace. It allows rounding to the displayed precision and
    fraction ↔ percent conversion. One-significant-digit figures must match exactly.
  * Labelling thresholds (±0.05 sector, 0.005 reversal, ±0.10 fundamental, p < 0.10 / 0.01
    weekday) live in `src/bist_analytics/strategy/label_rules.py` and come back inside
    the tool outputs (`label_rule`). So when the model cites a threshold, it is citing
    tool evidence.
  * The fine-tuning data was built under the same rule. `training/dataset/build.py`
    rejects any example whose answer contains a figure not found in its tool messages
    (see `training/dataset/audit.json`).
* `src/bist_analytics/harness/evaluation.py` holds expected values for **grading**
  harness experiments only. No file on the agent path imports it, and the verifier checks this too.

## 4. Submission manifest

```powershell
.\.venv\Scripts\python.exe scripts\build_submission.py    # writes submission.json
.\.venv\Scripts\python.exe scripts\verify_submission.py   # recomputes and checks everything
```

`submission.json` lists every attachment with its role, size and SHA-256:

| course item | manifest section | files |
|---|---|---|
| Python source: tools, agent/harness, run scripts | `code` | `src/bist_analytics/**`, `scripts/local_agent.py`, `scripts/ask.py`, `scripts/run_presentation_scenarios.py`, … |
| Fine-tuning file: data, config, hyperparameters | `fine_tuning` | `training/dataset/{train,eval}.jsonl`, `training/config/hyperparams.json`, `training/dataset/audit.json` |
| Model weights: LoRA adapter only, plus base model info | `adapter`, `base_model` | `training/adapter/adapter_model.safetensors` (+ `adapter_config.json`); Qwen/Qwen2.5-3B-Instruct with its HF revision |
| RAG file: KB documents + source metadata | `rag` | `rag/knowledge_base.json` (built by `scripts/build_rag_kb.py`) |
| Execution traces for the five scenarios | `execution_traces` | `outputs/presentation/traces/S1..S5.trace.json` |

The merged GGUF that Ollama serves (`training/bist_lora.gguf`, about 1.9 GB) is exported
from the same training run as the adapter. It is listed under `served_model` with its
hash, but it is not an attachment.
