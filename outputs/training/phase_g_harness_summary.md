# Phase G — 5-stage A→E harness re-run with `bist-qwen`

- Backend: Ollama (localhost:11434), zero cloud traffic
- Model: `bist-qwen` (Qwen 2.5 3B + LoRA, merged GGUF)
- Stages: `raw_llm` → `llm_tools` → `stateful_harness` → `evidence_quality_gate` → `memory_human_review`
- Fix applied: dedup guard + force-answer-after-7-turns in `scripts/local_agent.py`
- Full artefacts: `outputs/harness/{stage}.{json,jsonl,score.json}`, `comparison.finetuned.json`, `state.finetuned.json`

## Per-stage §30 metric table (post-dedup fix)

| Axis | raw_llm | llm_tools | stateful | evidence_gate | memory_review | Monotonic? |
|---|---|---|---|---|---|---|
| `evidence_coverage` (↑) | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | **yes** |
| `workflow_completion` (↑) | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | **yes** |
| `structured_reproducibility` (↑) | False | **True** | False | False | False | partial (peaks at B) |
| `constraint_compliance` (↑) | True | False | **True** | **True** | False | partial (3/5 pass) |
| `temporal_validity` (↑) | False | False | False | False | False | flat |
| `numeric_exactness` (↑) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | flat |

## Improvements vs previous run (pre-dedup fix)

| Stage | Axis | Before | After | Change |
|---|---|---|---|---|
| llm_tools | structured_reproducibility | False | **True** | improved |
| stateful_harness | as_of check | False | **True** | improved |
| stateful_harness | context_event check | False | **True** | improved |
| stateful_harness | constraint_compliance | False | **True** | improved |
| evidence_quality_gate | constraint_compliance | False | **True** | improved |
| memory_human_review | signal_action check | False | **True** | improved |

## Reading

- **evidence_coverage, workflow_completion**: both strictly monotonic. Giving the fine-tune MCP
  tools (A → B transition) immediately drives both to 1.0 and they stay there through every
  later stage. This is the headline Phase G finding.
- **structured_reproducibility**: peaks at `llm_tools` with the dedup fix — without looping the
  model produces cleaner single-pass JSON output. Drops in later stages because the longer
  prompts (state, gate language, memory) push the model into adding preamble text that breaks
  pure-JSON extraction.
- **constraint_compliance**: now passes in 3 of 5 stages (raw_llm, stateful_harness,
  evidence_quality_gate). The dedup guard stops the model from cycling through tools and landing
  in a confused state; with clean exits it correctly includes `educational_caveat` and omits
  `investment_recommendation`.
- **numeric_exactness**: flat at 0 across all stages. The 3B model reliably calls the right
  tools but does not populate the strict numeric schema slots (revenue, net profit, net debt,
  four returns). Root cause: trained to call tools and cite them, under-trained on extracting
  specific scalars from large tool-result JSON into a structured output schema.
- **temporal_validity**: flat at False. The model embeds dates in free-form narrative rather
  than the `as_of`/`financial_period` schema slots.

## Phase G exit decision

2 / 6 axes strictly monotonic, 1 / 6 partial-monotonic, 3 / 6 flat or partial — consistent
with an architecture demonstration. The dedup fix improved 6 individual checks across the 5
stages. Per the plan's Phase G exit criterion ("monotonic improvement on the §30 metrics *or*
honest documentation of any non-monotonic axis"), this run documents all non-monotonic axes
with root causes.

## Reproducing

```powershell
ollama serve
ollama list | Select-String bist-qwen
./.venv/Scripts/python.exe scripts/run_harness_experiments.py --backend ollama --model bist-qwen
```

All five stages run in ~25 min on a workstation with 8 GB VRAM. No network calls after the
Ollama tag is pulled once.
