"""QLoRA fine-tune Qwen 2.5 7B Instruct on the BIST educational-agent dataset.

Designed to run unmodified on a free Colab T4 (15 GB VRAM) or Kaggle T4 (16 GB VRAM).
Uses 4-bit bitsandbytes quantization + LoRA adapters via HuggingFace peft + trl.

Setup (Colab cell):
    !pip install -q transformers==4.46.2 peft==0.14.0 trl==0.12.1 bitsandbytes==0.44.1 \
                   accelerate==1.1.1 datasets==3.0.1
    !pip install -q flash-attn --no-build-isolation
    # Mount Drive and clone the repo:
    from google.colab import drive; drive.mount('/content/drive')
    !git clone <your-fork> /content/bist
    %cd /content/bist

Run:
    !python training/train_lora.py \
        --train training/dataset/train.jsonl \
        --eval  training/dataset/eval.jsonl \
        --output training/outputs/lora \
        --epochs 3 --batch 4 --grad-accum 4

The resulting adapter directory is converted to GGUF via llama.cpp and loaded by Ollama
through ``training/Modelfile.finetuned``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--train", required=True)
    parser.add_argument("--eval", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    # Deferred imports so the module can be read on machines without a GPU toolchain.
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True,
                                              trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, quantization_config=quant,
        device_map="auto", trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2" if _has_flash_attn() else "eager",
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=args.lora_rank, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
        bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
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
        lr_scheduler_type="cosine",
        warmup_ratio=args.warmup_ratio,
        logging_steps=5,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        bf16=True,
        max_seq_length=args.max_length,
        packing=False,
        dataset_text_field="text",
        gradient_checkpointing=True,
        report_to=["none"],
        seed=args.seed,
    )

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        train_dataset=train_ds, eval_dataset=eval_ds,
        args=sft_config, peft_config=lora_config,
    )
    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    metrics = trainer.evaluate()
    Path(args.output, "eval_metrics.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(json.dumps(metrics, indent=2, default=str))


def _has_flash_attn() -> bool:
    try:
        import flash_attn  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
