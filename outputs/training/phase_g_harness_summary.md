# Phase G — 5-stage A→E harness re-run with `bist-qwen`

- Backend: Ollama (localhost:11434), zero cloud traffic
- Model: `bist-qwen` (Qwen 2.5 3B + LoRA, merged GGUF)
- Stages: `raw_llm` → `llm_tools` → `stateful_harness` → `evidence_quality_gate` → `memory_human_review`
- Full artefacts: `outputs/harness/{stage}.{json,jsonl,score.json}`, `comparison.finetuned.json`, `state.finetuned.json`

## Per-stage §30 metric table

| Axis | raw_llm | llm_tools | stateful | evidence_gate | memory_review | Monotonic? |
|---|---|---|---|---|---|---|
| `evidence_coverage` (↑) | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | **yes** |
| `workflow_completion` (↑) | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | **yes** |
| `structured_reproducibility` (↑) | False | False | **True** | False | **True** | partial |
| `numeric_exactness` (↑) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | no (flat at 0) |
| `constraint_compliance` (↑) | True | False | False | False | False | **regressed** |
| `temporal_validity` (↑) | False | False | False | False | False | no (flat at 0) |

## Reading

- **evidence_coverage, workflow_completion**: the architectural payoff lands as expected.
  Giving the fine-tune MCP tools (A → B transition) immediately drives both to 1.0 and
  they stay there through every later stage. This is the headline Phase G finding — the
  tool-chain integration works and the fine-tune follows the trained patterns.
- **structured_reproducibility**: toggles on at `stateful_harness` (immutable run state
  disambiguates dates) and again at `memory_human_review` (prior memory reinforces the
  schema). It dips at `evidence_quality_gate` because the gate language ("will be
  rejected unless …") leads the model to add a narrative preamble that breaks pure-JSON
  extraction. A schema-strict decoding step (grammar-constrained Ollama) would fix this
  and is in the de-scope ladder for a later iteration.
- **numeric_exactness**: flat at 0 across all tool stages. The fine-tune reliably CALLS
  the required tools but a 3B model struggles to pick the exact scalar out of a large
  tool-result JSON and surface it in the harness's rich numeric schema (revenue,
  net profit, net debt, four returns). This matches the tool-loop pathology documented
  in `outputs/training/base_vs_finetuned.md` and `docs/MODEL_CARD.md`: trained to use
  the tools, under-trained on schema-slot population.
- **constraint_compliance**: regresses from True (raw_llm, which emits nulls) to False
  once tools are enabled, because the fine-tune's narrative field includes text that
  pattern-matches banned advisory phrasing. This is a surface-level fine-tune artifact,
  not a safety failure (the model still refuses to recommend trades) — fixable by
  tightening the dataset's narrative field to a factual, caveat-only register.
- **temporal_validity**: flat at False. The model emits dates in free-form text inside
  the narrative and misses the `as_of`/`financial_period` slots in the strict schema,
  which the evaluator fails.

## Phase G exit decision

Per the plan's Phase G exit criterion — "comparison.json with monotonic improvement
across the 5 stages on the §30 metrics (or honest documentation of any non-monotonic
axis)" — this report documents:

- 2 / 6 axes are strictly monotonic (`evidence_coverage`, `workflow_completion`)
- 1 / 6 is partial-monotonic (`structured_reproducibility`)
- 3 / 6 are flat-at-zero or regressed, each with root cause documented above

The architectural comparison itself is sound: giving the fine-tune MCP tools (A→B) is the
single largest quality lift observed, which is exactly the point of the 5-stage
experiment. Numeric-exactness and schema-slot regressions are scoped as model-side
limitations and are the top candidates for any subsequent dataset / training iteration.

## Reproducing

```powershell
ollama serve
ollama list | Select-String bist-qwen   # confirm the tag is present
./.venv/Scripts/python.exe scripts/run_harness_experiments.py --backend ollama --model bist-qwen
```

All five stages run in ~8-12 min on a workstation with 8 GB VRAM. Outputs land under
`outputs/harness/`. No network calls are made after the Ollama tag is pulled once.
