# QLoRA training runbook (Colab T4)

End-to-end instructions for the user who runs the actual GPU training. All files already
exist in the repo; this doc only tells the operator which cells to execute.

## 0. Prerequisites

- A free Google Colab account (Colab offers 15 GB T4 for ~4 h sessions, enough for 3 epochs on 400 examples).
- This repo pushed to a Git host the Colab runtime can clone (public fork or a token-protected clone).
- Dataset built locally first:

```powershell
# On Windows, with Ollama already able to answer basic smoke questions:
.\.venv\Scripts\python.exe scripts\local_agent.py --smoke
# Build dataset by hitting the live MCP server (takes ~10 min):
.\.venv\Scripts\python.exe training\dataset\build.py --target 400 --seed 17
# Commit the resulting training/dataset/{train,eval}.jsonl to the repo so Colab can pull them.
git add training/dataset/*.jsonl training/dataset/audit.json
git commit -m "dataset: initial 400-example corpus"
git push
```

## 1. Colab session setup

**IMPORTANT**: credentials for cloning are provided by the user interactively in the Colab
runtime; do not commit tokens to this repo.

Cell 1 — environment:

```python
!pip install -q transformers==4.46.2 peft==0.14.0 trl==0.12.1 bitsandbytes==0.44.1 \
                 accelerate==1.1.1 datasets==3.0.1 sentencepiece==0.2.0
!pip install -q flash-attn --no-build-isolation
```

Cell 2 — clone + checkout:

```python
import getpass, subprocess
token = getpass.getpass("GitHub token (or press Enter if repo is public): ").strip()
repo = "Yselim1/cse481-bist-project"
url = f"https://{token}@github.com/{repo}.git" if token else f"https://github.com/{repo}.git"
subprocess.check_call(["git", "clone", url, "/content/bist"])
%cd /content/bist
```

Cell 3 — train:

```python
!python training/train_lora.py \
   --train training/dataset/train.jsonl \
   --eval  training/dataset/eval.jsonl \
   --output training/outputs/lora \
   --epochs 3 --batch 4 --grad-accum 4 --lr 2e-4
```

Expected wall-clock: ~70 min for 400 examples on T4. If OOM occurs, drop `--batch` to 2
and raise `--grad-accum` to 8.

Cell 4 — export to GGUF:

```python
!bash training/export_gguf.sh training/outputs/lora training/bist_lora.gguf
```

Cell 5 — download the GGUF back to the Windows workstation:

```python
from google.colab import files
files.download("training/bist_lora.gguf")
```

## 2. Local install (back on Windows)

Drop `bist_lora.gguf` into `training/` and build the Ollama tag:

```powershell
Move-Item ~/Downloads/bist_lora.gguf training/bist_lora.gguf
ollama create bist-qwen -f training/Modelfile.finetuned
ollama run bist-qwen "project_status"
```

## 3. Evaluate base vs fine-tuned

```powershell
.\.venv\Scripts\python.exe training\eval\run_baseline.py --model qwen2.5:7b-instruct
Rename-Item outputs\harness\baseline_local.score.json outputs\harness\base.score.json
.\.venv\Scripts\python.exe training\eval\run_baseline.py --model bist-qwen
Rename-Item outputs\harness\baseline_local.score.json outputs\harness\finetuned.score.json
.\.venv\Scripts\python.exe training\eval\compare.py
```

The comparison report lands at `outputs/training/base_vs_finetuned.md` and must show
improvement on ≥3 of the §30 metrics (invalid tool-call rate, missing-required-tool
rate, label mismatch, advice leak, reproducibility).

## 4. Submission wiring

After the comparison passes, Phase G re-runs the 5-stage harness under the fine-tuned
tag, Phase H bundles the GGUF into the submission zip via `scripts/package_project.py`.
