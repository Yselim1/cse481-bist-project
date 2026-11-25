"""Unsloth QLoRA fine-tune of Qwen 2.5 3B Instruct on the BIST educational-agent dataset.

Replaces the earlier ``train_lora.py`` (HF peft + trl + bnb) flow. The raw stack kept
colliding with Colab's moving base image (torch 2.5.1+cu121 one boot, 2.14.1+cu130 the
next) — bitsandbytes wheels do not track these revisions fast enough and 7B QLoRA sits
at the T4 memory cliff anyway. Unsloth bundles a tested compatibility matrix per Colab
image and Qwen 2.5 3B leaves ~8 GB of VRAM headroom on a T4 even at seq_len 2048.

Run from /content/bist on Colab after `pip install unsloth`::

    python training/train_unsloth.py \
        --train training/dataset/train.jsonl \
        --eval  training/dataset/eval.jsonl \
        --output training/outputs/lora \
        --gguf training/bist_lora.gguf

Writes, besides the checkpoints:
    <output>/adapter_model.safetensors, adapter_config.json   the LoRA adapter (submission)
    <output>/training_run.json                                hyperparameters + provenance
    training/config/hyperparams.json                          same record, committed to the repo

This script is not intended to run on the Windows workstation — the base model and
4-bit quantization kernels require a CUDA GPU.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

BASE_MODEL_UPSTREAM = "Qwen/Qwen2.5-3B-Instruct"


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hf_revision(repo_id: str) -> str | None:
    try:
        from huggingface_hub import model_info
        return model_info(repo_id).sha
    except Exception:  # noqa: BLE001 - offline or hub hiccup: record as unknown
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default="unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
                        help="Unsloth-published 4-bit checkpoint (saves a 6 GB download).")
    parser.add_argument("--train", required=True)
    parser.add_argument("--eval", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gguf", default=None,
                        help="If set, export merged GGUF to this path after training.")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--max-length", type=int, default=3072,
                        help="Dataset v2 conversations peak at ~2.6k Qwen tokens.")
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--run-record", default="training/config/hyperparams.json")
    args = parser.parse_args()
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    t0 = time.time()

    # Deferred import so `python -m` style tooling can at least load the script on CPU.
    # Unsloth must be imported before trl/transformers (it patches them), hence noqa.
    import torch
    from unsloth import FastLanguageModel  # noqa: I001
    from unsloth.chat_templates import get_chat_template, train_on_responses_only
    from datasets import load_dataset
    from trl import SFTConfig, SFTTrainer

    # T4 (Turing) only supports fp16; A100/L4/H100 (Ampere+) support bf16.
    bf16_ok = torch.cuda.is_available() and torch.cuda.is_bf16_supported()

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_length,
        dtype=None,          # Unsloth picks bf16/fp16 for the current GPU.
        load_in_4bit=True,
    )
    tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
    )

    train_ds = load_dataset("json", data_files=args.train, split="train")
    eval_ds = load_dataset("json", data_files=args.eval, split="train")

    def format_messages(example: dict) -> dict:
        text = tokenizer.apply_chat_template(example["messages"],
                                              tokenize=False, add_generation_prompt=False)
        return {"text": text}

    train_ds = train_ds.map(format_messages, remove_columns=train_ds.column_names)
    eval_ds = eval_ds.map(format_messages, remove_columns=eval_ds.column_names)

    sft_config = SFTConfig(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type="cosine",
        logging_steps=5,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        bf16=bf16_ok,
        fp16=not bf16_ok,
        max_seq_length=args.max_length,
        packing=False,
        dataset_text_field="text",
        report_to=["none"],
        seed=args.seed,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=sft_config,
    )
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|im_start|>user\n",
        response_part="<|im_start|>assistant\n",
    )

    train_result = trainer.train()
    trainer.save_model(args.output)          # PEFT model -> adapter_model.safetensors only
    tokenizer.save_pretrained(args.output)
    adapter = Path(args.output, "adapter_model.safetensors")
    adapter_cfg = Path(args.output, "adapter_config.json")
    if not adapter.exists() or not adapter_cfg.exists():
        raise SystemExit(f"LoRA adapter files missing in {args.output}: "
                         f"{sorted(p.name for p in Path(args.output).iterdir())}")

    metrics = trainer.evaluate()
    Path(args.output, "eval_metrics.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(json.dumps(metrics, indent=2, default=str))

    import datasets
    import peft
    import transformers
    import trl
    import unsloth
    record = {
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "train_seconds": round(time.time() - t0, 1),
        "method": "QLoRA (4-bit base, LoRA adapters) via Unsloth + TRL SFTTrainer, "
                  "loss on assistant turns only (train_on_responses_only)",
        "base_model": {
            "upstream": BASE_MODEL_UPSTREAM,
            "upstream_revision": _hf_revision(BASE_MODEL_UPSTREAM),
            "training_checkpoint": args.base_model,
            "training_checkpoint_revision": _hf_revision(args.base_model),
            "source": f"https://huggingface.co/{BASE_MODEL_UPSTREAM}",
            "license": "Qwen Research License (qwen2.5-3b-instruct)",
        },
        "hyperparameters": {
            "epochs": args.epochs, "per_device_batch": args.batch, "grad_accum": args.grad_accum,
            "effective_batch": args.batch * args.grad_accum, "learning_rate": args.lr,
            "lr_scheduler": "cosine", "warmup_ratio": args.warmup_ratio,
            "lora_rank": args.lora_rank, "lora_alpha": args.lora_alpha,
            "lora_dropout": args.lora_dropout, "bias": "none",
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                               "gate_proj", "up_proj", "down_proj"],
            "max_seq_length": args.max_length, "load_in_4bit": True,
            "precision": "bf16" if bf16_ok else "fp16", "packing": False,
            "gradient_checkpointing": "unsloth", "seed": args.seed,
            "chat_template": "qwen-2.5",
        },
        "dataset": {
            "train": args.train, "train_sha256": _sha256(args.train), "train_rows": len(train_ds),
            "eval": args.eval, "eval_sha256": _sha256(args.eval), "eval_rows": len(eval_ds),
        },
        "results": {
            "train_loss": getattr(train_result, "training_loss", None),
            "global_steps": getattr(train_result, "global_step", None),
            "eval": metrics,
            "log_history": trainer.state.log_history,
        },
        "adapter": {
            "path": str(adapter), "sha256": _sha256(adapter), "bytes": adapter.stat().st_size,
            "config_sha256": _sha256(adapter_cfg),
            "config": json.loads(adapter_cfg.read_text(encoding="utf-8")),
        },
        "environment": {
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "peak_gpu_memory_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)
            if torch.cuda.is_available() else None,
            "python": platform.python_version(), "torch": torch.__version__,
            "transformers": transformers.__version__, "trl": trl.__version__,
            "peft": peft.__version__, "datasets": datasets.__version__,
            "unsloth": getattr(unsloth, "__version__", None),
        },
    }
    text = json.dumps(record, indent=2, default=str)
    Path(args.output, "training_run.json").write_text(text, encoding="utf-8")
    Path(args.run_record).parent.mkdir(parents=True, exist_ok=True)
    Path(args.run_record).write_text(text, encoding="utf-8")
    print(f"adapter sha256 {record['adapter']['sha256']}  ->  {args.run_record}")

    if args.gguf:
        gguf_path = Path(args.gguf)
        gguf_path.parent.mkdir(parents=True, exist_ok=True)
        # Unsloth's save_pretrained_gguf handles the llama.cpp conversion itself and
        # writes a merged f16/q4 GGUF alongside the adapter.
        model.save_pretrained_gguf(str(gguf_path.with_suffix("")),
                                    tokenizer, quantization_method="q4_k_m")


if __name__ == "__main__":
    main()
