r"""Verify ``submission.json`` against the files on disk and the course rules.

    .\.venv\Scripts\python.exe scripts/verify_submission.py

Checks:
  1. every attachment exists and its SHA-256 matches;
  2. the LoRA adapter is present as safetensors, and its hash equals the hash recorded at
     training time (training/config/hyperparams.json);
  3. the base model name, version and download source are stated;
  4. there are exactly five execution traces. Each one has the required provenance fields,
     names the served model's digest, and passes the figure-grounding audit;
  5. the RAG knowledge base has source metadata on every document;
  6. no file on the agent path imports the grader's expected values.
Exits non-zero on any failure.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TRACE_FIELDS = ["model", "sampling", "system_prompt", "user_prompt", "steps",
                         "final_answer", "started_at", "finished_at", "grounding_audit"]
AGENT_PATH = ["scripts/local_agent.py", "scripts/ask.py", "scripts/run_presentation_scenarios.py",
              "src/bist_analytics/mcp/server.py", "src/bist_analytics/rag.py",
              "src/bist_analytics/harness/grounding.py"]


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


def main() -> int:
    manifest = json.loads((ROOT / "submission.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    warnings: list[str] = []

    for a in manifest["attachments"]:
        path = ROOT / a["path"]
        if a.get("status") == "MISSING" or not path.exists():
            failures.append(f"missing attachment: {a['path']} ({a['role']})")
        elif sha256(path) != a["sha256"]:
            failures.append(f"sha256 mismatch: {a['path']}")

    adapter = manifest["adapter"]
    if not adapter.get("path", "").endswith(".safetensors") or adapter.get("status") == "MISSING":
        failures.append("LoRA adapter safetensors missing")
    elif not adapter.get("matches_training_record"):
        failures.append("adapter sha256 does not match training/config/hyperparams.json")

    base = manifest["base_model"]
    for key in ("name", "version", "download_source"):
        if not base.get(key):
            failures.append(f"base_model.{key} missing")
    if not base.get("huggingface_revision"):
        warnings.append("base_model.huggingface_revision unknown (filled in from the training run record)")

    served_digest = manifest["served_model"].get("digest")
    traces = manifest["execution_traces"]["items"]
    if len(traces) != 5:
        failures.append(f"expected 5 execution traces, found {len(traces)}")
    for item in traces:
        path = ROOT / item["path"]
        if not path.exists():
            continue
        t = json.loads(path.read_text(encoding="utf-8"))
        absent = [f for f in REQUIRED_TRACE_FIELDS if f not in t or t[f] in (None, "")]
        if absent:
            failures.append(f"{item['path']}: missing fields {absent}")
        if t["sampling"].get("seed") is None or t["sampling"].get("temperature") is None:
            failures.append(f"{item['path']}: seed/temperature not recorded")
        if not t["model"].get("digest"):
            failures.append(f"{item['path']}: model digest not recorded")
        elif served_digest and t["model"]["digest"] != served_digest:
            failures.append(f"{item['path']}: produced by digest {t['model']['digest'][:12]}, "
                            f"served model is {served_digest[:12]}; re-run the scenarios")
        if not t["grounding_audit"]["all_grounded"]:
            failures.append(f"{item['path']}: ungrounded figures "
                            f"{[f['text'] for f in t['grounding_audit']['ungrounded']]}")
        for step in t["steps"]:
            if step["type"] == "tool_call" and "arguments" not in step:
                failures.append(f"{item['path']}: tool step without arguments")

    kb = json.loads((ROOT / "rag/knowledge_base.json").read_text(encoding="utf-8"))
    for doc in kb["documents"]:
        if not (doc.get("source_path") or doc.get("source_url")) or not doc.get("sha256"):
            failures.append(f"KB document without source metadata: {doc['doc_id']}")

    for rel in AGENT_PATH:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if re.search(r"harness\.evaluation|from .*evaluation import|EXPECTED\b", text):
            failures.append(f"{rel} references the grader's expected values")

    for w in warnings:
        print(f"WARN  {w}")
    for f in failures:
        print(f"FAIL  {f}")
    if not failures:
        print(f"OK    {len(manifest['attachments'])} attachments verified; 5 traces grounded; "
              f"adapter {adapter['sha256'][:16]}…")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
