# Local LLM stack (Ollama + Qwen 2.5 + LoRA adapter)

The submission runs fully offline. Inference is served by a locally hosted small LLM
through Ollama's OpenAI-compatible endpoint; no cloud API is contacted during the
graded demo.

## Hardware / prerequisites

| Scenario | VRAM | Notes |
|---|---|---|
| Qwen 2.5 7B Instruct (default) | 6–8 GB (Q4_K_M) | preferred on 8GB+ discrete GPU or Apple Silicon |
| Qwen 2.5 3B Instruct (fallback) | 3–4 GB | integrated graphics or lightweight laptops |
| CPU-only | 0 GB | 7B is 5–10 tok/s; 3B is 15–25 tok/s on a 12-core desktop |

Ollama bundles llama.cpp and ships Windows / macOS / Linux installers at
https://ollama.com/download. Install once; it registers as a service.

## Base model install

```powershell
# Confirm the daemon is reachable (uses port 11434)
ollama serve     # usually auto-starts as a service on Windows

# Pull the base model (≈4.3 GB)
ollama pull qwen2.5:7b-instruct

# Smaller fallback if VRAM is tight
ollama pull qwen2.5:3b-instruct
```

Validate with a raw call:

```powershell
curl http://localhost:11434/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"qwen2.5:7b-instruct","messages":[{"role":"user","content":"ping"}],"stream":false}'
```

## Agent wrapper

`scripts/local_agent.py` is the Python bridge. It:

1. Launches the BIST MCP server as a child process (stdio transport).
2. Lists the 21 MCP tools and translates their schemas into OpenAI tool-calling format.
3. Hits `http://localhost:11434/v1/chat/completions` with `tool_choice="auto"`.
4. Shuttles each `tool_calls` entry back to the MCP server, appends the result as a
   `role: tool` message, and re-invokes the model until it produces a tool-less answer
   or `max_turns` is reached.
5. Dumps a trace at `outputs/agent/local_agent.trace.json` and the final answer at
   `outputs/agent/local_agent.result.json`.

Smoke test (one tool call):

```powershell
.\.venv\Scripts\python.exe scripts\local_agent.py --smoke
```

Full ticker analysis:

```powershell
.\.venv\Scripts\python.exe scripts\local_agent.py --ticker THYAO.IS --as-of 2025-12-31
```

Environment overrides:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Point at a remote Ollama instance (same LAN only; submission must be local) |
| `BIST_LOCAL_MODEL` | `qwen2.5:7b-instruct` | Switch model without editing the script |

## Fine-tuned adapter (produced in Phase F)

The LoRA adapter is trained on Colab/Kaggle T4 and exported to GGUF. It is loaded
through a custom Modelfile that chains the adapter onto the Qwen base:

```powershell
# Phase F produces training/bist_lora.gguf
ollama create bist-qwen -f training/Modelfile.finetuned
ollama run bist-qwen  # verify
```

Then switch the agent with no code change:

```powershell
$env:BIST_LOCAL_MODEL = "bist-qwen"
.\.venv\Scripts\python.exe scripts\local_agent.py --smoke
```

## 5-stage A–E harness

Once the model answers smoke questions, re-run the full five-stage experiment with
the local backend:

```powershell
.\.venv\Scripts\python.exe scripts\run_harness_experiments.py --backend ollama --model qwen2.5:7b-instruct
.\.venv\Scripts\python.exe scripts\run_harness_experiments.py --backend ollama --model bist-qwen
```

Outputs land in `outputs/harness/`; `comparison.json` collects per-stage §30 metrics.
The Codex-CLI backend is retained only as a legacy development comparison and is not
used for submission.

## Offline verification

During the smoke run, disable the workstation's network adapter (or watch
`netstat -an | findstr ESTABLISHED` for non-localhost connections). No non-localhost
traffic is expected: Ollama runs on 127.0.0.1:11434 and the MCP child process is
pure stdin/stdout with no sockets.

## Troubleshooting

- **`connection refused`**: `ollama serve` is not running. Start the service or reboot.
- **`model not found`**: run `ollama list`; pull the base model again.
- **Model ignores tools**: Qwen 2.5 7B emits tool-calls reliably; smaller or older
  models may need the alternate prompt in `scripts/local_agent.py` (`--tool-style xml`).
- **Tool-call arguments malformed**: the adapter will fix this post-training; baseline
  numbers in `outputs/harness/baseline_local.score.json` capture the pre-training rate.
