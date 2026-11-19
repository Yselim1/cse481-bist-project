"""Scenario 4 — Quarterly fundamentals release reaction.

For each Fintables release in the KAP/fundamentals ledger, measure post-release 1/5/20-session
abnormal return vs XU100 and (optionally) a sector peer basket.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bist_analytics.scenarios._markdown import to_markdown


def _forward(frame: pd.DataFrame, start: pd.Timestamp, horizon: int) -> float:
    window = frame.loc[frame.index >= start].head(horizon + 1)
    if len(window) < horizon + 1:
        return np.nan
    return float(window.adj_close.iloc[-1] / window.adj_close.iloc[0] - 1)


def _next_session(frame: pd.DataFrame, published: pd.Timestamp) -> pd.Timestamp | None:
    future = frame.index[frame.index > published]
    return future[0] if len(future) else None


def run(releases: pd.DataFrame, universe_prices: dict[str, pd.DataFrame],
        benchmark: pd.DataFrame, sector_map: dict[str, str] | None = None,
        ticker: str = "THYAO.IS", horizons: tuple[int, ...] = (1, 5, 20),
        output_dir: Path | None = None) -> dict:
    """`releases` must have columns `ticker`, `published_at`."""
    if ticker not in universe_prices:
        return {"warning": f"{ticker} absent from universe_prices", "panel": pd.DataFrame()}
    rows = []
    frame = universe_prices[ticker]
    peers = [t for t, s in (sector_map or {}).items() if s == (sector_map or {}).get(ticker) and t != ticker and t in universe_prices]
    releases = releases.copy()
    releases["published_at"] = pd.to_datetime(releases.published_at, errors="coerce", utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    for _, release in releases.iterrows():
        if pd.isna(release.published_at) or release.ticker != ticker:
            continue
        anchor = _next_session(frame, release.published_at)
        if anchor is None:
            continue
        stock = {h: _forward(frame, anchor, h) for h in horizons}
        index_ = {h: _forward(benchmark, anchor, h) for h in horizons}
        peer_basket = {h: float(np.nanmean([_forward(universe_prices[p], anchor, h) for p in peers]))
                       if peers else np.nan for h in horizons}
        rows.append({"ticker": ticker, "published_at": str(release.published_at.date()),
                     "anchor": str(anchor.date()),
                     **{f"stock_{h}d": stock[h] for h in horizons},
                     **{f"bist_{h}d": index_[h] for h in horizons},
                     **{f"peer_{h}d": peer_basket[h] for h in horizons},
                     **{f"abnormal_vs_bist_{h}d": stock[h] - index_[h] if pd.notna(stock[h]) and pd.notna(index_[h]) else np.nan
                        for h in horizons},
                     **{f"abnormal_vs_peers_{h}d": stock[h] - peer_basket[h] if pd.notna(stock[h]) and pd.notna(peer_basket[h]) else np.nan
                        for h in horizons}})
    panel = pd.DataFrame(rows)
    summary = pd.DataFrame()
    if not panel.empty:
        agg = {f"abnormal_vs_bist_{h}d": ["mean", "median", lambda s: float((s > 0).mean())] for h in horizons}
        agg.update({f"abnormal_vs_peers_{h}d": ["mean", "median", lambda s: float((s > 0).mean())] for h in horizons})
        summary = panel.agg(agg).T
        summary.columns = ["mean", "median", "positive_rate"]
    result = {"panel": panel, "summary": summary, "ticker": ticker, "horizons": list(horizons)}
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        panel.to_csv(output_dir / "s4_fundamental_reaction_panel.csv", index=False)
        if not summary.empty:
            summary.to_csv(output_dir / "s4_fundamental_reaction_summary.csv")
        _write_markdown(result, output_dir / "s4_fundamental_reaction.md")
    return result


def _write_markdown(result: dict, path: Path) -> None:
    lines = [f"# Scenario 4 — Quarterly fundamental release reaction ({result['ticker']})",
             f"\nForward horizons: {result['horizons']} sessions from next session open after release.",
             "\n## Release-by-release panel\n"]
    panel = result["panel"]
    if panel.empty:
        lines.append("No releases with usable forward windows.")
    else:
        lines.append(to_markdown(panel, index=False, floatfmt=".3f"))
    lines.append("\n## Aggregate abnormal return distribution\n")
    summary = result["summary"]
    if summary.empty:
        lines.append("No aggregate.")
    else:
        lines.append(to_markdown(summary.round(4), index=True, floatfmt=".4f"))
    path.write_text("\n".join(lines), encoding="utf-8")
