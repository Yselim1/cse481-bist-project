"""Scenario 1 — Sector laggards (catch-up candidates).

For each as-of date in a schedule, rank the universe by 63-session cumulative return within sector.
A ticker in the lowest sector rank is flagged as a `POTENTIAL_CATCH_UP_CANDIDATE`; we then
measure its forward 5/20-session return against its sector peers' mean forward return.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bist_analytics.analysis.grouping import rank_sector_relative_strength
from bist_analytics.scenarios._markdown import to_markdown


def _schedule(index: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp, cadence: str = "W-FRI") -> pd.DatetimeIndex:
    all_fridays = pd.date_range(start, end, freq=cadence)
    return pd.DatetimeIndex([d for d in all_fridays if d in index])


def _forward_return(frame: pd.DataFrame, start: pd.Timestamp, horizon: int) -> float:
    window = frame.loc[frame.index >= start].head(horizon + 1)
    if len(window) < horizon + 1:
        return np.nan
    return float(window.adj_close.iloc[-1] / window.adj_close.iloc[0] - 1)


def run(universe_prices: dict[str, pd.DataFrame], sector_map: dict[str, str],
        start: str | pd.Timestamp, end: str | pd.Timestamp,
        lookback: int = 63, forward_horizons: tuple[int, ...] = (5, 20),
        output_dir: Path | None = None) -> dict:
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    anchors: set[pd.Timestamp] = set()
    for frame in universe_prices.values():
        anchors.update(frame.index.tolist())
    all_sessions = pd.DatetimeIndex(sorted(anchors))
    schedule = _schedule(all_sessions, start_ts, end_ts)
    records = []
    for as_of in schedule:
        ranking = rank_sector_relative_strength(universe_prices, sector_map, as_of=as_of,
                                                lookback_sessions=lookback)
        if ranking.empty:
            continue
        for _, row in ranking.iterrows():
            forwards = {h: _forward_return(universe_prices[row.ticker], as_of, h) for h in forward_horizons}
            # sector peer forward basket (mean excluding self)
            sector_peers = ranking.loc[(ranking.sector == row.sector) & (ranking.ticker != row.ticker), "ticker"]
            peer_forwards = {h: float(np.nanmean([_forward_return(universe_prices[p], as_of, h)
                                                   for p in sector_peers])) if len(sector_peers) else np.nan
                             for h in forward_horizons}
            records.append({"as_of": as_of.strftime("%Y-%m-%d"), "ticker": row.ticker,
                            "sector": row.sector, "sector_rank": int(row.sector_rank),
                            "cum_return": row.cum_return, "sector_mean": row.sector_mean,
                            "relative_vs_sector": row.relative_vs_sector,
                            **{f"forward_{h}d": forwards[h] for h in forward_horizons},
                            **{f"peer_forward_{h}d": peer_forwards[h] for h in forward_horizons}})
    panel = pd.DataFrame(records)
    if panel.empty:
        return {"anchors": 0, "panel": panel, "summary": pd.DataFrame(),
                "warning": "No anchors produced a full ranking; verify universe coverage."}
    # Worst-ranked ticker per sector = catch-up candidate
    candidates = panel.loc[panel.sector_rank == panel.groupby(["as_of", "sector"]).sector_rank.transform("max")]
    summary = candidates.groupby("sector", group_keys=False).apply(lambda g: pd.Series({
        "candidate_signals": len(g),
        "hit_rate_5d_vs_peers": float((g.forward_5d > g.peer_forward_5d).mean()) if g.forward_5d.notna().any() else np.nan,
        "hit_rate_20d_vs_peers": float((g.forward_20d > g.peer_forward_20d).mean()) if g.forward_20d.notna().any() else np.nan,
        "mean_forward_5d": g.forward_5d.mean(),
        "mean_peer_forward_5d": g.peer_forward_5d.mean(),
        "mean_forward_20d": g.forward_20d.mean(),
        "mean_peer_forward_20d": g.peer_forward_20d.mean(),
    })).reset_index()
    result = {"anchors": len(schedule), "panel": panel, "summary": summary,
              "lookback_sessions": lookback, "forward_horizons": list(forward_horizons),
              "start": start_ts.strftime("%Y-%m-%d"), "end": end_ts.strftime("%Y-%m-%d")}
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        panel.to_csv(output_dir / "s1_sector_laggard_panel.csv", index=False)
        summary.to_csv(output_dir / "s1_sector_laggard_summary.csv", index=False)
        _write_markdown(result, output_dir / "s1_sector_laggard.md")
    return result


def _write_markdown(result: dict, path: Path) -> None:
    summary = result["summary"]
    lines = ["# Scenario 1 — Sector laggards (catch-up candidates)",
             f"\nAnchor schedule: weekly Fridays from {result['start']} to {result['end']} "
             f"({result['anchors']} anchors).",
             f"Lookback: {result['lookback_sessions']} sessions; forward horizons: "
             f"{result['forward_horizons']} sessions.",
             "\n## Candidate = worst sector_rank at each anchor; forward return vs sector peer basket mean.\n",
             "## Per-sector hit rates\n"]
    if summary.empty:
        lines.append("No usable anchors.")
    else:
        lines.append(to_markdown(summary, index=False, floatfmt=".3f"))
    path.write_text("\n".join(lines), encoding="utf-8")
