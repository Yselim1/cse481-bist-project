r"""Build ``submission.json``: the single manifest for the presentation submission.

    .\.venv\Scripts\python.exe scripts/build_submission.py
    .\.venv\Scripts\python.exe scripts/verify_submission.py

The manifest names every attachment with its role, size and SHA-256:
  * source_code       tool definitions (MCP server + analysis), agent/harness, run scripts
  * fine_tuning       training data (JSONL), hyperparameters/config (JSON), dataset audit
  * model_weights     LoRA adapter (safetensors) + adapter_config, base model name/version/source
  * rag               knowledge base (JSON) with per-document source metadata
  * execution_traces  the five scenario question-answer records (JSON)
Ollama's served-model digest is recorded too. Every trace must carry the same digest.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "submission.json"
META = ROOT / "presentation" / "submission_meta.json"

SOURCE_CODE = {
    "tools": ["src/bist_analytics/mcp/server.py", "src/bist_analytics/analysis/*.py",
              "src/bist_analytics/strategy/*.py", "src/bist_analytics/backtest/*.py",
              "src/bist_analytics/data/*.py", "src/bist_analytics/rag.py",
              "src/bist_analytics/pipeline.py", "src/bist_analytics/config.py",
              "src/bist_analytics/schemas.py", "src/bist_analytics/io.py",
              "src/bist_analytics/__init__.py", "src/bist_analytics/*/__init__.py"],
    "agent_harness": ["scripts/local_agent.py", "src/bist_analytics/harness/grounding.py"],
    "run_scripts": ["scripts/run_presentation_scenarios.py", "scripts/ask.py",
                    "scripts/build_rag_kb.py", "scripts/build_submission.py",
                    "scripts/verify_submission.py"],
    "training_code": ["training/dataset/build.py", "training/train_unsloth.py",
                      "training/Modelfile.finetuned", "training/Modelfile.base",
                      "training/export_gguf.sh"],
    "evaluation_code": ["training/eval/run_baseline.py", "training/eval/compare.py",
                        "scripts/run_harness_experiments.py", "scripts/generate_deliverables.py",
                        "src/bist_analytics/harness/evaluation.py"],
    "environment": ["pyproject.toml", "uv.lock"],
}
CONFIGS = ["config/universe_live.yaml", "config/universe10.yaml", "config/bist100_universe.yaml", "presentation/scenarios.json"]


# Text files are hashed with LF line endings so the hash is the same on a Windows checkout
# (core.autocrlf) and a Linux/macOS one. Binary files (safetensors, gguf, pdf) are hashed as-is.
BINARY_SUFFIXES = {".safetensors", ".gguf", ".pdf", ".png", ".jpg", ".zip", ".bin"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    if path.suffix.lower() not in BINARY_SUFFIXES and path.stat().st_size < 64 << 20:
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
        return h.hexdigest()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entry(rel: str, role: str, **extra) -> dict:
    path = ROOT / rel
    if not path.exists():
        return {"path": rel, "role": role, "status": "MISSING", **extra}
    return {"path": rel, "role": role, "bytes": path.stat().st_size, "sha256": sha256(path), **extra}


def expand(patterns: list[str]) -> list[str]:
    out: list[str] = []
    for pattern in patterns:
        matches = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file())
        out.extend(matches or [pattern])
    return list(dict.fromkeys(out))


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main() -> None:
    from scripts.local_agent import model_provenance

    meta = json.loads(META.read_text(encoding="utf-8"))
    attachments: list[dict] = []

    # --- model weights ---------------------------------------------------------------------
    run_record_path = ROOT / "training" / "config" / "hyperparams.json"
    run_record = json.loads(run_record_path.read_text(encoding="utf-8")) if run_record_path.exists() else {}
    base = run_record.get("base_model") or {
        "upstream": "Qwen/Qwen2.5-3B-Instruct", "upstream_revision": None,
        "training_checkpoint": "unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
        "source": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct"}
    adapter = entry("training/adapter/adapter_model.safetensors", "lora_adapter", format="safetensors")
    adapter_cfg = entry("training/adapter/adapter_config.json", "lora_adapter_config")
    attachments += [adapter, adapter_cfg]
    recorded = (run_record.get("adapter") or {}).get("sha256")

    served = model_provenance(meta["served_model_name"])
    gguf = ROOT / "training" / "bist_lora.gguf"

    # --- fine-tuning -----------------------------------------------------------------------
    fine_tuning = [entry("training/dataset/train.jsonl", "training_data", format="jsonl"),
                   entry("training/dataset/eval.jsonl", "evaluation_data", format="jsonl"),
                   entry("training/dataset/audit.json", "dataset_audit"),
                   entry("training/config/hyperparams.json", "hyperparameters_and_run_record")]
    attachments += fine_tuning

    # --- RAG -------------------------------------------------------------------------------
    kb_rel = "rag/knowledge_base.json"
    kb = json.loads((ROOT / kb_rel).read_text(encoding="utf-8"))
    rag = entry(kb_rel, "rag_knowledge_base", documents=kb["document_count"],
                source_counts=kb["source_counts"], retrieval=kb["retrieval"])
    attachments.append(rag)

    # --- traces ----------------------------------------------------------------------------
    index_path = ROOT / "outputs" / "presentation" / "index.json"
    traces = []
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for row in index["traces"]:
            traces.append(entry(row["trace"], "execution_trace", scenario_id=row["id"],
                                scenario=row["scenario"], question=row["question"],
                                model=row["model"], model_digest=row["model_digest"],
                                seed=row["seed"], temperature=row["temperature"],
                                started_at=row["started_at"], label=row["label"],
                                tools_called=row["tools_called"], all_grounded=row["all_grounded"]))
        attachments.append(entry("outputs/presentation/index.json", "trace_index"))
        attachments.append(entry("outputs/presentation/traces.html", "trace_viewer"))
    attachments += traces

    # --- evaluation results ----------------------------------------------------------------
    evaluation = [entry("outputs/training/base_vs_finetuned.md", "evaluation_report"),
                  entry("outputs/training/figures/base_vs_finetuned.png", "evaluation_chart"),
                  entry("outputs/harness/eval_v3/summary.json", "evaluation_summary")]
    evaluation += [entry(f"outputs/harness/eval_v3/{m}.{p}.score.json", "evaluation_scores", model=m, protocol=p)
                   for m in ("base", "finetuned") for p in ("original", "presentation")]
    evaluation += [entry(f"outputs/harness/comparison.{m}.json", "harness_comparison", model=m)
                   for m in ("base", "finetuned")]
    evaluation.append(entry("outputs/training/phase_g_harness_summary.md", "harness_report"))
    attachments += evaluation

    # --- code + configs --------------------------------------------------------------------
    code = {group: [entry(rel, f"source_code:{group}") for rel in expand(patterns)]
            for group, patterns in SOURCE_CODE.items()}
    for items in code.values():
        attachments += items
    configs = [entry(rel, "configuration") for rel in CONFIGS]
    attachments += configs

    manifest = {
        "schema": "cse481-submission/1",
        "hashing": ("SHA-256. Text files are hashed with CRLF normalised to LF, so the hash does not "
                    "depend on the checkout's line endings; binary files (.safetensors, .gguf) are "
                    "hashed byte-for-byte. scripts/verify_submission.py applies the same rule."),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **{k: meta[k] for k in ("project", "course", "group_members", "repository")},
        "git": {"commit": git("rev-parse", "HEAD"),
                "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))},
        "base_model": {
            "name": "Qwen2.5-3B-Instruct",
            "version": "Qwen2.5, 3B parameters, instruct",
            "huggingface_repo": base.get("upstream"),
            "huggingface_revision": base.get("upstream_revision"),
            "training_checkpoint": base.get("training_checkpoint"),
            "training_checkpoint_revision": base.get("training_checkpoint_revision"),
            "download_source": base.get("source"),
            "ollama_base_tag": meta["base_model_ollama_tag"],
            "license": base.get("license", "Qwen Research License"),
        },
        "adapter": {**adapter, "config": adapter_cfg,
                    "sha256_recorded_at_training": recorded,
                    "matches_training_record": bool(recorded) and recorded == adapter.get("sha256"),
                    "hyperparameters": run_record.get("hyperparameters")},
        "served_model": {
            "ollama_name": meta["served_model_name"], "digest": served.get("digest"),
            "quantization": served.get("quantization_level"), "family": served.get("family"),
            "parameter_size": served.get("parameter_size"), "ollama_version": served.get("ollama_version"),
            "modelfile": entry("training/Modelfile.finetuned", "modelfile"),
            "gguf": ({"path": "training/bist_lora.gguf", "bytes": gguf.stat().st_size,
                      "sha256": sha256(gguf), "distribution": "external (not in archive; ~1.9 GB)"}
                     if gguf.exists() else {"status": "MISSING"}),
            "relation_to_adapter": ("Merged Q4_K_M GGUF exported by training/train_unsloth.py from the "
                                    "same in-memory model right after the adapter was saved: "
                                    "base + this adapter, quantized for Ollama."),
        },
        "fine_tuning": {"files": fine_tuning,
                        "method": run_record.get("method"),
                        "results": {k: (run_record.get("results") or {}).get(k)
                                    for k in ("train_loss", "global_steps", "eval")}},
        "rag": {"knowledge_base": rag, "builder": entry("scripts/build_rag_kb.py", "rag_builder"),
                "retriever": entry("src/bist_analytics/rag.py", "rag_retriever"),
                "usage": ("scripts/local_agent.py calls the MCP tool search_knowledge_base before the "
                          "first model turn and adds the hits to the user message. The model may "
                          "also call the tool itself. Documents published after the question's "
                          "as_of date are filtered out.")},
        "execution_traces": {"count": len(traces), "items": traces,
                             "scenarios_file": entry("presentation/scenarios.json", "scenario_definitions"),
                             "trace_schema": "bist-execution-trace/1",
                             "fields": ["model (name, digest, family, size, quantization, Ollama version)",
                                        "sampling (temperature, seed, top_p, num_ctx)",
                                        "system_prompt", "user_prompt", "user_message_sent",
                                        "retrieval", "steps[] (tool, arguments, date_range, result, "
                                        "result_sha256, started_at, finished_at)",
                                        "final_answer", "grounding_audit", "started_at", "finished_at"]},
        "evaluation": {"files": evaluation,
                       "base_comparison_model": "bist-qwen-base (training/Modelfile.base: qwen2.5:3b-instruct, "
                                                "same num_ctx 16384 and sampling as bist-qwen)",
                       "per_question_traces": "outputs/harness/eval_v3/traces/"},
        "live_question": {"cli": "scripts/ask.py \"<question>\"",
                          "same_code_path_as_scenarios": True,
                          "traces_dir": "outputs/presentation/live/"},
        "integrity": {
            "no_hardcoded_answers": ("The agent path (scripts/local_agent.py, scripts/ask.py, "
                                     "scripts/run_presentation_scenarios.py, MCP server) has no "
                                     "question-to-answer mapping. Every final answer is the model's "
                                     "text, unedited."),
            "grader_only_reference_values": ("src/bist_analytics/harness/evaluation.py holds expected "
                                             "values used only to score harness experiments. The agent "
                                             "path never imports it; scripts/verify_submission.py "
                                             "checks this."),
            "figure_grounding": ("Each trace's grounding_audit lists every figure in the answer and "
                                 "the tool value it matches. Ungrounded figures are reported, never "
                                 "removed."),
            "label_thresholds": ("Labelling thresholds live in src/bist_analytics/strategy/label_rules.py "
                                 "and are returned inside tool outputs (label_rule), so any threshold "
                                 "the model cites is tool evidence."),
        },
        "code": code,
        "configs": configs,
        "reproduce": [
            "python -m venv .venv; .\\.venv\\Scripts\\python.exe -m pip install uv==0.12.15",
            ".\\.venv\\Scripts\\uv.exe sync --frozen --extra dev --python .\\.venv\\Scripts\\python.exe",
            "ollama create bist-qwen -f training/Modelfile.finetuned   # needs training/bist_lora.gguf",
            ".\\.venv\\Scripts\\python.exe scripts/build_rag_kb.py",
            ".\\.venv\\Scripts\\python.exe scripts/run_presentation_scenarios.py",
            ".\\.venv\\Scripts\\python.exe scripts/ask.py \"<live question>\"",
            ".\\.venv\\Scripts\\python.exe scripts/verify_submission.py",
        ],
        "attachments": attachments,
    }
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    missing = [a["path"] for a in attachments if a.get("status") == "MISSING"]
    print(json.dumps({"submission": OUT.relative_to(ROOT).as_posix(), "attachments": len(attachments),
                      "traces": len(traces), "missing": missing}, indent=2))


if __name__ == "__main__":
    main()
