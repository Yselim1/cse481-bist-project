"""Deterministic scoring and evidence gates for structured harness answers."""

from __future__ import annotations

import math
from typing import Any

EXPECTED = {
    "as_of": "2026-09-25",
    "financial_period": "2026-06-30",
    "revenue_try_million": 1_132_505.0,
    "net_profit_try_million": 112_059.0,
    "net_debt_try_million": 620_378.0,
    "combined_return": -0.11029793916663655,
    "technical_return": 0.06421505249467252,
    "buy_hold_return": 0.05291060851497198,
    "bist100_return": 0.30850781608315225,
    "signal_action": "HOLD",
    "context_event_id": "boeing-2026",
}
NUMERIC = [
    "revenue_try_million", "net_profit_try_million", "net_debt_try_million",
    "combined_return", "technical_return", "buy_hold_return", "bist100_return",
]
REQUIRED_TOOLS = {
    "get_fundamental_metrics", "calculate_indicators", "calculate_scores",
    "generate_signal", "run_backtest", "get_context_events",
}


def score_answer(answer: dict[str, Any], called_tools: set[str]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    for key in NUMERIC:
        value = answer.get(key)
        expected = EXPECTED[key]
        tolerance = max(abs(expected) * 1e-6, 1e-8)
        checks[key] = isinstance(value, (int, float)) and math.isfinite(value) and abs(value - expected) <= tolerance
    checks["as_of"] = answer.get("as_of") == EXPECTED["as_of"]
    checks["financial_period"] = answer.get("financial_period") == EXPECTED["financial_period"]
    checks["signal_action"] = answer.get("signal_action") == EXPECTED["signal_action"]
    checks["context_event"] = EXPECTED["context_event_id"] in (answer.get("context_event_ids") or [])
    numeric_score = sum(checks[key] for key in NUMERIC) / len(NUMERIC)
    evidence_score = len(REQUIRED_TOOLS & called_tools) / len(REQUIRED_TOOLS)
    temporal_valid = checks["as_of"] and checks["financial_period"] and checks["context_event"]
    constraint_valid = bool(answer.get("educational_caveat")) and not bool(answer.get("investment_recommendation"))
    claimed_tools = {name.removeprefix("mcp__bist__") for name in answer.get("evidence_tools", [])}
    unsupported = sorted(claimed_tools - called_tools)
    missing_data_honesty = (all(answer.get(key) is None for key in NUMERIC) if not called_tools else
                            all(answer.get(key) is not None for key in NUMERIC))
    required_fields = {"as_of", "financial_period", *NUMERIC, "signal_action", "context_event_ids",
                       "evidence_tools", "educational_caveat", "investment_recommendation", "narrative"}
    return {
        "checks": checks, "numeric_exactness": numeric_score, "evidence_coverage": evidence_score,
        "temporal_validity": temporal_valid, "constraint_compliance": constraint_valid,
        "missing_data_honesty": missing_data_honesty,
        "workflow_completion": evidence_score,
        "structured_reproducibility": required_fields <= set(answer),
        "unsupported_tool_claims": unsupported,
        "quality_gate_pass": numeric_score == 1 and evidence_score == 1 and temporal_valid
                             and constraint_valid and not unsupported,
    }
