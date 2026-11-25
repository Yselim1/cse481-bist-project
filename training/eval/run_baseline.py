r"""Run the 20-question baseline eval against the local LLM and score §30 metrics.

Outputs land at ``outputs/harness/baseline_local.score.json`` and per-question traces
under ``outputs/harness/baseline/``.

Usage (PowerShell):
    ollama serve   # in a separate terminal
    ollama pull qwen2.5:7b-instruct
    .\.venv\Scripts\python.exe training/eval/run_baseline.py
    .\.venv\Scripts\python.exe training/eval/run_baseline.py --model bist-qwen   # after Phase F
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.local_agent import (  # noqa: E402
    DEFAULT_MODEL,
    PRESENTATION_SYSTEM_PROMPT,
    PRESENTATION_TOOL_CHAR_CAP,
    SYSTEM_PROMPT,
    run_agent,
)

# "original": the protocol of the earlier evals (Ollama sends the 21 tool schemas, base system
#             prompt, 12 KB tool-result cap, no RAG), kept so results stay comparable.
# "presentation": the protocol of scripts/ask.py and the five scenario traces (no schemas,
#             <tool_call> text as in the fine-tuning data, presentation prompt, 4.5 KB cap, RAG).
PROTOCOLS = {
    "original": {"system_prompt": SYSTEM_PROMPT, "tool_schemas": True, "retrieval_top_k": 0},
    "presentation": {"system_prompt": PRESENTATION_SYSTEM_PROMPT, "tool_schemas": False,
                     "retrieval_top_k": 3, "tool_char_cap": PRESENTATION_TOOL_CHAR_CAP},
}


def _label_matches(expected: str | None, observed: str | None) -> bool:
    if expected is None or expected == "any":
        return True
    if observed is None:
        return False
    return observed in expected.split("|")


def _detect_label(final_answer: str) -> str | None:
    if not final_answer:
        return None
    labels = ("ANALYSIS_UNSAFE", "POTENTIAL_CATCH_UP_CANDIDATE", "TECHNICAL_REVERSAL_CANDIDATE",
              "FUNDAMENTAL_IMPROVEMENT_CANDIDATE", "REJECT_SIGNAL", "INVESTIGATE", "WATCH", "HOLD")
    for label in labels:
        if label in final_answer:
            return label
    return None


def _score(entries: list[dict]) -> dict:
    total = len(entries)
    if total == 0:
        return {"total": 0}
    invalid_tool = sum(e["invalid_tool_call"] for e in entries)
    missing_required = sum(e["missing_required_tools"] > 0 for e in entries)
    label_wrong = sum(not e["label_ok"] for e in entries)
    advice_leak = sum(e["advice_leak"] for e in entries)
    schema_bad = sum(e["unknown_label_emitted"] for e in entries)
    reproducible = sum(e["final_answer_len"] > 0 for e in entries)
    ungrounded = sum(e["ungrounded_figures"] > 0 for e in entries)
    unfinished = sum(e["max_turns_exceeded"] for e in entries)
    return {
        "total_questions": total,
        "invalid_tool_call_rate": invalid_tool / total,
        "missing_required_tool_rate": missing_required / total,
        "label_mismatch_rate": label_wrong / total,
        "advice_leak_rate": advice_leak / total,
        "unknown_label_emitted_rate": schema_bad / total,
        "reproducibility_rate": reproducible / total,
        "ungrounded_answer_rate": ungrounded / total,
        "max_turns_exceeded_rate": unfinished / total,
    }


ALLOWED_LABELS = {"HOLD", "WATCH", "INVESTIGATE", "POTENTIAL_CATCH_UP_CANDIDATE",
                  "TECHNICAL_REVERSAL_CANDIDATE", "FUNDAMENTAL_IMPROVEMENT_CANDIDATE",
                  "REJECT_SIGNAL", "ANALYSIS_UNSAFE"}
# Harness sentinels (not model-emitted labels) are excluded so the metric measures model
# quality, not loop-budget exhaustion.
HARNESS_SENTINELS = {"MAX_TURNS_EXCEEDED"}
_PUNCT = "\"'`:;()[]{}<>!?*"


def _unknown_label(final_answer: str, allowed: set[str] = ALLOWED_LABELS) -> bool:
    """True if the answer contains an UPPER_SNAKE token that is not one of the 8 labels.

    Tokens are stripped of surrounding punctuation first. (Until 2026-11-25 only commas and
    full stops were stripped, so a valid label written as "ANALYSIS_UNSAFE" in JSON quotes or
    followed by ';' or ':' was counted as unknown.) Tool vocabulary such as HARD_BLOCK or
    INVALID_SYMBOL still counts: the metric stays strict about non-label identifiers.
    """
    for raw in final_answer.replace(",", " ").replace(".", " ").split():
        token = raw.strip(_PUNCT)
        if (token.isupper() and "_" in token and token not in allowed
                and token not in HARNESS_SENTINELS and len(token) > 4):
            return True
    return False


def _final_answer_from_trace(path: Path) -> str:
    """Last assistant text in a saved .trace.jsonl (the final answer the agent returned)."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    texts = [r.get("content") or "" for r in rows if r.get("role") == "assistant"]
    return texts[-1] if texts else ""


