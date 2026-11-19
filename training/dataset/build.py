r"""Generate the ~400-example fine-tuning dataset by calling the live MCP server.

Produces ChatML-formatted conversations with Qwen 2.5 tool-call syntax. Every example is
grounded in real tool outputs — no synthetic numerics. Discarded examples (MCP failure,
missing data) are logged to ``audit.json`` so we can report rejection rate.

Outputs:
    training/dataset/train.jsonl   (80 % stratified by scenario)
    training/dataset/eval.jsonl    (20 %)
    training/dataset/audit.json    (generation + rejection stats)

Usage:
    .\.venv\Scripts\python.exe training/dataset/build.py
    .\.venv\Scripts\python.exe training/dataset/build.py --target 400 --seed 17
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.local_agent import MCPStdioClient  # noqa: E402

SCENARIO_TARGETS = {
    "sector_lag": 100,
    "weekday": 60,
    "reversal": 120,
    "fundamental": 24,  # THYAO-only × 6 dates × 4 metric variants
    "analysis_unsafe": 96,
}

# Fundamental tool only has data for THYAO (Fintables TMS29 observations).
SCENARIO_TICKERS: dict[str, list[str]] = {"fundamental": ["THYAO.IS"]}

FUND_METRICS = ["net_profit_qoq", "revenue_qoq", "operating_profit_qoq", "ebitda_qoq"]
FUND_METRIC_LABELS = {"net_profit_qoq": "net profit", "revenue_qoq": "revenue",
                       "operating_profit_qoq": "operating profit", "ebitda_qoq": "EBITDA"}

UNIVERSE = ["THYAO.IS", "PGSUS.IS", "AKBNK.IS", "GARAN.IS", "EREGL.IS",
             "KRDMD.IS", "BIMAS.IS", "MGROS.IS", "TCELL.IS", "TTKOM.IS"]
SECTORS = {"THYAO.IS": "airlines", "PGSUS.IS": "airlines", "AKBNK.IS": "banking",
           "GARAN.IS": "banking", "EREGL.IS": "steel", "KRDMD.IS": "steel",
           "BIMAS.IS": "retail", "MGROS.IS": "retail", "TCELL.IS": "telecom",
           "TTKOM.IS": "telecom"}
AS_OF_DATES = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
               "2026-03-31", "2026-06-30", "2026-09-26"]

SYSTEM = (
    "You are an academic BIST financial-analysis agent. For every claim, call a tool first: "
    "you must never invent numbers. Allowed labels are the 8 educational labels "
    "(HOLD, WATCH, INVESTIGATE, POTENTIAL_CATCH_UP_CANDIDATE, TECHNICAL_REVERSAL_CANDIDATE, "
    "FUNDAMENTAL_IMPROVEMENT_CANDIDATE, REJECT_SIGNAL, ANALYSIS_UNSAFE). When evidence is "
    "insufficient, choose INVESTIGATE or ANALYSIS_UNSAFE. Cite tool names in your reasoning. "
    "Do not give investment advice. Numeric values must come from committed_evidence entries."
)


def _mcp_call(mcp: MCPStdioClient, name: str, arguments: dict) -> dict | None:
    try:
        return mcp.call_tool(name, arguments)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _trim(payload: Any, limit: int = 2500) -> Any:
    text = json.dumps(payload, default=str)
    if len(text) <= limit:
        return payload
    return text[:limit] + " ...[truncated]"


def _tool_message(tool_name: str, args: dict, result: Any) -> list[dict]:
    """ChatML tool-call + tool-result pair (Qwen 2.5 format)."""
    return [
        {"role": "assistant", "content": f"<tool_call>\n{json.dumps({'name': tool_name, 'arguments': args})}\n</tool_call>"},
        {"role": "tool", "name": tool_name,
         "content": json.dumps(_trim(result), default=str) if not isinstance(_trim(result), str) else _trim(result)},
    ]


def _assistant_finalize(label: str, explanation: str, evidence_ids: list[str]) -> dict:
    payload = {"educational_label": label, "committed_evidence_ids": evidence_ids,
                "explanation": explanation}
    content = "<final_answer>\n" + json.dumps(payload) + "\n</final_answer>"
    return {"role": "assistant", "content": content}


def _unwrap(result: Any) -> Any:
    """MCP envelope → inner structured payload (handles both direct-dict and MCP wire forms)."""
    if not isinstance(result, dict):
        return result
    if "structuredContent" in result:
        inner = result["structuredContent"]
    elif "content" in result and isinstance(result["content"], list):
        try:
            inner = json.loads(result["content"][0]["text"])
        except (KeyError, json.JSONDecodeError, TypeError):
            return result
    else:
        inner = result
    if isinstance(inner, dict) and "data" in inner:
        return inner["data"]
    return inner


def _is_error(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if "error" in result:
        return True
    if result.get("isError"):
        return True
    if isinstance(result.get("content"), list):
        for item in result["content"]:
            if isinstance(item, dict) and "Error" in item.get("text", ""):
                return True
    return False


# ---------- Scenario builders --------------------------------------------------------------

SECTOR_LAG_LOOKBACKS = [21, 42, 63, 126]


def build_sector_lag_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    lookback = random.choice(SECTOR_LAG_LOOKBACKS)
    args = {"as_of": as_of, "lookback": lookback}
    result = _mcp_call(mcp, "rank_sector_relative_strength", args)
    if not result or _is_error(result):
        return None
    rows = _unwrap(result)
    if not isinstance(rows, list):
        return None
    row = next((r for r in rows if r.get("ticker") == ticker), None)
    if row is None:
        return None
    rel = row.get("relative_vs_sector")
    rank = row.get("sector_rank")
    sector = row.get("sector")
    if rel is None:
        return None
    if rel < -0.05:
        label = "POTENTIAL_CATCH_UP_CANDIDATE"
    elif rel > 0.05:
        label = "WATCH"
    else:
        label = "HOLD"
    question = (f"Over the last {lookback} trading days ending {as_of}, is {ticker} lagging its "
                f"sector? Call rank_sector_relative_strength with lookback={lookback}, commit the "
                f"evidence, pick one educational label.")
    evidence_id = f"rank_sector_relative_strength:{ticker}:{as_of}:lb{lookback}"
    explanation = (f"{ticker} sits in the {sector} sector with {lookback}-session relative return "
                   f"{rel:.4f} vs peers (rank {rank}). Below -5% peer-relative → "
                   f"POTENTIAL_CATCH_UP_CANDIDATE; above +5% → WATCH; otherwise HOLD. Selected: {label}.")
    messages = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": question}]
    messages += _tool_message("rank_sector_relative_strength", args, result)
    messages.append(_assistant_finalize(label, explanation, [evidence_id]))
    return {"scenario": "sector_lag", "messages": messages, "variant": f"lb{lookback}",
            "label": label, "ticker": ticker, "as_of": as_of}


WEEKDAY_STARTS = ["2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01"]


def build_weekday_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    start = random.choice(WEEKDAY_STARTS)
    if start >= as_of:
        return None
    args = {"ticker": ticker, "start": start, "end": as_of}
    result = _mcp_call(mcp, "test_weekday_pattern", args)
    if not result or _is_error(result):
        return None
    rows = _unwrap(result)
    if not isinstance(rows, list) or not rows:
        return None
    weakest = min(rows, key=lambda r: r.get("mean") if r.get("mean") is not None else 1.0)
    weekday = weakest.get("weekday")
    p_val = weakest.get("p_value_uncorrected")
    mean = weakest.get("mean")
    count = weakest.get("count")
    if mean is None:
        return None
    significant = p_val is not None and p_val < 0.10
    label = "INVESTIGATE" if significant else "WATCH"
    question = (f"For {ticker} between {start} and {as_of}, call test_weekday_pattern. "
                f"Commit the weakest-weekday evidence, pick an educational label, and note "
                f"the multiple-testing caveat.")
    evidence_id = f"test_weekday_pattern:{ticker}:{start}:{as_of}:{weekday}"
    p_text = f"{p_val:.3f}" if p_val is not None else "n/a"
    explanation = (f"{weekday} is the weakest weekday ({count} obs, mean {mean:.4f}, "
                   f"uncorrected p={p_text}). 5 weekdays tested → Bonferroni-adjusted "
                   f"significance needs p<0.01, so without stronger evidence we stay at {label}.")
    messages = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": question}]
    messages += _tool_message("test_weekday_pattern", args, result)
    messages.append(_assistant_finalize(label, explanation, [evidence_id]))
    return {"scenario": "weekday", "messages": messages, "variant": start,
            "label": label, "ticker": ticker, "as_of": as_of}


REVERSAL_LOOKBACKS = [90, 180, 252]


def build_reversal_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    lookback = random.choice(REVERSAL_LOOKBACKS)
    args = {"ticker": ticker, "as_of": as_of, "lookback": lookback}
    result = _mcp_call(mcp, "detect_reversal_events", args)
    if not result or _is_error(result):
        return None
    events = _unwrap(result)
    if not isinstance(events, list) or not events:
        return None
    # Aggregate forward_5d by event_type.
    by_type: dict[str, list[float]] = {}
    for event in events:
        et = event.get("event_type")
        fwd = event.get("forward_5d")
        if et and fwd is not None:
            by_type.setdefault(et, []).append(fwd)
    if not by_type:
        return None
    summary = [(et, sum(xs) / len(xs), len(xs)) for et, xs in by_type.items() if len(xs) >= 2]
    if not summary:
        return None
    summary.sort(key=lambda x: x[1], reverse=True)
    best_type, best_mean, best_count = summary[0]
    label = "TECHNICAL_REVERSAL_CANDIDATE" if best_mean > 0.005 else "WATCH"
    question = (f"For {ticker} as of {as_of} with lookback {lookback} days, call "
                f"detect_reversal_events. Compare event-family forward-5d returns, commit the "
                f"strongest signal, pick a label.")
    evidence_id = f"detect_reversal_events:{ticker}:{as_of}:lb{lookback}:{best_type}"
    explanation = (f"Strongest event family in-sample: {best_type} with {best_count} occurrences "
                   f"and mean forward-5d return {best_mean:.4f}. >0.5% → "
                   f"TECHNICAL_REVERSAL_CANDIDATE; otherwise WATCH. Selected {label}. "
                   f"Note: in-sample strength only; no live trading signal.")
    messages = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": question}]
    messages += _tool_message("detect_reversal_events", args, result)
    messages.append(_assistant_finalize(label, explanation, [evidence_id]))
    return {"scenario": "reversal", "messages": messages, "variant": f"lb{lookback}",
            "label": label, "ticker": ticker, "as_of": as_of}


def build_fundamental_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    args = {"ticker": ticker, "as_of": as_of}
    result = _mcp_call(mcp, "calculate_fundamental_change", args)
    if not result or _is_error(result):
        return None
    data = _unwrap(result)
    if not isinstance(data, dict):
        return None
    metric = random.choice(FUND_METRICS)
    value = data.get(metric)
    if value is None:
        return None
    rev_qoq = data.get("revenue_qoq") or 0.0
    label_name = FUND_METRIC_LABELS[metric]
    if metric == "net_profit_qoq":
        if value > 0.10 and rev_qoq > 0:
            label = "FUNDAMENTAL_IMPROVEMENT_CANDIDATE"
        elif value < -0.10:
            label = "REJECT_SIGNAL"
        else:
            label = "WATCH"
    else:
        if value > 0.10:
            label = "FUNDAMENTAL_IMPROVEMENT_CANDIDATE"
        elif value < -0.10:
            label = "REJECT_SIGNAL"
        else:
            label = "WATCH"
    question = (f"For {ticker} as of {as_of}, call calculate_fundamental_change. Focus on the "
                f"quarter-over-quarter {label_name} change and pick an educational label.")
    evidence_id = f"calculate_fundamental_change:{ticker}:{as_of}:{metric}"
    explanation = (f"Primary metric: QoQ {label_name} change = {value:+.3f}. "
                   f"Thresholds: >+10% → FUNDAMENTAL_IMPROVEMENT_CANDIDATE (net_profit also "
                   f"requires positive revenue); <-10% → REJECT_SIGNAL; else WATCH. "
                   f"Selected: {label}.")
    messages = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": question}]
    messages += _tool_message("calculate_fundamental_change", args, result)
    messages.append(_assistant_finalize(label, explanation, [evidence_id]))
    return {"scenario": "fundamental", "messages": messages, "variant": metric,
            "label": label, "ticker": ticker, "as_of": as_of}


def build_analysis_unsafe_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    pattern = random.choice(["future_date", "bad_ticker", "incomplete"])
    if pattern == "future_date":
        bogus_as_of = "2030-01-01"
        bundle_args = {"ticker": ticker, "as_of": bogus_as_of, "educational_label": "ANALYSIS_UNSAFE"}
        bundle = _mcp_call(mcp, "build_evidence_bundle", bundle_args)
        gate_args = {"ticker": ticker, "as_of": bogus_as_of}
        gate = _mcp_call(mcp, "check_data_quality", gate_args)
        if bundle is None or gate is None:
            return None
        question = (f"Analyze {ticker} as of {bogus_as_of}. Call build_evidence_bundle and "
                    f"check_data_quality. Commit the gate decision.")
        explanation = (f"{bogus_as_of} is in the future; the evidence-bundle call fails with "
                       f"DATE_OUT_OF_SNAPSHOT and the gate hard-blocks on FUTURE_STATEMENT. "
                       f"Label is ANALYSIS_UNSAFE — no numeric claim is permitted.")
        tool_sequence = [("build_evidence_bundle", bundle_args, bundle),
                         ("check_data_quality", gate_args, gate)]
        label = "ANALYSIS_UNSAFE"
    elif pattern == "bad_ticker":
        bogus_ticker = "ZZZ.IS"
        ind_args = {"ticker": bogus_ticker, "as_of": as_of}
        indicators = _mcp_call(mcp, "calculate_indicators", ind_args)
        gate_args = {"ticker": bogus_ticker, "as_of": as_of}
        gate = _mcp_call(mcp, "check_data_quality", gate_args)
        if indicators is None or gate is None:
            return None
        question = (f"Analyze {bogus_ticker} as of {as_of}. Call calculate_indicators and "
                    f"check_data_quality. The ticker is not in the universe.")
        explanation = (f"{bogus_ticker} is not in the universe cache. Indicators tool errors; "
                       f"gate escalates to ANALYSIS_UNSAFE. No numeric claims.")
        tool_sequence = [("calculate_indicators", ind_args, indicators),
                         ("check_data_quality", gate_args, gate)]
        label = "ANALYSIS_UNSAFE"
    else:  # incomplete
        ind_args = {"ticker": ticker, "as_of": as_of}
        indicators = _mcp_call(mcp, "calculate_indicators", ind_args)
        if indicators is None or _is_error(indicators):
            return None
        gate_args = {"ticker": ticker, "as_of": as_of}
        gate = _mcp_call(mcp, "check_data_quality", gate_args)
        if gate is None:
            return None
        question = (f"Analyze {ticker} as of {as_of} but only call calculate_indicators (no "
                    f"scores, no backtest). Then call check_data_quality.")
        explanation = ("Required tools calculate_scores and run_backtest were not called. "
                       "Gate escalates to INVESTIGATE. No numeric claims beyond calculate_indicators.")
        tool_sequence = [("calculate_indicators", ind_args, indicators),
                         ("check_data_quality", gate_args, gate)]
        label = "INVESTIGATE"

    evidence_ids = [f"{name}:{args.get('ticker', ticker)}:{args.get('as_of', as_of)}"
                     for name, args, _ in tool_sequence]
    messages = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": question}]
    for name, args, result in tool_sequence:
        messages += _tool_message(name, args, result)
    messages.append(_assistant_finalize(label, explanation, evidence_ids))
    return {"scenario": "analysis_unsafe", "messages": messages, "variant": pattern,
            "label": label, "ticker": ticker, "as_of": as_of}


BUILDERS = {
    "sector_lag": build_sector_lag_example,
    "weekday": build_weekday_example,
    "reversal": build_reversal_example,
    "fundamental": build_fundamental_example,
    "analysis_unsafe": build_analysis_unsafe_example,
}


def _is_duplicate(example: dict, pool: list[dict]) -> bool:
    for existing in pool:
        if (existing["scenario"] == example["scenario"]
                and existing["ticker"] == example["ticker"]
                and existing["as_of"] == example["as_of"]
                and existing.get("variant") == example.get("variant")):
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=400)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--train-out", default=str(ROOT/"training/dataset/train.jsonl"))
    parser.add_argument("--eval-out", default=str(ROOT/"training/dataset/eval.jsonl"))
    parser.add_argument("--audit", default=str(ROOT/"training/dataset/audit.json"))
    parser.add_argument("--max-attempts-factor", type=int, default=6,
                        help="Attempts per scenario = target × this factor")
    args = parser.parse_args()
    random.seed(args.seed)

    scale = args.target / sum(SCENARIO_TARGETS.values())
    targets = {k: max(1, int(round(v * scale))) for k, v in SCENARIO_TARGETS.items()}

    mcp = MCPStdioClient([sys.executable, "-m", "bist_analytics.mcp.server"],
                          env={"BIST_CONFIG": str(ROOT/"config/universe10.yaml")})
    examples: list[dict] = []
    rejects = {k: 0 for k in SCENARIO_TARGETS}
    started = time.time()
    try:
        for scenario, target in targets.items():
            builder = BUILDERS[scenario]
            candidates = SCENARIO_TICKERS.get(scenario, UNIVERSE)
            attempts = 0
            while (sum(1 for e in examples if e["scenario"] == scenario) < target
                   and attempts < target * args.max_attempts_factor):
                attempts += 1
                ticker = random.choice(candidates)
                as_of = random.choice(AS_OF_DATES)
                example = builder(mcp, ticker, as_of)
                if example is None or _is_duplicate(example, examples):
                    rejects[scenario] += 1
                    continue
                examples.append(example)
            print(f"[{scenario}] built {sum(1 for e in examples if e['scenario'] == scenario)}/"
                   f"{target} in {attempts} attempts ({rejects[scenario]} rejected)")
    finally:
        mcp.close()

    random.shuffle(examples)
    train: list[dict] = []
    eval_: list[dict] = []
    by_scenario: dict[str, list[dict]] = {}
    for ex in examples:
        by_scenario.setdefault(ex["scenario"], []).append(ex)
    for scenario, items in by_scenario.items():
        cut = max(1, int(round(len(items) * 0.2)))
        eval_.extend(items[:cut])
        train.extend(items[cut:])

    Path(args.train_out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.train_out).open("w", encoding="utf-8") as fh:
        for ex in train:
            fh.write(json.dumps(ex, default=str) + "\n")
    with Path(args.eval_out).open("w", encoding="utf-8") as fh:
        for ex in eval_:
            fh.write(json.dumps(ex, default=str) + "\n")

    audit = {
        "target": args.target,
        "scenarios_target": targets,
        "scenarios_built": {k: sum(1 for e in examples if e["scenario"] == k) for k in targets},
        "rejections": rejects,
        "train_count": len(train), "eval_count": len(eval_),
        "seed": args.seed, "elapsed_seconds": round(time.time() - started, 1),
    }
    Path(args.audit).write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
