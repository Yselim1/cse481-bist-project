# Local setup — fresh Windows machine → full submission reproduction

Target: a graded instructor with a stock Windows 11 laptop can reproduce every artefact
in `SUBMISSION_MANIFEST.json` by running the five commands below.

## 1. Python environment (10 min)

```powershell
# Ship-fresh prerequisites:
#   - Python 3.12 (python.org installer)
#   - Git for Windows
#   - 8 GB free disk

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install uv==0.12.15
.\.venv\Scripts\uv.exe sync --frozen --extra dev --python .\.venv\Scripts\python.exe
```

## 2. Validate pure-Python surface (5 min)

```powershell
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\ruff.exe check src tests scripts
.\.venv\Scripts\python.exe scripts\verify_mcp.py
.\.venv\Scripts\python.exe scripts\verify_reproduction.py
```

Every test must pass green; `verify_mcp.py` must match tool outputs to 1e-6.

## 3. Ollama + local LLM (10 min, one-time)

```powershell
# Download https://ollama.com/download/windows  — one-click installer; registers as a service.
ollama pull qwen2.5:7b-instruct                         # ≈4.3 GB
# If the submission zip ships bist_lora.gguf (Phase F artefact):
ollama create bist-qwen -f training/Modelfile.finetuned
# Otherwise fall back to the base tag:
ollama create bist-qwen -f training/Modelfile.base
```

## 4. Smoke the local agent (1 min)

```powershell
.\.venv\Scripts\python.exe scripts\local_agent.py --smoke
```

The command launches the MCP server as a child process and runs one tool call against
Ollama. Expect a two-sentence summary and `outputs/agent/local_agent.result.json` on disk.

## 5. Reproduce the five-stage harness (20 min)

```powershell
.\.venv\Scripts\python.exe scripts\run_harness_experiments.py --backend ollama --model bist-qwen
```

Outputs:

- `outputs/harness/{raw_llm,llm_tools,stateful_harness,evidence_quality_gate,memory_human_review}.json`
- `outputs/harness/*.score.json` with §30 metrics
- `outputs/harness/comparison.json` with monotonic improvement across the 5 stages
- `outputs/harness/human_review.json` requires sign-off before final grading

## 6. Regenerate the full PDF report (5 min)

```powershell
.\.venv\Scripts\python.exe -m bist_analytics.cli --config config/tms29.yaml run
.\.venv\Scripts\python.exe scripts\build_scenarios.py
.\.venv\Scripts\python.exe scripts\build_pdf.py
```

The PDF lands at `output/THYAO_Implementation_Package.pdf`; the full zip is produced by
`scripts/package_project.py`.

## Network isolation verification

During step 4 and 5, open a second PowerShell window and run:

```powershell
netstat -an | Select-String ":11434"
netstat -an | Select-String "ESTABLISHED" | Where-Object { $_ -notmatch "127.0.0.1" }
```

Only `127.0.0.1:11434` connections should appear — Ollama on localhost. The second filter
should return empty (no outbound ESTABLISHED sockets during inference). Alternatively,
disable the Wi-Fi adapter before step 4; everything must still work.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `uv` fails to resolve | Re-download the lockfile; this repo pins to `uv.lock` at a known-good state |
| `pytest` imports fail with `ModuleNotFoundError` | Ensure `.venv\Scripts\python.exe` is the shebang — not system Python |
| `ollama: command not found` | Reboot after installer; or run `C:\Users\<you>\AppData\Local\Programs\Ollama\ollama.exe` directly |
| `MCP server closed before responding` | Check `outputs/harness/<stage>.stderr.log`; usually a config path issue |
| GGUF adapter fails to load | Run `ollama show bist-qwen`; verify the adapter file is next to the Modelfile |

See also:
- `docs/LOCAL_MODEL.md` — model stack deep-dive
- `docs/MODEL_CARD.md` — training config + limitations
- `docs/DECISIONS.md` — frozen thresholds (strategy + gate)
