"""Technical reversal event detection; emits a tidy event table for Scenario 3 analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd

EVENT_COLUMNS = ["date", "event_type", "close", "detail",
                 "forward_1d", "forward_3d", "forward_5d", "forward_10d"]


def _forward_return(close: pd.Series, horizon: int) -> pd.Series:
    return close.shift(-horizon) / close - 1


def detect_reversal_events(features: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame:
    """Emit lower/upper Bollinger touches, RSI troughs/peaks, Supertrend flips, KAMA slope flips.

    `features` must already contain the indicator columns from `calculate_indicators`.
    Output columns: ticker (optional), date, event_type, close, detail, forward_{1,3,5,10}d.
    """
    required = {"close", "rsi", "bb_lower", "bb_upper", "kama10", "supertrend_direction"}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"detect_reversal_events requires indicator columns: {sorted(missing)}")
    f1, f3, f5, f10 = (_forward_return(features.close, h) for h in (1, 3, 5, 10))
    events: list[dict] = []

    def add(date, event_type, detail):
        events.append({"date": date, "event_type": event_type, "close": features.close.loc[date],
                       "detail": detail, "forward_1d": f1.loc[date], "forward_3d": f3.loc[date],
                       "forward_5d": f5.loc[date], "forward_10d": f10.loc[date]})

    # Bollinger lower-band touches (potential oversold bounce)
    lower_touch = features.close <= features.bb_lower
    for date in features.index[lower_touch.fillna(False)]:
        add(date, "bb_lower_touch", f"close={features.close.loc[date]:.2f} vs lower={features.bb_lower.loc[date]:.2f}")
    # Bollinger upper-band touches (potential exhaustion)
    upper_touch = features.close >= features.bb_upper
    for date in features.index[upper_touch.fillna(False)]:
        add(date, "bb_upper_touch", f"close={features.close.loc[date]:.2f} vs upper={features.bb_upper.loc[date]:.2f}")
    # RSI reversals
    rsi_cross_up = (features.rsi.shift(1) < 30) & (features.rsi >= 30)
    for date in features.index[rsi_cross_up.fillna(False)]:
        add(date, "rsi_oversold_recover", f"rsi {features.rsi.shift(1).loc[date]:.1f} -> {features.rsi.loc[date]:.1f}")
    rsi_cross_down = (features.rsi.shift(1) > 70) & (features.rsi <= 70)
    for date in features.index[rsi_cross_down.fillna(False)]:
        add(date, "rsi_overbought_fade", f"rsi {features.rsi.shift(1).loc[date]:.1f} -> {features.rsi.loc[date]:.1f}")
    # Supertrend flips
    st_up = (features.supertrend_direction.shift(1) == -1) & (features.supertrend_direction == 1)
    for date in features.index[st_up.fillna(False)]:
        add(date, "supertrend_flip_up", "direction -1 -> 1")
    st_down = (features.supertrend_direction.shift(1) == 1) & (features.supertrend_direction == -1)
    for date in features.index[st_down.fillna(False)]:
        add(date, "supertrend_flip_down", "direction 1 -> -1")
    # KAMA slope flips (trend-regime change)
    kama_slope = features.kama10.diff()
    kama_up = (kama_slope.shift(1) < 0) & (kama_slope > 0)
    for date in features.index[kama_up.fillna(False)]:
        add(date, "kama_slope_up", "slope<0 -> slope>0")
    kama_down = (kama_slope.shift(1) > 0) & (kama_slope < 0)
    for date in features.index[kama_down.fillna(False)]:
        add(date, "kama_slope_down", "slope>0 -> slope<0")

    result = pd.DataFrame(events, columns=EVENT_COLUMNS).sort_values("date").reset_index(drop=True)
    if ticker:
        result.insert(0, "ticker", ticker)
    return result


def summarize_events(events: pd.DataFrame) -> pd.DataFrame:
    """Per-event-type bounce rates and mean forward returns for 1/3/5/10-day horizons."""
    if events.empty:
        return pd.DataFrame(columns=["event_type", "count", "bounce_rate_5d",
                                     "mean_forward_1d", "mean_forward_3d", "mean_forward_5d", "mean_forward_10d"])
    grouped = events.groupby("event_type", group_keys=False)
    summary = grouped.apply(lambda g: pd.Series({
        "count": len(g),
        "bounce_rate_5d": float((g.forward_5d > 0).mean()) if g.forward_5d.notna().any() else np.nan,
        "mean_forward_1d": g.forward_1d.mean(),
        "mean_forward_3d": g.forward_3d.mean(),
        "mean_forward_5d": g.forward_5d.mean(),
        "mean_forward_10d": g.forward_10d.mean(),
    })).reset_index()
    return summary
