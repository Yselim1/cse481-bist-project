"""Support/resistance zones use only pivots confirmed at the decision close."""

import numpy as np
import pandas as pd

from bist_analytics.config import StrategyConfig


def confirmed_pivots(market: pd.DataFrame, left: int = 5, right: int = 5) -> pd.DataFrame:
    rows = []
    for i in range(left, len(market) - right):
        for kind, col, compare in [("high", "high", np.greater), ("low", "low", np.less)]:
            values = market[col].to_numpy()
            others = np.r_[values[i-left:i], values[i+1:i+right+1]]
            if compare(values[i], others).all():
                rows.append({"pivot_date": market.index[i], "confirmed_at": market.index[i+right],
                             "pivot_position": i, "kind": kind, "price": float(values[i])})
    return pd.DataFrame(rows, columns=["pivot_date", "confirmed_at", "pivot_position", "kind", "price"])


def cluster_prices(pivots: pd.DataFrame, tolerance: float, min_touches: int) -> list[dict]:
    groups = []
    current = []
    for record in pivots.sort_values(["price", "pivot_date"]).to_dict("records"):
        if current and np.log(record["price"] / current[0]["price"]) > np.log1p(tolerance):
            groups.append(current)
            current = []
        current.append(record)
    if current:
        groups.append(current)
    return [{"lower": min(x["price"] for x in group), "upper": max(x["price"] for x in group),
             "center": float(np.median([x["price"] for x in group])), "touches": len(group),
             "last_confirmation": max(x["confirmed_at"] for x in group)}
            for group in groups if len(group) >= min_touches]


def find_support_resistance(market: pd.DataFrame, config: StrategyConfig | None = None):
    cfg = config or StrategyConfig()
    pivots = confirmed_pivots(market, cfg.pivot_left, cfg.pivot_right)
    daily, zone_rows = [], []
    for i, (day, row) in enumerate(market.iterrows()):
        eligible = pivots[(pivots.confirmed_at <= day) & (pivots.pivot_position >= i-cfg.zone_lookback+1)]
        zones = cluster_prices(eligible, cfg.zone_tolerance, cfg.zone_min_touches)
        close = float(row.close)
        support = max((z["upper"] for z in zones if z["upper"] <= close), default=np.nan)
        resistance = min((z["lower"] for z in zones if z["lower"] >= close), default=np.nan)
        inside = any(z["lower"] <= close <= z["upper"] for z in zones)
        daily.append({"date": day, "support": support, "resistance": resistance, "in_zone": inside,
                      "support_distance": 0.0 if inside else (close-support)/close,
                      "resistance_distance": 0.0 if inside else (resistance-close)/close,
                      "zone_count": len(zones)})
        zone_rows.extend({"date": day, **z} for z in zones)
    return pd.DataFrame(daily).set_index("date"), pivots, pd.DataFrame(zone_rows)
