"""Run five architecture stages with one fixed model and score the saved evidence.

Supports two backends:
  --backend codex    Original Codex CLI subprocess path (legacy / development).
  --backend ollama   Local Ollama + Qwen (or fine-tuned bist-qwen) via scripts/local_agent.py.
                     This is the submission path — no cloud traffic.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bist_analytics.harness.evaluation import score_answer  # noqa: E402
from bist_analytics.io import sha256, write_json  # noqa: E402

DEFAULT_CODEX_MODEL = "gpt-6-luna"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"
STAGES = ["raw_llm", "llm_tools", "stateful_harness", "evidence_quality_gate", "memory_human_review"]
QUESTION = (
    "As of 2026-09-25, explain THYAO's latest available trailing financial state, current rule signal, "
    "the full 2025-01-01 to 2026-09-26-exclusive strategy comparison, and the latest reviewed KAP context event. "
    "Return money in million TRY and returns as decimals. Missing evidence must be null."
)


def prompt_for(stage: str) -> str:
    common = (QUESTION + " This is educational research. Do not recommend buying or selling. Return only the schema object. "
              "Use exactly YYYY-MM-DD in as_of and financial_period, only BUY/SELL/HOLD in signal_action, and bare MCP tool names without a server prefix in evidence_tools.")
    if stage == "raw_llm":
        return common + " You have no tools or project evidence. Do not guess; use null for facts you cannot verify."
    tool_rule = (
        " Use only the bist MCP tools for project facts. Call get_fundamental_metrics, calculate_indicators, "
        "calculate_scores, generate_signal, run_backtest, and get_context_events. Put every tool used in evidence_tools."
    )
    if stage == "llm_tools":
        return common + tool_rule
    state = json.dumps({"as_of": "2026-09-25", "holding": False, "entry_price": 0, "holding_sessions": 0,
                        "evaluation_start": "2025-01-01", "evaluation_end_exclusive": "2026-09-26"})
    if stage == "stateful_harness":
        return common + tool_rule + " The harness supplies this immutable run state: " + state
    gate = (
        " The candidate will be rejected unless every requested number exactly matches tool evidence, all dates obey "
        "point-in-time availability, all cited tools were actually called, and limitations are stated."
    )
    if stage == "evidence_quality_gate":
        return common + tool_rule + " Immutable run state: " + state + gate
    memory = (ROOT/"data/harness/memory.json").read_text(encoding="utf-8")
    return common + tool_rule + " Immutable run state: " + state + gate + " Reviewed project memory: " + memory


# ---------- Codex CLI backend (legacy) -----------------------------------------------------

def _run_codex_stage(stage: str, args: argparse.Namespace, output: Path) -> tuple[dict, set[str]]:
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("Codex CLI is required for --backend codex")
    answer_path = output/f"{stage}.json"
    trace_path = output/f"{stage}.jsonl"
    error_path = output/f"{stage}.stderr.log"
    command = [codex, "exec", "--ignore-user-config", "--ephemeral", "--json", "--sandbox", "read-only",
               "--model", args.model, "-c", 'model_reasoning_effort="low"', "-C", str(ROOT),
               "--output-schema", str(ROOT/"data/harness/answer.schema.json"), "-o", str(answer_path)]
    if stage != "raw_llm":
        config_value = str((ROOT/"config/tms29.yaml").as_posix()).replace('"', '\\"')
        command += ["-c", "mcp_servers.bist.command="+json.dumps(str(Path(os.sys.executable).as_posix())),
                    "-c", 'mcp_servers.bist.args=["-m","bist_analytics.mcp.server"]',
                    "-c", 'mcp_servers.bist.env={BIST_CONFIG="'+config_value+'"}',
                    "-c", "mcp_servers.bist.required=true", "-c", "mcp_servers.bist.startup_timeout_sec=45",
                    "-c", "mcp_servers.bist.tool_timeout_sec=120"]
    command.append(prompt_for(stage))
    environment = os.environ.copy()
    environment["BIST_CONFIG"] = str(ROOT/"config/tms29.yaml")
    with trace_path.open("w", encoding="utf-8") as stdout, error_path.open("w", encoding="utf-8") as stderr:
        completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, timeout=600)
    if completed.returncode:
        raise SystemExit(f"{stage} failed; inspect {error_path}")
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.startswith("{")]
    calls = [event["item"] for event in events if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "mcp_tool_call"]
    called_tools = {call["tool"] for call in calls if call.get("status") == "completed" and not call.get("error")}
    return answer, called_tools


# ---------- Ollama backend (local, submission path) ----------------------------------------

def _run_ollama_stage(stage: str, args: argparse.Namespace, output: Path) -> tuple[dict, set[str]]:
    from scripts.local_agent import run_agent  # lazy import — only needed on this branch
    prompt = prompt_for(stage)
    schema_hint = (" Return your final answer as ONE JSON object matching data/harness/answer.schema.json "
                   "with keys: as_of, financial_period, revenue_try_million, net_profit_try_million, "
                   "net_debt_try_million, combined_return, technical_return, buy_hold_return, bist100_return, "
                   "signal_action, context_event_ids, evidence_tools, educational_caveat, "
                   "investment_recommendation, narrative. Any unknown field must be null.")
    full_prompt = prompt + schema_hint

    trace_path = output/f"{stage}.jsonl"
    answer_path = output/f"{stage}.json"
    error_path = output/f"{stage}.stderr.log"
    # raw_llm stage runs without any tool access; we still use run_agent but strip tool calls after the fact.
    allow_tools = stage != "raw_llm"
    result = run_agent(full_prompt, model=args.model, max_turns=12 if allow_tools else 1,
                       trace_path=trace_path, allow_tools=allow_tools)
    text = result.get("final_answer", "")
    answer = _extract_json(text)
    if answer is None:
        answer = {"as_of": None, "financial_period": None, "revenue_try_million": None,
                  "net_profit_try_million": None, "net_debt_try_million": None,
                  "combined_return": None, "technical_return": None, "buy_hold_return": None,
                  "bist100_return": None, "signal_action": None, "context_event_ids": [],
                  "evidence_tools": [], "educational_caveat": "", "investment_recommendation": None,
                  "narrative": text[:2000] if text else "parse_error"}
        error_path.write_text(f"Could not parse JSON from model output. Raw text:\n{text}\n",
                              encoding="utf-8")
    answer_path.write_text(json.dumps(answer, indent=2, default=str), encoding="utf-8")
    called_tools = {entry["tool"] for entry in result.get("trace", []) if entry.get("tool")}
    return answer, called_tools


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    # Strip markdown fences, if any.
    stripped = text.strip()
    for fence in ("```json", "```JSON", "```"):
        if stripped.startswith(fence):
            stripped = stripped[len(fence):].lstrip("\n")
        if stripped.endswith("```"):
            stripped = stripped[:-3].rstrip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Greedy JSON object extraction (first { to last }).
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start:end+1])
        except json.JSONDecodeError:
            return None
    return None


# ---------- Shared driver -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--backend", choices=["codex", "ollama"], default="ollama",
                        help="Which LLM backend to use. Ollama is the submission path.")
    parser.add_argument("--model", default=None,
                        help="Backend-specific model name. Defaults: codex→gpt-6-luna, ollama→qwen2.5:7b-instruct.")
    args = parser.parse_args()
    if args.model is None:
        args.model = DEFAULT_CODEX_MODEL if args.backend == "codex" else DEFAULT_OLLAMA_MODEL

    stages = [args.stage] if args.stage else STAGES
    output = ROOT/"outputs/harness"
    output.mkdir(parents=True, exist_ok=True)
    state_path = output/"state.json"
    state = ({"completed_stages": [], "runs": []} if not args.stage else
             json.loads(state_path.read_text()) if state_path.exists() else {"completed_stages": [], "runs": []})

    for stage in stages:
        if args.backend == "codex":
            answer, called_tools = _run_codex_stage(stage, args, output)
        else:
            answer, called_tools = _run_ollama_stage(stage, args, output)
        answer_path = output/f"{stage}.json"
        trace_path = output/f"{stage}.jsonl"
        score = score_answer(answer, called_tools)
        write_json(output/f"{stage}.score.json", score)
        state["completed_stages"] = list(dict.fromkeys(state["completed_stages"] + [stage]))
        state["runs"].append({"stage": stage, "backend": args.backend, "model": args.model,
                              "completed_at": datetime.now(timezone.utc).isoformat(),
                              "answer_sha256": sha256(answer_path),
                              "trace_sha256": sha256(trace_path) if trace_path.exists() else None,
                              "called_tools": sorted(called_tools), "quality_gate_pass": score["quality_gate_pass"]})
        write_json(state_path, state)

    rows = []
    for stage in STAGES:
        score_path = output/f"{stage}.score.json"
        if score_path.exists():
            rows.append({"stage": stage, **json.loads(score_path.read_text(encoding="utf-8"))})
    write_json(output/"comparison.json", {"backend": args.backend, "fixed_model": args.model,
                                           "question": QUESTION, "stages": rows,
        "interpretation": "Architecture comparison only; model identity is fixed and model quality is not the independent variable."})
    review = output/"human_review.json"
    if "memory_human_review" in stages:
        write_json(review, {"stage": "memory_human_review", "status": "pending_human_review",
            "candidate": "memory_human_review.json", "reviewer": "", "reviewed_at": "", "decision": "",
            "comments": "Review numerical evidence, clarity, limitations, and presentation suitability."})
    print(json.dumps({"backend": args.backend, "model": args.model, "completed": stages,
                      "comparison": str(output/"comparison.json"),
                      "human_review": str(review)}, indent=2))


if __name__ == "__main__":
    main()
