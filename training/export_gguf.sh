#!/usr/bin/env bash
# Convert a trained LoRA adapter to GGUF so Ollama can load it.
# Run on Colab or any Linux box with ~6 GB free disk.
set -euo pipefail

ADAPTER_DIR=${1:-training/outputs/lora}
OUT_GGUF=${2:-training/bist_lora.gguf}
LLAMA_CPP_DIR=${3:-/content/llama.cpp}

if [[ ! -d "${LLAMA_CPP_DIR}" ]]; then
  git clone --depth 1 https://github.com/ggerganov/llama.cpp "${LLAMA_CPP_DIR}"
  pip install -q -r "${LLAMA_CPP_DIR}/requirements.txt"
fi

python "${LLAMA_CPP_DIR}/convert_lora_to_gguf.py" \
  --base "Qwen/Qwen2.5-7B-Instruct" \
  --outfile "${OUT_GGUF}" \
  "${ADAPTER_DIR}"

echo "GGUF adapter written to ${OUT_GGUF}"
echo "Next: scp back to Windows and run:"
echo "  ollama create bist-qwen -f training/Modelfile.finetuned"
