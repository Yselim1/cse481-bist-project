# QLoRA training runbook (Colab T4) — Unsloth + Qwen 2.5 3B

End-to-end instructions for the user who runs the actual GPU training. The earlier
`train_lora.py` + raw `peft/trl/bitsandbytes` recipe kept colliding with Colab's moving
base image (torch 2.5.1+cu121 one boot, 2.14.1+cu130 the next — bnb wheels could not
track the drift) and 7B QLoRA sits at the T4 memory cliff anyway. This runbook uses
**Unsloth** (which owns its own tested compatibility matrix per Colab image) and
**Qwen 2.5 3B Instruct** (the project plan's D2 fallback for <12 GB effective VRAM).

- Same chat template and tokenizer as Qwen 7B → downstream harness/eval code unchanged.
- ~20 min training vs ~70 min on 7B; leaves ~8 GB VRAM headroom at seq_len 2048.

## 0. Prerequisites

- A free Google Colab account with a T4 runtime.
- This repo pushed to a Git host the Colab runtime can clone.
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

**Create a new Colab notebook. Set runtime type → T4 GPU.**

Cell 1 — install Unsloth (it brings its own compatible torch/bnb/triton pins):

```python
!pip install -q "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install -q --no-deps "xformers<0.0.27" "trl<0.9.0" peft accelerate bitsandbytes
```

If Unsloth prints a compatibility warning about torch or triton, follow its on-screen
instructions — it emits the exact `pip install` line needed for the current Colab image.

Cell 2 — clone the repo:

```python
import getpass, subprocess, os
token = getpass.getpass("GitHub token (press Enter if repo is public): ").strip()
repo = "Yselim1/cse481-bist-project"
url = f"https://{token}@github.com/{repo}.git" if token else f"https://github.com/{repo}.git"
subprocess.check_call(["git", "clone", url, "/content/bist"])
os.chdir("/content/bist")
!ls training/dataset
```

Cell 3 — train + export GGUF in one go:

```python
!python training/train_unsloth.py \
   --train training/dataset/train.jsonl \
   --eval  training/dataset/eval.jsonl \
   --output training/outputs/lora \
   --gguf training/bist_lora.gguf \
   --epochs 3 --batch 4 --grad-accum 4 --max-length 2048 --lr 2e-4
```

Expected wall-clock: ~20 min for 400 examples on T4. If OOM still occurs (unusual on 3B),
drop `--batch` to 2 and raise `--grad-accum` to 8; drop `--max-length` to 1024 if that
is not enough.

Cell 4 — download the GGUF to the Windows workstation:

```python
from google.colab import files
files.download("training/bist_lora.gguf")
```

## 2. Local install (back on Windows)

Drop `bist_lora.gguf` into `training/`, pull the 3B base model (one-time, ~2 GB), and
build the Ollama tag:

```powershell
Move-Item ~/Downloads/bist_lora.gguf training/bist_lora.gguf
ollama pull qwen2.5:3b-instruct
ollama create bist-qwen -f training/Modelfile.finetuned
ollama run bist-qwen "project_status"
```

## 3. Evaluate base vs fine-tuned

The baseline eval was recorded against `qwen2.5:7b-instruct`
(`outputs/harness/baseline_local.score.json`). For the apples-to-apples base-vs-tuned
comparison use the 3B baseline so the only variable is fine-tuning:

```powershell
ollama pull qwen2.5:3b-instruct
.\.venv\Scripts\python.exe training\eval\run_baseline.py --model qwen2.5:3b-instruct
Rename-Item outputs\harness\baseline_local.score.json outputs\harness\base_3b.score.json
.\.venv\Scripts\python.exe training\eval\run_baseline.py --model bist-qwen
Rename-Item outputs\harness\baseline_local.score.json outputs\harness\finetuned.score.json
.\.venv\Scripts\python.exe training\eval\compare.py --base outputs\harness\base_3b.score.json \
    --finetuned outputs\harness\finetuned.score.json
```

The comparison report lands at `outputs/training/base_vs_finetuned.md` and must show
improvement on ≥3 of the §30 metrics (invalid tool-call rate, missing-required-tool
rate, label mismatch, advice leak, reproducibility). The original 7B baseline is kept
for reference as the stronger-base comparison point.

## 4. Submission wiring

After the comparison passes, Phase G re-runs the 5-stage harness under the `bist-qwen`
tag, Phase H bundles the GGUF + updated Modelfile into the submission zip via
`scripts/package_project.py`.
