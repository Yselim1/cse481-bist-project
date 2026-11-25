# QLoRA training runbook (Colab T4): Unsloth + Qwen 2.5 3B

This is the end-to-end procedure for the GPU training run. It produces the three things
the submission needs from one run:

| Output | Where it ends up locally | Used for |
|---|---|---|
| `adapter_model.safetensors` + `adapter_config.json` | `training/adapter/` | submitted LoRA adapter (SHA-256 in `submission.json`) |
| `training_run.json` (hyperparameters, base-model revision, losses, versions) | `training/config/hyperparams.json` | submitted fine-tuning config |
| merged Q4_K_M GGUF (base + this adapter) | `training/bist_lora.gguf` (not committed) | served by Ollama as `bist-qwen` |

The GGUF is exported **from the same in-memory model** right after the adapter is saved.
So the model answering in class is the submitted base model plus the submitted adapter.

Why Unsloth and 3B: the raw `peft/trl/bitsandbytes` recipe kept breaking on Colab's
changing base image, and 7B QLoRA is at the T4 memory limit. Unsloth ships a tested
dependency set, and Qwen 2.5 3B trains in about 25 min with room to spare. The chat
template and tool-call format are the same as 7B.

## 0. Before Colab (Windows)

The dataset (v2) is already built and committed: `training/dataset/{train,eval}.jsonl`
and `audit.json`. To rebuild it, start Ollama and run:

```powershell
.\.venv\Scripts\python.exe training\dataset\build.py --target 400 --seed 17
```

It is deterministic for a given seed and data snapshot. `audit.json` records the SHA-256 of both splits.

Push the repo so Colab can clone it (or upload a zip of the repo in Cell 2 instead).

## 1. Colab session

Create a new notebook and set **Runtime → Change runtime type → T4 GPU**.

**Cell 1: install Unsloth** (it brings compatible torch/bnb/triton/trl/peft pins; do not pin them yourself):

```python
!pip install -q "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
```

**Cell 2: get the repo:**

```python
import getpass, subprocess, os
token = getpass.getpass("GitHub token (press Enter if repo is public): ").strip()
repo = "Yselim1/cse481-bist-project"
url = f"https://{token}@github.com/{repo}.git" if token else f"https://github.com/{repo}.git"
subprocess.check_call(["git", "clone", url, "/content/bist"])
os.chdir("/content/bist")
!git log --oneline -1 && head -c 400 training/dataset/audit.json
```

**Cell 3: mount Google Drive.** Every artifact is copied here, so a closed tab never loses the adapter again:

```python
from google.colab import drive
drive.mount("/content/drive")
RUN_DIR = "/content/drive/MyDrive/bist_lora_run_v2"
os.makedirs(RUN_DIR, exist_ok=True)
```

**Cell 4: train, save the adapter, and export the GGUF** (about 25–35 min):

```python
!python training/train_unsloth.py \
   --train training/dataset/train.jsonl \
   --eval  training/dataset/eval.jsonl \
   --output training/outputs/lora \
   --gguf training/bist_lora.gguf \
   --epochs 3 --batch 2 --grad-accum 8 --max-length 3072 --lr 2e-4 --seed 17
```

If it runs out of memory (unlikely), use `--batch 1 --grad-accum 16`. That keeps the
effective batch at 16 and the run comparable. If you have to restart more than twice,
stop and start again from a fresh runtime rather than patching.

**Cell 5: copy everything to Drive immediately:**

```python
import glob, shutil, json
lora = "training/outputs/lora"
for name in ["adapter_model.safetensors", "adapter_config.json", "training_run.json",
             "eval_metrics.json", "tokenizer_config.json", "special_tokens_map.json",
             "tokenizer.json", "chat_template.jinja"]:
    if os.path.exists(f"{lora}/{name}"):
        shutil.copy(f"{lora}/{name}", RUN_DIR)
gguf = sorted(glob.glob("training/bist_lora*/**/*Q4_K_M*.gguf", recursive=True)
              + glob.glob("training/*Q4_K_M*.gguf"))[0]
shutil.copy(gguf, f"{RUN_DIR}/bist_lora.gguf")
rec = json.load(open(f"{lora}/training_run.json"))
print("adapter sha256:", rec["adapter"]["sha256"])
print("train_loss:", rec["results"]["train_loss"], "eval:", rec["results"]["eval"].get("eval_loss"))
!ls -la {RUN_DIR}
```

**Cell 6: download.** You can also fetch the files from Drive later:

```python
from google.colab import files
# The zip holds the adapter + run record only; the 2 GB GGUF is downloaded separately.
!cd {RUN_DIR} && zip -q /content/bist_adapter.zip adapter_model.safetensors adapter_config.json training_run.json eval_metrics.json
files.download("/content/bist_adapter.zip")
files.download(f"{RUN_DIR}/bist_lora.gguf")
```

## 2. Install locally (Windows)

```powershell
Expand-Archive ~/Downloads/bist_adapter.zip -DestinationPath training/adapter -Force
Move-Item training/adapter/training_run.json training/config/hyperparams.json -Force
Move-Item ~/Downloads/bist_lora.gguf training/bist_lora.gguf -Force
ollama create bist-qwen -f training/Modelfile.finetuned
(Get-FileHash training/adapter/adapter_model.safetensors -Algorithm SHA256).Hash   # must equal hyperparams.json adapter.sha256
.\.venv\Scripts\python.exe scripts\local_agent.py --smoke --model bist-qwen
```

## 3. Evaluate base vs fine-tuned

The only variable is the adapter. Both runs use the same 3B base, prompts and harness:

```powershell
.\.venv\Scripts\python.exe training\eval\run_baseline.py --model qwen2.5:3b-instruct
Rename-Item outputs\harness\baseline_local.score.json base_3b.score.json -Force
.\.venv\Scripts\python.exe training\eval\run_baseline.py --model bist-qwen
Rename-Item outputs\harness\baseline_local.score.json finetuned.score.json -Force
.\.venv\Scripts\python.exe training\eval\compare.py --base outputs\harness\base_3b.score.json `
    --finetuned outputs\harness\finetuned.score.json
```

The report lands at `outputs/training/base_vs_finetuned.md`. Refresh `docs/MODEL_CARD.md` from it.

## 4. Presentation traces and submission

```powershell
.\.venv\Scripts\python.exe scripts\run_presentation_scenarios.py     # 5 traces + traces.html
.\.venv\Scripts\python.exe scripts\build_submission.py               # submission.json
.\.venv\Scripts\python.exe scripts\verify_submission.py              # recomputes every SHA-256
```
