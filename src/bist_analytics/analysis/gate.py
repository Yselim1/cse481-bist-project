"""Five-state data-quality gate (PASS / PASS_WITH_WARNINGS / INVESTIGATE / ANALYSIS_UNSAFE / HARD_BLOCK).

The gate runs after tools and before explanation. Hard blocks are safety rails the agent
cannot override — they catch look-ahead bias, future statements, broken price history, period
mismatch and backtest leakage. The rest of the states admit the answer with increasing caveats.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bist_analytics.schemas import GATE_STATES, EvidenceBundle


@dataclass
class GateDecision:
    status: str  # one of GATE_STATES
    reasons: list[str]
    hard_blocks: list[str]
    warnings: list[str]


def _to_decision(status: str, reasons: list[str], hard_blocks: list[str], warnings: list[str]) -> GateDecision:
    assert status in GATE_STATES
    return GateDecision(status=status, reasons=reasons, hard_blocks=hard_blocks, warnings=warnings)


def check_data_quality(bundle: EvidenceBundle, *,
                       max_fundamental_age_days: int = 230,
                       required_evidence_tools: tuple[str, ...] = (
                           "calculate_indicators", "calculate_scores", "run_backtest"),
                       as_of_boundary: str | pd.Timestamp | None = None) -> GateDecision:
    """Run the 5-state gate against an evidence bundle.

    Hard blocks:
      - FUTURE_STATEMENT: any committed evidence dated after `as_of`.
      - LOOK_AHEAD: any observation marked future-known in notes.
      - PRICE_HISTORY_BROKEN: any evidence note names a broken history gap.
      - PERIOD_MISMATCH: TMS 29/pre-TMS 29 crossing flagged in notes.
      - BACKTEST_LEAKAGE: run_backtest evidence note indicates in-sample tuning on holdout.

    Soft escalations:
      - Missing required evidence tool -> INVESTIGATE.
      - Stale fundamentals (> max_fundamental_age_days) -> INVESTIGATE or ANALYSIS_UNSAFE.
      - Non-empty warnings but no hard blocks -> PASS_WITH_WARNINGS.
    """
    reasons: list[str] = []
    hard_blocks: list[str] = []
    warnings: list[str] = list(bundle.warnings)

    as_of_ts = pd.Timestamp(as_of_boundary or bundle.as_of)
    for item in bundle.committed:
        if item.as_of is not None:
            try:
                if pd.Timestamp(item.as_of) > as_of_ts:
                    hard_blocks.append(f"FUTURE_STATEMENT: evidence {item.evidence_id} dated {item.as_of} > as_of {bundle.as_of}")
            except (ValueError, TypeError):
                warnings.append(f"Unparseable as_of on evidence {item.evidence_id}")
        note = (item.note or "").lower()
        if "look-ahead" in note or "future-known" in note:
            hard_blocks.append(f"LOOK_AHEAD: evidence {item.evidence_id} flagged '{item.note}'")
        if "broken history" in note or "broken_price_history" in note:
            hard_blocks.append(f"PRICE_HISTORY_BROKEN: evidence {item.evidence_id} flagged '{item.note}'")
        if "period mismatch" in note or "tms29 crossing" in note:
            hard_blocks.append(f"PERIOD_MISMATCH: evidence {item.evidence_id} flagged '{item.note}'")
        if "backtest leakage" in note or "in-sample tuning" in note:
            hard_blocks.append(f"BACKTEST_LEAKAGE: evidence {item.evidence_id} flagged '{item.note}'")

    tools_cited = {item.source_tool for item in bundle.committed}
    missing_required = [t for t in required_evidence_tools if t not in tools_cited]
    if missing_required and bundle.educational_label != "ANALYSIS_UNSAFE":
        reasons.append(f"Missing committed evidence from required tools: {missing_required}")

    # Fundamental staleness: find the latest fundamental publication among committed evidence.
    fundamental_items = [i for i in bundle.committed if i.source_tool == "get_fundamental_metrics" and i.as_of]
    if fundamental_items:
        latest = max(pd.Timestamp(i.as_of) for i in fundamental_items)
        age_days = (as_of_ts - latest).days
        if age_days > 2 * max_fundamental_age_days:
            hard_blocks.append(f"STALE_FUNDAMENTALS: {age_days} days > 2x limit {max_fundamental_age_days}")
        elif age_days > max_fundamental_age_days:
            reasons.append(f"Fundamentals stale: {age_days} > {max_fundamental_age_days} days")

    if hard_blocks:
        return _to_decision("HARD_BLOCK", reasons, hard_blocks, warnings)
    if bundle.educational_label == "ANALYSIS_UNSAFE":
        return _to_decision("ANALYSIS_UNSAFE", reasons or ["Agent chose ANALYSIS_UNSAFE"], hard_blocks, warnings)
    if reasons:
        return _to_decision("INVESTIGATE", reasons, hard_blocks, warnings)
    if warnings:
        return _to_decision("PASS_WITH_WARNINGS", reasons, hard_blocks, warnings)
    return _to_decision("PASS", reasons, hard_blocks, warnings)
