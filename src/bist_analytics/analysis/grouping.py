"""Sector peer basket, relative-strength ranking and weekday pattern test."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd


def build_sector_peer_groups(sector_map: dict[str, str]) -> dict[str, list[str]]:
    """Invert `{ticker: sector}` into `{sector: [tickers]}` sorted."""
    groups: dict[str, list[str]] = defaultdict(list)
    for ticker, sector in sector_map.items():
        groups[sector].append(ticker)
    return {sector: sorted(tickers) for sector, tickers in groups.items()}


def stacked_returns(universe_prices: dict[str, pd.DataFrame], column: str = "adj_close") -> pd.DataFrame:
    """Return daily log/close returns keyed by ticker as a wide DataFrame."""
    frames = {ticker: frame[column].pct_change(fill_method=None)
              for ticker, frame in universe_prices.items() if column in frame.columns}
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index()


def rank_sector_relative_strength(universe_prices: dict[str, pd.DataFrame], sector_map: dict[str, str],
                                  as_of: pd.Timestamp | str, lookback_sessions: int = 63) -> pd.DataFrame:
    """Rank each ticker by cumulative return over the lookback vs its own sector mean.

    A **negative** `relative_vs_sector` indicates a laggard — Scenario 1's catch-up candidate.
    """
    as_of = pd.Timestamp(as_of)
    rows = []
    for ticker, frame in universe_prices.items():
        sector = sector_map.get(ticker)
        if sector is None or "adj_close" not in frame.columns:
            continue
        window = frame.loc[frame.index <= as_of].tail(lookback_sessions + 1)
        if len(window) < lookback_sessions:
            continue
        cum_return = float(window.adj_close.iloc[-1] / window.adj_close.iloc[0] - 1)
        rows.append({"ticker": ticker, "sector": sector, "cum_return": cum_return})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    sector_mean = frame.groupby("sector").cum_return.transform("mean")
    frame["sector_mean"] = sector_mean
    frame["relative_vs_sector"] = frame.cum_return - sector_mean
    frame["sector_rank"] = frame.groupby("sector").cum_return.rank(ascending=False, method="min")
    frame["lookback_sessions"] = lookback_sessions
    frame["as_of"] = as_of.strftime("%Y-%m-%d")
    return frame.sort_values(["sector", "sector_rank"]).reset_index(drop=True)


def weekday_pattern_test(returns: pd.Series, min_count: int = 20) -> pd.DataFrame:
    """Per-weekday mean, median, win rate, count and t-statistic for daily returns.

    The naive t-statistic flags weekdays with persistent non-zero mean returns; the p-value
    is uncorrected for multiple testing across five weekdays.
    """
    cleaned = returns.dropna()
    if cleaned.empty:
        return pd.DataFrame(columns=["weekday", "count", "mean", "median", "win_rate",
                                     "t_statistic", "p_value_uncorrected"])
    stats = []
    for weekday, group in cleaned.groupby(cleaned.index.weekday):
        if len(group) < min_count:
            t_stat, p_val = np.nan, np.nan
        else:
            sd = group.std(ddof=1)
            t_stat = float(group.mean() / (sd / np.sqrt(len(group)))) if sd else np.nan
            # Two-tailed normal approx; adequate for a flag, not a publishable result.
            from math import erfc
            p_val = erfc(abs(t_stat) / np.sqrt(2)) if np.isfinite(t_stat) else np.nan
        stats.append({"weekday": ["Mon", "Tue", "Wed", "Thu", "Fri"][weekday] if weekday < 5 else f"d{weekday}",
                      "count": len(group), "mean": float(group.mean()), "median": float(group.median()),
                      "win_rate": float((group > 0).mean()), "t_statistic": t_stat,
                      "p_value_uncorrected": p_val})
    return pd.DataFrame(stats)


def multi_day_pattern_test(returns: pd.Series, horizon: int = 3, min_count: int = 30) -> pd.DataFrame:
    """Rolling `horizon`-day return starting from each weekday; same stats as weekday test."""
    forward = returns.rolling(horizon).sum().shift(-horizon + 1)
    return weekday_pattern_test(forward, min_count=min_count).assign(horizon_days=horizon)
