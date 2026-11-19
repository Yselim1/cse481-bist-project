"""Scenario 3 — Technical reversal events.

Aggregates reversal events across the universe and reports hit rates, forward-return distributions,
and regime splits (rising vs falling XU100) for each event family.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bist_analytics.analysis.indicators import calculate_indicators
from bist_analytics.analysis.reversals import detect_reversal_events, summarize_events
from bist_analytics.scenarios._markdown import to_markdown


def _regime(benchmark: pd.DataFrame, window: int = 63) -> pd.Series:
    sma = benchmark.adj_close.rolling(window).mean()
    return pd.Series(np.where(benchmark.adj_close > sma, "rising_market", "falling_market"),
                     index=benchmark.index, name="regime")


def run(universe_prices: dict[str, pd.DataFrame], benchmark: pd.DataFrame | None,
        start: str | pd.Timestamp, end: str | pd.Timestamp,
        output_dir: Path | None = None) -> dict:
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    regime = _regime(benchmark) if benchmark is not None else None
    all_events = []
    for ticker, frame in universe_prices.items():
        features = calculate_indicators(frame)
        window = features.loc[(features.index >= start_ts) & (features.index < end_ts)]
        if window.empty:
            continue
        events = detect_reversal_events(features, ticker)
        events = events[(events.date >= start_ts) & (events.date < end_ts)].copy()
        if regime is not None:
            events["regime"] = events.date.map(regime)
        all_events.append(events)
    events_panel = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    overall = summarize_events(events_panel) if not events_panel.empty else pd.DataFrame()
    by_regime = pd.DataFrame()
    if not events_panel.empty and "regime" in events_panel.columns:
        rows = []
        for (event_type, reg), group in events_panel.groupby(["event_type", "regime"]):
            if group.forward_5d.notna().any():
                rows.append({"event_type": event_type, "regime": reg, "count": len(group),
                             "bounce_rate_5d": float((group.forward_5d > 0).mean()),
                             "mean_forward_5d": group.forward_5d.mean(),
                             "mean_forward_10d": group.forward_10d.mean()})
        by_regime = pd.DataFrame(rows)
    result = {"start": start_ts.strftime("%Y-%m-%d"), "end": end_ts.strftime("%Y-%m-%d"),
              "events_panel": events_panel, "overall": overall, "by_regime": by_regime}
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        events_panel.to_csv(output_dir / "s3_reversal_events.csv", index=False)
        overall.to_csv(output_dir / "s3_reversal_overall.csv", index=False)
        by_regime.to_csv(output_dir / "s3_reversal_by_regime.csv", index=False)
        _write_markdown(result, output_dir / "s3_reversals.md")
    return result


def _write_markdown(result: dict, path: Path) -> None:
    lines = ["# Scenario 3 — Technical reversal events",
             f"\nWindow: {result['start']} to {result['end']}.",
             "\n## Overall bounce rates and mean forward returns\n"]
    overall = result["overall"]
    if overall.empty:
        lines.append("No events observed.")
    else:
        lines.append(to_markdown(overall, index=False, floatfmt=".3f"))
    by_regime = result["by_regime"]
    lines.append("\n## By-regime breakdown (XU100 above/below 63-session SMA)\n")
    if by_regime.empty:
        lines.append("No benchmark regime assignment available.")
    else:
        lines.append(to_markdown(by_regime, index=False, floatfmt=".3f"))
    path.write_text("\n".join(lines), encoding="utf-8")
