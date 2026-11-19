"""Scenario 2 — Weekday and multi-day return patterns.

Applies `weekday_pattern_test` per ticker over the evaluation window and reports:
- per-weekday mean/median/win-rate/t-stat/p-value (uncorrected)
- 3-day multi-day pattern starting at each weekday
Caveat recorded in the report: no multiple-testing correction; signals are hypotheses, not rules.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from bist_analytics.analysis.grouping import multi_day_pattern_test, weekday_pattern_test
from bist_analytics.scenarios._markdown import to_markdown


def _returns(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    window = frame.loc[(frame.index >= start) & (frame.index < end)]
    return window.adj_close.pct_change(fill_method=None).dropna()


def run(universe_prices: dict[str, pd.DataFrame], start: str | pd.Timestamp, end: str | pd.Timestamp,
        multi_day_horizon: int = 3, output_dir: Path | None = None) -> dict:
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    weekday_rows = []
    multi_day_rows = []
    for ticker, frame in universe_prices.items():
        returns = _returns(frame, start_ts, end_ts)
        if returns.empty:
            continue
        weekday_stats = weekday_pattern_test(returns, min_count=20).assign(ticker=ticker)
        weekday_rows.append(weekday_stats)
        multi_stats = multi_day_pattern_test(returns, horizon=multi_day_horizon, min_count=20).assign(ticker=ticker)
        multi_day_rows.append(multi_stats)
    weekday_panel = pd.concat(weekday_rows, ignore_index=True) if weekday_rows else pd.DataFrame()
    multi_day_panel = pd.concat(multi_day_rows, ignore_index=True) if multi_day_rows else pd.DataFrame()
    result = {"start": start_ts.strftime("%Y-%m-%d"), "end": end_ts.strftime("%Y-%m-%d"),
              "weekday_panel": weekday_panel, "multi_day_panel": multi_day_panel,
              "multi_day_horizon": multi_day_horizon,
              "note": ("p-values are uncorrected for multiple testing across tickers and weekdays; "
                       "treat sub-5% flags as hypotheses to investigate, not trading rules.")}
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        weekday_panel.to_csv(output_dir / "s2_weekday_panel.csv", index=False)
        multi_day_panel.to_csv(output_dir / "s2_multi_day_panel.csv", index=False)
        _write_markdown(result, output_dir / "s2_weekday.md")
    return result


def _write_markdown(result: dict, path: Path) -> None:
    weekday = result["weekday_panel"]
    multi = result["multi_day_panel"]
    lines = ["# Scenario 2 — Weekday and multi-day patterns",
             f"\nWindow: {result['start']} to {result['end']}.",
             "\n## Per-ticker weekday mean return (sorted by |t|)\n"]
    if weekday.empty:
        lines.append("No data.")
    else:
        flagged = weekday.assign(abs_t=weekday.t_statistic.abs()).sort_values("abs_t", ascending=False).head(20)
        lines.append(to_markdown(flagged[["ticker", "weekday", "count", "mean", "win_rate",
                                           "t_statistic", "p_value_uncorrected"]],
                                 index=False, floatfmt=".4f"))
    lines.append(f"\n## Multi-day pattern (horizon={result['multi_day_horizon']}) — top 20 by |t|\n")
    if multi.empty:
        lines.append("No data.")
    else:
        flagged = multi.assign(abs_t=multi.t_statistic.abs()).sort_values("abs_t", ascending=False).head(20)
        lines.append(to_markdown(flagged[["ticker", "weekday", "count", "mean", "win_rate",
                                           "t_statistic", "p_value_uncorrected"]],
                                 index=False, floatfmt=".4f"))
    lines.append(f"\n**Caveat.** {result['note']}")
    path.write_text("\n".join(lines), encoding="utf-8")
