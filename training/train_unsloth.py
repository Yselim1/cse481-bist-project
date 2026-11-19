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

This script is not intended to run on the Windows workstation — the base model and
4-bit quantization kernels require a CUDA GPU.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


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
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    # Deferred import so `python -m` style tooling can at least load the script on CPU.
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template, train_on_responses_only
    from datasets import load_dataset
    from trl import SFTConfig, SFTTrainer

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
        bf16=True,
        fp16=False,
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

    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    metrics = trainer.evaluate()
    Path(args.output, "eval_metrics.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(json.dumps(metrics, indent=2, default=str))

    if args.gguf:
        gguf_path = Path(args.gguf)
        gguf_path.parent.mkdir(parents=True, exist_ok=True)
        # Unsloth's save_pretrained_gguf handles the llama.cpp conversion itself and
        # writes a merged f16/q4 GGUF alongside the adapter.
        model.save_pretrained_gguf(str(gguf_path.with_suffix("")),
                                    tokenizer, quantization_method="q4_k_m")


if __name__ == "__main__":
    main()
