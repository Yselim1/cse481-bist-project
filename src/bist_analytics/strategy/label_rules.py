"""Educational-label decision rules: the single source of truth for every threshold.

These thresholds are returned *inside* the tool outputs (``label_rule`` block of the MCP
envelope). That gives the model a citable source for each one and lets the grounding
audit trace a figure like "-5%" back to evidence. The fine-tuning dataset builder
(``training/dataset/build.py``) imports the same functions, so training labels and
inference-time evidence cannot drift apart.

They were fixed before the 2025 evaluation window and are not tuned on returns.
"""

from __future__ import annotations

SECTOR_RULE = {
    "metric": "relative_vs_sector",
    "catch_up_below": -0.05,
    "watch_above": 0.05,
    "rule": ("relative_vs_sector < -0.05 -> POTENTIAL_CATCH_UP_CANDIDATE; "
             "relative_vs_sector > 0.05 -> WATCH; otherwise HOLD"),
}
WEEKDAY_RULE = {
    "metric": "p_value_uncorrected",
    "screen_p_value": 0.10,
    "weekdays_tested": 5,
    "bonferroni_p_threshold": 0.01,
    "rule": ("5 weekdays are tested, so a Bonferroni-corrected 5% test needs p < 0.01. "
             "p_value_uncorrected < 0.10 -> INVESTIGATE (screen only, not significant); "
             "otherwise WATCH"),
}
REVERSAL_RULE = {
    "metric": "mean_forward_5d",
    "candidate_above": 0.005,
    "min_events": 2,
    "rule": ("event family with >= 2 events and mean_forward_5d > 0.005 -> "
             "TECHNICAL_REVERSAL_CANDIDATE; otherwise WATCH. In-sample only"),
}
FUNDAMENTAL_RULE = {
    "metric": "qoq change",
    "improvement_above": 0.10,
    "reject_below": -0.10,
    "rule": ("qoq change > 0.10 -> FUNDAMENTAL_IMPROVEMENT_CANDIDATE (net_profit_qoq also needs "
             "revenue_qoq > 0); qoq change < -0.10 -> REJECT_SIGNAL; otherwise WATCH; "
             "available=false -> INVESTIGATE"),
}
GATE_RULE = {
    "rule": ("gate_status HARD_BLOCK or ANALYSIS_UNSAFE -> ANALYSIS_UNSAFE; "
             "INVESTIGATE -> INVESTIGATE; PASS / PASS_WITH_WARNINGS -> label from the evidence"),
}


def sector_label(relative_vs_sector: float) -> str:
    if relative_vs_sector < SECTOR_RULE["catch_up_below"]:
        return "POTENTIAL_CATCH_UP_CANDIDATE"
    if relative_vs_sector > SECTOR_RULE["watch_above"]:
        return "WATCH"
    return "HOLD"


def weekday_label(p_value: float | None) -> str:
    return "INVESTIGATE" if p_value is not None and p_value < WEEKDAY_RULE["screen_p_value"] else "WATCH"


def reversal_label(mean_forward_5d: float, count: int) -> str:
    ok = count >= REVERSAL_RULE["min_events"] and mean_forward_5d > REVERSAL_RULE["candidate_above"]
    return "TECHNICAL_REVERSAL_CANDIDATE" if ok else "WATCH"


def fundamental_label(metric: str, value: float, revenue_qoq: float | None) -> str:
    if value > FUNDAMENTAL_RULE["improvement_above"]:
        if metric == "net_profit_qoq" and not (revenue_qoq or 0) > 0:
            return "WATCH"
        return "FUNDAMENTAL_IMPROVEMENT_CANDIDATE"
    if value < FUNDAMENTAL_RULE["reject_below"]:
        return "REJECT_SIGNAL"
    return "WATCH"


def summarize_reversal_events(events: list[dict]) -> list[dict]:
    """Per event_type: count and mean forward 1/3/5-day return (only non-null values)."""
    groups: dict[str, list[dict]] = {}
    for event in events:
        if event.get("event_type"):
            groups.setdefault(event["event_type"], []).append(event)
    out = []
    for event_type, rows in sorted(groups.items()):
        entry: dict = {"event_type": event_type, "count": len(rows)}
        for horizon in ("forward_1d", "forward_3d", "forward_5d"):
            values = [r[horizon] for r in rows if r.get(horizon) is not None]
            entry[f"mean_{horizon}"] = round(sum(values) / len(values), 4) if values else None
            if horizon == "forward_5d":
                entry["n_forward_5d"] = len(values)
        out.append(entry)
    out.sort(key=lambda e: (e["mean_forward_5d"] is None, -(e["mean_forward_5d"] or 0)))
    return out
