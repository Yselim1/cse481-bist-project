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


def _r(value, places: int = 4):
    return None if value is None else round(float(value), places)


def summarize_sectors(rows: list[dict]) -> list[dict]:
    """Per sector: members, mean, laggard and leader (by relative_vs_sector), and the label the
    SECTOR_RULE gives the laggard. Deterministic arithmetic over the returned rows."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("sector") and row.get("relative_vs_sector") is not None:
            groups.setdefault(row["sector"], []).append(row)
    out = []
    for sector, members in sorted(groups.items()):
        ordered = sorted(members, key=lambda r: (r["relative_vs_sector"], r["ticker"]))
        lag, lead = ordered[0], ordered[-1]
        out.append({"sector": sector, "sector_mean": _r(lag.get("sector_mean")),
                    "laggard": lag["ticker"],
                    "laggard_relative_vs_sector": _r(lag["relative_vs_sector"]),
                    "laggard_label_by_rule": sector_label(lag["relative_vs_sector"]),
                    "leader": lead["ticker"],
                    "leader_relative_vs_sector": _r(lead["relative_vs_sector"]),
                    "members": [{"ticker": r["ticker"], "cum_return": _r(r.get("cum_return")),
                                 "relative_vs_sector": _r(r["relative_vs_sector"]),
                                 "label_by_rule": sector_label(r["relative_vs_sector"])}
                                for r in members]})
    return out


def summarize_weekdays(rows: list[dict]) -> dict:
    """Highest/lowest mean weekday, smallest uncorrected p-value, and the WEEKDAY_RULE label."""
    rows = [r for r in rows if r.get("mean") is not None]
    if not rows:
        return {"available": False}
    hi = max(rows, key=lambda r: r["mean"])
    lo = min(rows, key=lambda r: r["mean"])
    with_p = [r for r in rows if r.get("p_value_uncorrected") is not None]
    sp = min(with_p, key=lambda r: r["p_value_uncorrected"]) if with_p else None
    p = sp["p_value_uncorrected"] if sp else None
    return {"highest_mean_weekday": hi["weekday"], "highest_mean": _r(hi["mean"], 6),
            "highest_mean_p_value": _r(hi.get("p_value_uncorrected"), 3), "highest_mean_count": hi.get("count"),
            "lowest_mean_weekday": lo["weekday"], "lowest_mean": _r(lo["mean"], 6),
            "lowest_mean_p_value": _r(lo.get("p_value_uncorrected"), 3), "lowest_mean_count": lo.get("count"),
            "smallest_p_weekday": sp["weekday"] if sp else None, "smallest_p_value": _r(p, 3),
            "any_below_screen_p": p is not None and p < WEEKDAY_RULE["screen_p_value"],
            "any_below_bonferroni_p": p is not None and p < WEEKDAY_RULE["bonferroni_p_threshold"],
            "label_by_rule": weekday_label(p)}


def best_reversal_family(summary: list[dict]) -> dict:
    """The family with the highest mean_forward_5d among those with >= min_events forward returns."""
    eligible = [s for s in summary if s.get("mean_forward_5d") is not None
                and s.get("n_forward_5d", 0) >= REVERSAL_RULE["min_events"]]
    if not eligible:
        return {"event_type": None, "label_by_rule": "WATCH",
                "note": "no event family has >= 2 forward 5-day returns"}
    best = max(eligible, key=lambda s: s["mean_forward_5d"])
    return {"event_type": best["event_type"], "count": best["count"],
            "mean_forward_5d": best["mean_forward_5d"],
            "label_by_rule": reversal_label(best["mean_forward_5d"], best["n_forward_5d"])}


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
