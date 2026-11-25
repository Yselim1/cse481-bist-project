# Phase G — Re-run the 5-stage A–E harness with the local fine-tuned model

The 5-stage experiment (`raw_llm` → `llm_tools` → `stateful_harness` →
`evidence_quality_gate` → `memory_human_review`) is the rubric-anchored comparison. It
must be re-run after Phase F so the submission zip ships the local-model traces, not the
Codex/dev-cloud traces.

## Prerequisites

1. `ollama serve` is running (port 11434).
2. `bist-qwen` (fine-tuned) and `bist-qwen-base` (base) are present
   (`ollama list`).
3. The repo's venv is bootstrapped (`docs/LOCAL_SETUP.md` §1).

The Ollama path always loads `config/tms29.yaml` (the question is about the TMS 29 THYAO study)
and does no harness-side RAG, so stages stay comparable across runs. Results of the
2026-11-25 run: `outputs/training/phase_g_harness_summary.md`.

## Baseline run (Qwen 2.5 3B base, same context as the fine-tune)

```powershell
ollama create bist-qwen-base -f training/Modelfile.base
.\.venv\Scripts\python.exe scripts\run_harness_experiments.py `
    --backend ollama --model bist-qwen-base
# Preserve for the comparison table:
Copy-Item outputs\harness\comparison.json outputs\harness\comparison.base.json
Copy-Item outputs\harness\state.json outputs\harness\state.base.json
```

## Fine-tuned run

```powershell
.\.venv\Scripts\python.exe scripts\run_harness_experiments.py `
    --backend ollama --model bist-qwen
Copy-Item outputs\harness\comparison.json outputs\harness\comparison.finetuned.json
Copy-Item outputs\harness\state.json     outputs\harness\state.finetuned.json
```

Expected wall clock: about 5 min per run with the 3B model fully on a 4 GB GPU (see docs/PRESENTATION.md for the Ollama GPU settings).

## What to inspect

- `outputs/harness/*.score.json` — per-stage §30 metrics
- `outputs/harness/comparison.json` — must show monotonic (or honestly-documented
  non-monotonic) improvement across the 5 stages
- `outputs/harness/human_review.json` — flagged for M6.9 instructor review; fill in
  `reviewer`, `reviewed_at`, `decision`, `comments`

## Expected failure modes and what to do

- **`raw_llm` stage emits bogus numbers**: expected. It has no tools; that is the baseline.
- **`llm_tools` makes invalid tool calls**: common on the base model. The fine-tune should
  reduce it; if not, see `docs/MODEL_CARD.md` limitations.
- **Gate escalates to ANALYSIS_UNSAFE on `evidence_quality_gate` stage**: expected on
  future-dated or broken-cache inputs; the harness logs the block reason.
- **Timeout on a stage**: raise `tool_timeout_sec` in `scripts/run_harness_experiments.py`
  if the local model is slow; default is 120 s per tool and 600 s per stage overall.

## Submission package wiring

`scripts/package_project.py` is expected to include:

- `outputs/harness/{raw_llm,llm_tools,stateful_harness,evidence_quality_gate,memory_human_review}.json`
- `outputs/harness/*.score.json`
- `outputs/harness/comparison.{base,finetuned}.json`
- `training/bist_lora.gguf` (adapter)
- `training/Modelfile.finetuned`

Verify by unzipping the submission on a fresh machine and re-running
`run_harness_experiments.py --backend ollama --model bist-qwen` with no Internet access.