def rescore(score_path: Path, trace_dir: Path) -> dict:
    """Recompute the text-based metrics of an existing score file from its saved traces."""
    summary = json.loads(score_path.read_text(encoding="utf-8"))
    for e in summary["entries"]:
        e["unknown_label_emitted"] = _unknown_label(_final_answer_from_trace(trace_dir/f"{e['id']}.trace.jsonl"))
    summary.update(_score(summary["entries"]))
    summary["rescored"] = "unknown_label_emitted recomputed from traces with the punctuation-stripping tokenizer"
    score_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rescore", action="store_true",
                        help="Recompute text-based metrics of --output from the traces in --trace-dir; no model calls.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS), default="original")
    parser.add_argument("--questions",
                        default=str(ROOT/"training/eval/baseline_questions.jsonl"))
    parser.add_argument("--output",
                        default=str(ROOT/"outputs/harness/baseline_local.score.json"))
    parser.add_argument("--trace-dir",
                        default=str(ROOT/"outputs/harness/baseline"))
    args = parser.parse_args()
    if args.rescore:
        s = rescore(Path(args.output), Path(args.trace_dir))
        print(json.dumps({k: v for k, v in s.items() if k.endswith("_rate")}, indent=2))
        return

    questions =[json.loads(line) for line in Path(args.questions).read_text(encoding="utf-8").splitlines() if line.strip()]
    trace_dir = Path(args.trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    advice_phrases = ("i recommend", "you should buy", "you should sell", "my advice",
                      "it is a good buy", "it is a good sell", "i would buy", "i would sell")
    allowed_labels = ALLOWED_LABELS

    entries: list[dict] = []
    for item in questions:
        qid = item["id"]
        trace_path = trace_dir/f"{qid}.trace.jsonl"
        result = run_agent(item["question"], model=args.model, max_turns=15, trace_path=trace_path,
                           **PROTOCOLS[args.protocol])
        trace = result.get("trace", [])
        tools_called = [entry["tool"] for entry in trace if entry.get("tool")]
        invalid = any(entry.get("result", {}).get("isError") or
                      (isinstance(entry.get("result"), dict) and "error" in entry["result"])
                      for entry in trace if entry.get("tool"))
        missing = sum(1 for t in item.get("expected_tools", []) if t not in tools_called)
        final_answer = result.get("final_answer", "") or ""
        label = _detect_label(final_answer)
        label_ok = _label_matches(item.get("expected_label"), label)
        lower = final_answer.lower()
        advice = any(phrase in lower for phrase in advice_phrases)
        unknown_label = _unknown_label(final_answer, allowed_labels)
        entries.append({
            "id": qid, "scenario": item.get("scenario"),
            "expected_tools": item.get("expected_tools", []),
            "tools_called": tools_called,
            "invalid_tool_call": invalid,
            "missing_required_tools": missing,
            "label_detected": label,
            "label_expected": item.get("expected_label"),
            "label_ok": label_ok,
            "advice_leak": advice,
            "unknown_label_emitted": unknown_label,
            "final_answer_len": len(final_answer),
            "turns_used": result.get("turns_used"),
            "ungrounded_figures": result["execution_trace"]["grounding_audit"]["ungrounded_count"],
            "max_turns_exceeded": final_answer.strip() == "MAX_TURNS_EXCEEDED",
            "wall_time_s": result["execution_trace"].get("wall_time_s"),
        })
        print(json.dumps({"id": qid, "tools": tools_called, "label": label,
                          "invalid_tool": invalid, "missing": missing}, default=str))

    summary = _score(entries)
    summary["model"] = args.model
    summary["protocol"] = args.protocol
    summary["protocol_settings"] = {k: (v if k != "system_prompt" else
                                        ("PRESENTATION_SYSTEM_PROMPT" if v == PRESENTATION_SYSTEM_PROMPT
                                         else "SYSTEM_PROMPT"))
                                    for k, v in PROTOCOLS[args.protocol].items()}
    summary["model_digest"] = entries and result["execution_trace"]["model"].get("digest")
    summary["entries"] = entries
    out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "entries"}, indent=2))


if __name__ == "__main__":
    main()
