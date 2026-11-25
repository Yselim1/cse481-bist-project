# Phase G — 5-stage A→E harness, base vs fine-tuned (v3)

- Backend: Ollama (localhost:11434), zero cloud traffic; data config `config/tms29.yaml`, no harness-side RAG
- Fine-tuned: `bist-qwen` (Qwen 2.5 3B + LoRA v3, merged Q4_K_M GGUF, 16k context)
- Base: `bist-qwen-base` (`qwen2.5:3b-instruct` with the same 16k context and sampling; `training/Modelfile.base`)
- Stages: `raw_llm` → `llm_tools` → `stateful_harness` → `evidence_quality_gate` → `memory_human_review`
- One fixed THYAO question; only the architecture changes between stages, so this is an architecture comparison
- Artefacts: `outputs/harness/comparison.{finetuned,base}.json`, `state.{finetuned,base}.json`;
  per-stage `{stage}.{json,jsonl,score.json}` are the fine-tuned run (it ran last)
- Run on 2026-11-25 with the submitted adapter (SHA-256 `ad3716e9…`)

## Per-stage table — fine-tuned `bist-qwen`

| Axis | raw_llm | llm_tools | stateful | evidence_gate | memory_review | Shape |
|---|---|---|---|---|---|---|
| `evidence_coverage` (↑) | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | **monotonic** |
| `workflow_completion` (↑) | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | **monotonic** |
| `structured_reproducibility` (↑) | False | True | True | True | False | 3 / 5 |
| `constraint_compliance` (↑) | True | True | True | True | True | **5 / 5** |
| `temporal_validity` (↑) | False | False | False | False | False | flat |
| `numeric_exactness` (↑) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | flat |
| strict field checks passed (of 11) | 1 | 2 | 2 | 2 | 2 | |

## Per-stage table — base `bist-qwen-base`

| Axis | raw_llm | llm_tools | stateful | evidence_gate | memory_review | Shape |
|---|---|---|---|---|---|---|
| `evidence_coverage` (↑) | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | monotonic |
| `workflow_completion` (↑) | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | monotonic |
| `structured_reproducibility` (↑) | True | True | True | True | True | 5 / 5 |
| `constraint_compliance` (↑) | True | False | True | False | False | 2 / 5 |
| `temporal_validity` (↑) | False | False | False | False | False | flat |
| `numeric_exactness` (↑) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | flat |
| strict field checks passed (of 11) | 1 | 0 | 2 | 0 | 0 | |

## Reading

- **Tools are the step change.** For both models, adding MCP tools (A → B) takes
  evidence_coverage and workflow_completion from 0 to 1.0, and they stay there in every later stage.
- **The fine-tune keeps the rules.** constraint_compliance (educational caveat present, no
  investment recommendation) holds in all five stages for `bist-qwen`, versus two of five for the
  base. It also passes both the as_of and context_event checks in all four tool stages
  (B–E); the base passes both only at `stateful_harness`.
- **The base produces cleaner JSON.** structured_reproducibility is 5/5 for the base and 3/5 for
  the fine-tune: the fine-tune was trained to answer in its `<final_answer>` format, so on the
  long harness prompt it sometimes wraps or prefixes the JSON object.
- **numeric_exactness stays 0 for both.** This stage asks for eleven strict fields (revenue, net
  profit, net debt in million TRY, four strategy returns, signal, context event) assembled from
  several large tool outputs in one JSON object. Neither 3B model fills them exactly; the
  presentation path avoids this by having tools return the needed comparisons directly.
- **temporal_validity stays False**: dates go into the narrative instead of the `as_of` /
  `financial_period` schema slots.

## Earlier run (v1 adapter, for reference)

The v1 fine-tune (dataset v1, dedup guard) had constraint_compliance in 3 of 5 stages and
structured_reproducibility only at `llm_tools`; evidence_coverage and workflow_completion had the
same 0 → 1.0 shape. That run used the default data config and is superseded by this one.

## Reproducing

```powershell
.\.venv\Scripts\python.exe scripts\run_harness_experiments.py --backend ollama --model bist-qwen-base
Copy-Item outputs\harness\comparison.json outputs\harness\comparison.base.json
Copy-Item outputs\harness\state.json outputs\harness\state.base.json
.\.venv\Scripts\python.exe scripts\run_harness_experiments.py --backend ollama --model bist-qwen
Copy-Item outputs\harness\comparison.json outputs\harness\comparison.finetuned.json
Copy-Item outputs\harness\state.json outputs\harness\state.finetuned.json
```
