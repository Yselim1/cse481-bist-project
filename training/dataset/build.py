r"""Generate the ~400-example fine-tuning dataset by calling the live MCP server.

Produces ChatML-formatted conversations with Qwen 2.5 tool-call syntax. Every example is
grounded in real tool outputs — no synthetic numerics. Discarded examples (MCP failure,
missing data) are logged to ``audit.json`` so we can report rejection rate.

Dataset v2 (2026-11-25) — rebuilt for the presentation rules ("no figure that is not in a
tool output"):
* every figure in an assistant answer is copied from the tool result shown in the same
  conversation: label thresholds come from the tool's ``label_rule`` block, reversal
  averages from the tool's ``summary`` block (both placed before ``data`` so the 2,500-char
  training trim never cuts them);
* labels are decided by ``bist_analytics.strategy.label_rules``, the same module the tools
  return their rules from;
* about half the questions are phrased naturally without naming a tool, use the
  presentation system prompt, and carry the same knowledge-base context block that
  ``scripts/local_agent.py`` injects at inference time;
* new analysis_unsafe patterns: varied future dates, varied unknown tickers, and
  "fundamentals unavailable" for tickers outside the fundamentals dataset.

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
import hashlib
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for extra in (ROOT, ROOT / "src"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from bist_analytics.strategy import label_rules  # noqa: E402
from scripts.local_agent import (  # noqa: E402
    PRESENTATION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    MCPStdioClient,
    _format_reference_context,
    _retrieval_args,
    _truncate_tool_result,
    model_view,
)

DATASET_VERSION = 2
SCENARIO_TARGETS = {
    "sector_lag": 100,
    "weekday": 60,
    "reversal": 110,
    "fundamental": 34,  # THYAO-only (the fundamentals dataset covers THYAO alone)
    "analysis_unsafe": 96,
}
NATURAL_SHARE = 0.5
RAG_TOP_K = 3

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
FUTURE_DATES = ["2026-12-31", "2027-03-31", "2027-06-30", "2028-01-15", "2030-01-01"]
UNKNOWN_TICKERS = ["ZZZ.IS", "ABCDE.IS", "QWRTY.IS", "XYZ.IS"]

# Kept for the tool-named half of the dataset (identical to the eval-baseline prompt).
SYSTEM = SYSTEM_PROMPT

# Natural phrasings: no tool names. {placeholders} are filled from the example.
NATURAL = {
    "sector_lag_ticker": [
        "Is {ticker} lagging its sector over the last {lookback} trading sessions up to {as_of}? Give one educational label.",
        "How has {ticker} performed relative to its sector peers in the {lookback} sessions ending {as_of}?",
        "As of {as_of}, is {ticker} a catch-up candidate versus its sector ({lookback}-session window)?",
        "{as_of} itibarıyla son {lookback} işlem gününde {ticker} sektörünün gerisinde mi kaldı?",
    ],
    "sector_lag_sector": [
        "As of {as_of}, which stock in the {sector} sector has lagged its sector the most over the last {lookback} trading sessions? Give one educational label.",
        "Within the {sector} sector, who is the laggard over the {lookback} sessions ending {as_of}, and could it catch up?",
        "{as_of} tarihinde {sector} sektöründe son {lookback} işlem gününde en çok geride kalan hisse hangisi?",
    ],
    "weekday": [
        "Using {ticker} daily returns from {start} to {as_of}, is there a day-of-the-week effect?",
        "Does {ticker} show a weekday pattern in returns between {start} and {as_of}? Which day is weakest, and is it significant?",
        "{ticker} için {start} ile {as_of} arasında haftanın günü etkisi var mı?",
    ],
    "reversal": [
        "Which technical reversal signals appeared for {ticker} in the {lookback} sessions up to {as_of}, and how did the price behave over the next 5 sessions?",
        "For {ticker} as of {as_of}, look back {lookback} sessions: which turning-point events occurred and which family had the best forward 5-day return?",
        "{ticker} hissesinde {as_of} öncesi son {lookback} seansta hangi dönüş sinyalleri oluştu?",
    ],
    "fundamental": [
        "As of {as_of}, how did {ticker}'s {metric_name} change compared with the previous quarter, and when were the latest statements published?",
        "Did {ticker}'s {metric_name} improve quarter over quarter as of {as_of}? Give one educational label.",
        "{as_of} itibarıyla {ticker} {metric_name} bir önceki çeyreğe göre nasıl değişti?",
    ],
    "future_date": [
        "Is {ticker} a fundamental improvement candidate as of {as_of}? Give one educational label.",
        "Analyze {ticker} as of {as_of} and give one educational label.",
        "{ticker} için {as_of} tarihli bir analiz yap ve bir eğitim etiketi seç.",
    ],
    "bad_ticker": [
        "Analyze {ticker} as of {as_of}. Is it a technical reversal candidate?",
        "What is the technical state of {ticker} on {as_of}? Give one educational label.",
    ],
    "no_fundamentals": [
        "As of {as_of}, did {ticker}'s net profit improve versus the previous quarter? Give one educational label.",
        "Is {ticker} a fundamental improvement candidate as of {as_of}?",
    ],
}

# Tool text in training is trimmed tighter than at inference (12 KB) to fit max_seq_length;
# label_rule/summary sit before `data`, so they always survive the trim.
TRAIN_TOOL_CHAR_CAP = 3000


def _mcp_call(mcp: MCPStdioClient, name: str, arguments: dict) -> dict | None:
    try:
        return mcp.call_tool(name, arguments)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _tool_message(tool_name: str, args: dict, result: Any) -> list[dict]:
    """ChatML tool-call + tool-result pair (Qwen 2.5 format), using the inference model view."""
    return [
        {"role": "assistant", "content": f"<tool_call>\n{json.dumps({'name': tool_name, 'arguments': args})}\n</tool_call>"},
        {"role": "tool", "name": tool_name,
         "content": _truncate_tool_result(model_view(result), TRAIN_TOOL_CHAR_CAP)},
    ]


def _assistant_finalize(label: str, explanation: str, evidence_ids: list[str]) -> dict:
    payload = {"educational_label": label, "committed_evidence_ids": evidence_ids,
               "explanation": explanation}
    content = "<final_answer>\n" + json.dumps(payload, ensure_ascii=False) + "\n</final_answer>"
    return {"role": "assistant", "content": content}


def _structured(result: Any) -> dict:
    if isinstance(result, dict) and isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        try:
            return json.loads(result["content"][0]["text"])
        except (KeyError, IndexError, json.JSONDecodeError, TypeError):
            return {}
    return result if isinstance(result, dict) else {}


def _unwrap(result: Any) -> Any:
    """MCP envelope → inner ``data`` payload."""
    inner = _structured(result)
    return inner.get("data", inner) if isinstance(inner, dict) else inner


def _is_error(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if "error" in result or result.get("isError"):
        return True
    if isinstance(result.get("content"), list):
        for item in result["content"]:
            if isinstance(item, dict) and "Error" in item.get("text", ""):
                return True
    return False


def _opening(mcp: MCPStdioClient, natural: bool, question: str) -> list[dict]:
    """System + user messages. Natural questions mirror inference exactly: presentation
    system prompt + the knowledge-base context block local_agent.py injects."""
    if not natural:
        return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    user = question
    context = _format_reference_context(_mcp_call(mcp, "search_knowledge_base",
                                                  _retrieval_args(question, RAG_TOP_K)))
    if context:
        user = f"{question}\n\n{context}"
    return [{"role": "system", "content": PRESENTATION_SYSTEM_PROMPT},
            {"role": "user", "content": user}]


def _natural(key: str, **fields: Any) -> str:
    return random.choice(NATURAL[key]).format(**fields)


def _f(x: float, nd: int = 4) -> str:
    return f"{x:.{nd}f}"


def _p(p: float) -> str:
    """p-value with >= 2 significant digits (0.367, 0.0091), never scientific notation."""
    import math
    decimals = 3 if p >= 0.01 or p <= 0 else max(3, 1 - math.floor(math.log10(p)))
    return f"{p:.{decimals}f}"


# ---------- Scenario builders --------------------------------------------------------------

SECTOR_LAG_LOOKBACKS = [21, 42, 63, 126]


def build_sector_lag_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    lookback = random.choice(SECTOR_LAG_LOOKBACKS)
    natural = random.random() < NATURAL_SHARE
    sector_question = natural and random.random() < 0.5
    args = {"as_of": as_of, "lookback": lookback}
    result = _mcp_call(mcp, "rank_sector_relative_strength", args)
    if not result or _is_error(result):
        return None
    rows = _unwrap(result)
    if not isinstance(rows, list):
        return None
    rule = label_rules.SECTOR_RULE
    rule_text = (f"label_rule: relative_vs_sector < {rule['catch_up_below']} → POTENTIAL_CATCH_UP_CANDIDATE; "
                 f"> {rule['watch_above']} → WATCH; otherwise HOLD.")
    if sector_question:
        sector = SECTORS[ticker]
        members = [r for r in rows if r.get("sector") == sector and r.get("relative_vs_sector") is not None]
        if len(members) < 2:
            return None
        laggard = min(members, key=lambda r: r["relative_vs_sector"])
        ticker = laggard["ticker"]
        label = label_rules.sector_label(laggard["relative_vs_sector"])
        question = _natural("sector_lag_sector", sector=sector, lookback=lookback, as_of=as_of)
        peers = "; ".join(f"{r['ticker']} cum_return {_f(r['cum_return'])}, relative_vs_sector "
                          f"{_f(r['relative_vs_sector'])}" for r in members)
        explanation = (f"rank_sector_relative_strength ({lookback} sessions to {as_of}), {sector} "
                       f"sector mean {_f(laggard['sector_mean'])}: {peers}. The laggard is {ticker} "
                       f"at {_f(laggard['relative_vs_sector'])}. {rule_text} Selected: {label}.")
        variant = f"sector-{sector}-lb{lookback}"
    else:
        row = next((r for r in rows if r.get("ticker") == ticker), None)
        if row is None or row.get("relative_vs_sector") is None:
            return None
        rel = row["relative_vs_sector"]
        label = label_rules.sector_label(rel)
        if natural:
            question = _natural("sector_lag_ticker", ticker=ticker, lookback=lookback, as_of=as_of)
        else:
            question = (f"Over the last {lookback} trading days ending {as_of}, is {ticker} lagging its "
                        f"sector? Call rank_sector_relative_strength with lookback={lookback}, commit the "
                        f"evidence, pick one educational label.")
        explanation = (f"rank_sector_relative_strength ({lookback} sessions to {as_of}): {ticker} "
                       f"({row.get('sector')}) cum_return {_f(row['cum_return'])} vs sector_mean "
                       f"{_f(row['sector_mean'])}, relative_vs_sector {_f(rel)}, sector_rank "
                       f"{row.get('sector_rank'):g}. {rule_text} Selected: {label}.")
        variant = f"lb{lookback}"
    evidence_id = f"rank_sector_relative_strength:{ticker}:{as_of}:lb{lookback}"
    messages = _opening(mcp, natural, question)
    messages += _tool_message("rank_sector_relative_strength", args, result)
    messages.append(_assistant_finalize(label, explanation, [evidence_id]))
    return {"scenario": "sector_lag", "messages": messages, "variant": variant,
            "label": label, "ticker": ticker, "as_of": as_of, "natural": natural}


WEEKDAY_STARTS = ["2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01"]


def build_weekday_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    start = random.choice(WEEKDAY_STARTS)
    if start >= as_of:
        return None
    natural = random.random() < NATURAL_SHARE
    args = {"ticker": ticker, "start": start, "end": as_of}
    result = _mcp_call(mcp, "test_weekday_pattern", args)
    if not result or _is_error(result):
        return None
    rows = [r for r in (_unwrap(result) or []) if isinstance(r, dict) and r.get("mean") is not None]
    if len(rows) < 2:
        return None
    weakest = min(rows, key=lambda r: r["mean"])
    strongest = max(rows, key=lambda r: r["mean"])
    p_values = [r["p_value_uncorrected"] for r in rows if r.get("p_value_uncorrected") is not None]
    p_min = min(p_values) if p_values else None
    label = label_rules.weekday_label(p_min)
    rule = label_rules.WEEKDAY_RULE

    def describe(r: dict) -> str:
        p = r.get("p_value_uncorrected")
        return (f"{r['weekday']} mean {_f(r['mean'])} (n={r['count']}, uncorrected p="
                f"{_p(p) if p is not None else 'n/a'})")

    if p_min is None:
        verdict = "No p-values were available."
    elif p_min < rule["bonferroni_p_threshold"]:
        verdict = (f"The smallest uncorrected p is {_p(p_min)}, below the Bonferroni threshold "
                   f"{rule['bonferroni_p_threshold']} for {rule['weekdays_tested']} weekdays.")
    elif p_min < rule["screen_p_value"]:
        verdict = (f"The smallest uncorrected p is {_p(p_min)}: below the {rule['screen_p_value']} "
                   f"screen but not below the Bonferroni threshold {rule['bonferroni_p_threshold']} for "
                   f"{rule['weekdays_tested']} weekdays, so it is not significant after correction.")
    else:
        verdict = (f"No weekday has uncorrected p below {rule['screen_p_value']} (smallest "
                   f"{_p(p_min)}); with {rule['weekdays_tested']} weekdays tested, Bonferroni would "
                   f"need p < {rule['bonferroni_p_threshold']}. No significant weekday effect.")
    if natural:
        question = _natural("weekday", ticker=ticker, start=start, as_of=as_of)
    else:
        question = (f"For {ticker} between {start} and {as_of}, call test_weekday_pattern. "
                    f"Commit the weakest-weekday evidence, pick an educational label, and note "
                    f"the multiple-testing caveat.")
    explanation = (f"test_weekday_pattern for {ticker}, {start} to {as_of}: highest "
                   f"{describe(strongest)}; lowest {describe(weakest)}. {verdict} "
                   f"label_rule: uncorrected p < {rule['screen_p_value']} → INVESTIGATE, otherwise "
                   f"WATCH. Selected: {label}.")
    evidence_id = f"test_weekday_pattern:{ticker}:{start}:{as_of}"
    messages = _opening(mcp, natural, question)
    messages += _tool_message("test_weekday_pattern", args, result)
    messages.append(_assistant_finalize(label, explanation, [evidence_id]))
    return {"scenario": "weekday", "messages": messages, "variant": start,
            "label": label, "ticker": ticker, "as_of": as_of, "natural": natural}


REVERSAL_LOOKBACKS = [60, 90, 120, 180, 252]


def build_reversal_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    lookback = random.choice(REVERSAL_LOOKBACKS)
    natural = random.random() < NATURAL_SHARE
    args = {"ticker": ticker, "as_of": as_of, "lookback": lookback}
    result = _mcp_call(mcp, "detect_reversal_events", args)
    if not result or _is_error(result):
        return None
    summary = _structured(result).get("summary") or []
    families = [s for s in summary if s.get("mean_forward_5d") is not None]
    if not families:
        return None
    rule = label_rules.REVERSAL_RULE
    eligible = [s for s in families if s["n_forward_5d"] >= rule["min_events"]]
    best = max(eligible, key=lambda s: s["mean_forward_5d"]) if eligible else None
    label = label_rules.reversal_label(best["mean_forward_5d"], best["n_forward_5d"]) if best else "WATCH"
    listed = "; ".join(f"{s['event_type']}: {s['count']} events, mean_forward_5d "
                       f"{_f(s['mean_forward_5d'])}" for s in families[:4])
    best_text = (f"The best family with at least {rule['min_events']} forward returns is "
                 f"{best['event_type']} at {_f(best['mean_forward_5d'])}." if best else
                 f"No family has at least {rule['min_events']} forward returns.")
    if natural:
        question = _natural("reversal", ticker=ticker, lookback=lookback, as_of=as_of)
    else:
        question = (f"For {ticker} as of {as_of} with lookback {lookback} days, call "
                    f"detect_reversal_events. Compare event-family forward-5d returns, commit the "
                    f"strongest signal, pick a label.")
    explanation = (f"detect_reversal_events for {ticker}, {lookback} sessions to {as_of} (summary): "
                   f"{listed}. {best_text} label_rule: mean_forward_5d > {rule['candidate_above']} → "
                   f"TECHNICAL_REVERSAL_CANDIDATE, otherwise WATCH. Selected: {label}. "
                   f"In-sample only; not a trading signal.")
    evidence_id = f"detect_reversal_events:{ticker}:{as_of}:lb{lookback}"
    messages = _opening(mcp, natural, question)
    messages += _tool_message("detect_reversal_events", args, result)
    messages.append(_assistant_finalize(label, explanation, [evidence_id]))
    return {"scenario": "reversal", "messages": messages, "variant": f"lb{lookback}",
            "label": label, "ticker": ticker, "as_of": as_of, "natural": natural}


def build_fundamental_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    args = {"ticker": ticker, "as_of": as_of}
    natural = random.random() < NATURAL_SHARE
    result = _mcp_call(mcp, "calculate_fundamental_change", args)
    if not result or _is_error(result):
        return None
    data = _unwrap(result)
    if not isinstance(data, dict) or data.get("available") is False:
        return None
    metric = random.choice(FUND_METRICS)
    value = data.get(metric)
    if value is None:
        return None
    rev_qoq = data.get("revenue_qoq")
    label = label_rules.fundamental_label(metric, value, rev_qoq)
    rule = label_rules.FUNDAMENTAL_RULE
    name = FUND_METRIC_LABELS[metric]
    others = "; ".join(f"{k} {_f(v)}" for k, v in data.items()
                       if k.endswith("_qoq") and k != metric and v is not None)
    period = str(data.get("financial_period", ""))[:10]
    published = str(data.get("financial_available_at", ""))[:10]
    if natural:
        question = _natural("fundamental", ticker=ticker, as_of=as_of, metric_name=name)
    else:
        question = (f"For {ticker} as of {as_of}, call calculate_fundamental_change. Focus on the "
                    f"quarter-over-quarter {name} change and pick an educational label.")
    explanation = (f"calculate_fundamental_change for {ticker} as of {as_of}: {metric} {_f(value)} "
                   f"(other qoq: {others}). Latest statements: period {period}, published {published}. "
                   f"label_rule: qoq > {rule['improvement_above']} → FUNDAMENTAL_IMPROVEMENT_CANDIDATE "
                   f"(net_profit_qoq also needs revenue_qoq > 0); < {rule['reject_below']} → "
                   f"REJECT_SIGNAL; otherwise WATCH. Selected: {label}.")
    evidence_id = f"calculate_fundamental_change:{ticker}:{as_of}:{metric}"
    messages = _opening(mcp, natural, question)
    messages += _tool_message("calculate_fundamental_change", args, result)
    messages.append(_assistant_finalize(label, explanation, [evidence_id]))
    return {"scenario": "fundamental", "messages": messages, "variant": f"{metric}-{int(natural)}",
            "label": label, "ticker": ticker, "as_of": as_of, "natural": natural}


def _gate_reason(gate: Any) -> str:
    data = _unwrap(gate)
    if isinstance(data, dict):
        reasons = data.get("hard_blocks") or data.get("reasons") or []
        return f"gate_status {data.get('gate_status')}: {reasons[0] if reasons else 'no reason given'}"
    return "gate unavailable"


def build_analysis_unsafe_example(mcp: MCPStdioClient, ticker: str, as_of: str) -> dict | None:
    pattern = random.choice(["future_date", "bad_ticker", "incomplete", "no_fundamentals"])
    natural = random.random() < NATURAL_SHARE and pattern != "incomplete"
    if pattern == "future_date":
        as_of = random.choice(FUTURE_DATES)
        gate_args = {"ticker": ticker, "as_of": as_of}
        gate = _mcp_call(mcp, "check_data_quality", gate_args)
        if gate is None or _is_error(gate):
            return None
        question = (_natural("future_date", ticker=ticker, as_of=as_of) if natural else
                    f"Analyze {ticker} as of {as_of}. Call check_data_quality and commit the gate decision.")
        explanation = (f"check_data_quality: {_gate_reason(gate)}. A date after today has no "
                       f"point-in-time data, so the label is ANALYSIS_UNSAFE and no figures are reported.")
        tool_sequence = [("check_data_quality", gate_args, gate)]
        label = "ANALYSIS_UNSAFE"
    elif pattern == "bad_ticker":
        ticker = random.choice(UNKNOWN_TICKERS)
        ind_args = {"ticker": ticker, "as_of": as_of}
        indicators = _mcp_call(mcp, "calculate_indicators", ind_args)
        gate_args = {"ticker": ticker, "as_of": as_of}
        gate = _mcp_call(mcp, "check_data_quality", gate_args)
        if indicators is None or gate is None or _is_error(gate):
            return None
        question = (_natural("bad_ticker", ticker=ticker, as_of=as_of) if natural else
                    f"Analyze {ticker} as of {as_of}. Call calculate_indicators and check_data_quality.")
        explanation = (f"calculate_indicators returned an error for {ticker} (INVALID_SYMBOL: not in "
                       f"the cached universe). check_data_quality: {_gate_reason(gate)}. Label "
                       f"ANALYSIS_UNSAFE; no figures are reported.")
        tool_sequence = [("calculate_indicators", ind_args, indicators),
                         ("check_data_quality", gate_args, gate)]
        label = "ANALYSIS_UNSAFE"
    elif pattern == "no_fundamentals":
        if ticker == "THYAO.IS":
            return None
        f_args = {"ticker": ticker, "as_of": as_of}
        change = _mcp_call(mcp, "calculate_fundamental_change", f_args)
        if change is None or _is_error(change):
            return None
        data = _unwrap(change)
        if not isinstance(data, dict) or data.get("available") is not False:
            return None
        question = (_natural("no_fundamentals", ticker=ticker, as_of=as_of) if natural else
                    f"For {ticker} as of {as_of}, call calculate_fundamental_change and pick an "
                    f"educational label.")
        explanation = (f"calculate_fundamental_change returned available=false for {ticker}: the "
                       f"fundamentals dataset has no statements for this ticker. Fundamental change "
                       f"cannot be assessed and is not estimated. Label INVESTIGATE.")
        tool_sequence = [("calculate_fundamental_change", f_args, change)]
        label = "INVESTIGATE"
    else:  # incomplete
        ind_args = {"ticker": ticker, "as_of": as_of}
        indicators = _mcp_call(mcp, "calculate_indicators", ind_args)
        if indicators is None or _is_error(indicators):
            return None
        gate_args = {"ticker": ticker, "as_of": as_of}
        gate = _mcp_call(mcp, "check_data_quality", gate_args)
        if gate is None or _is_error(gate):
            return None
        question = (f"Analyze {ticker} as of {as_of} but only call calculate_indicators (no "
                    f"scores, no backtest). Then call check_data_quality.")
        explanation = (f"check_data_quality: {_gate_reason(gate)}. Required evidence is missing, so "
                       f"the label is INVESTIGATE; no conclusion is drawn from calculate_indicators alone.")
        tool_sequence = [("calculate_indicators", ind_args, indicators),
                         ("check_data_quality", gate_args, gate)]
        label = "INVESTIGATE"

    evidence_ids = [f"{name}:{args.get('ticker', ticker)}:{args.get('as_of', as_of)}"
                    for name, args, _ in tool_sequence]
    messages = _opening(mcp, natural, question)
    for name, args, result in tool_sequence:
        messages += _tool_message(name, args, result)
    messages.append(_assistant_finalize(label, explanation, evidence_ids))
    return {"scenario": "analysis_unsafe", "messages": messages, "variant": pattern,
            "label": label, "ticker": ticker, "as_of": as_of, "natural": natural}


BUILDERS = {
    "sector_lag": build_sector_lag_example,
    "weekday": build_weekday_example,
    "reversal": build_reversal_example,
    "fundamental": build_fundamental_example,
    "analysis_unsafe": build_analysis_unsafe_example,
}


def _is_duplicate(example: dict, pool: list[dict]) -> bool:
    key = (example["scenario"], example["ticker"], example["as_of"], example.get("variant"),
           example.get("natural"))
    return any((e["scenario"], e["ticker"], e["as_of"], e.get("variant"), e.get("natural")) == key
               for e in pool)


def _grounding_check(example: dict) -> list[str]:
    """Every figure in the final answer must be traceable to the tool messages or the prompt."""
    from bist_analytics.harness.grounding import audit_answer
    tools = [m["content"] for m in example["messages"] if m["role"] == "tool"]
    prompts = [m["content"] for m in example["messages"] if m["role"] in ("system", "user")]
    answer = example["messages"][-1]["content"]
    return [f["text"] for f in audit_answer(answer, tools, prompt_texts=prompts)["ungrounded"]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    ungrounded_rejects: list[dict] = []
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
                bad = _grounding_check(example)
                if bad:
                    rejects[scenario] += 1
                    ungrounded_rejects.append({"scenario": scenario, "ticker": example["ticker"],
                                               "as_of": example["as_of"], "ungrounded": bad})
                    continue
                examples.append(example)
            print(f"[{scenario}] built {sum(1 for e in examples if e['scenario'] == scenario)}/"
                  f"{target} in {attempts} attempts ({rejects[scenario]} rejected)", flush=True)
    finally:
        mcp.close()

    random.shuffle(examples)
    train: list[dict] = []
    eval_: list[dict] = []
    by_scenario: dict[str, list[dict]] = {}
    for ex in examples:
        by_scenario.setdefault(ex["scenario"], []).append(ex)
    for _scenario, items in by_scenario.items():
        cut = max(1, int(round(len(items) * 0.2)))
        eval_.extend(items[:cut])
        train.extend(items[cut:])

    Path(args.train_out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.train_out).open("w", encoding="utf-8") as fh:
        for ex in train:
            fh.write(json.dumps(ex, default=str, ensure_ascii=False) + "\n")
    with Path(args.eval_out).open("w", encoding="utf-8") as fh:
        for ex in eval_:
            fh.write(json.dumps(ex, default=str, ensure_ascii=False) + "\n")

    audit = {
        "dataset_version": DATASET_VERSION,
        "target": args.target,
        "scenarios_target": targets,
        "scenarios_built": {k: sum(1 for e in examples if e["scenario"] == k) for k in targets},
        "labels": {lbl: sum(1 for e in examples if e["label"] == lbl)
                   for lbl in sorted({e["label"] for e in examples})},
        "natural_share": round(sum(1 for e in examples if e.get("natural")) / max(1, len(examples)), 3),
        "rejections": rejects,
        "ungrounded_rejections": ungrounded_rejects,
        "grounding_check": "every final-answer figure traced to tool output (bist_analytics.harness.grounding)",
        "train_count": len(train), "eval_count": len(eval_),
        "train_sha256": _sha256(Path(args.train_out)), "eval_sha256": _sha256(Path(args.eval_out)),
        "tool_char_cap": TRAIN_TOOL_CHAR_CAP, "rag_top_k": RAG_TOP_K,
        "seed": args.seed, "elapsed_seconds": round(time.time() - started, 1),
    }
    Path(args.audit).write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k != "ungrounded_rejections"}, indent=2))


if __name__ == "__main__":
    main()
