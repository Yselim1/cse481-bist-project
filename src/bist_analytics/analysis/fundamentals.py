"""Build comparable financial metrics using only observations known as of a date."""

import numpy as np
import pandas as pd

from bist_analytics.config import ProjectConfig
from bist_analytics.data.fundamentals import add_availability
from bist_analytics.schemas import FLOW_METRICS

BASE_METRICS = sorted(FLOW_METRICS | {
    "cash", "financial_debt", "net_debt", "total_assets", "equity", "current_assets",
    "inventories", "current_liabilities", "shares_outstanding",
})
DERIVED_METRICS = ["revenue_growth", "ebitda_growth", "net_profit_growth", "roe", "roa",
                   "ebitda_margin", "net_margin", "net_debt_ebitda", "debt_equity", "current_ratio", "quick_ratio"]


def safe_ratio(numerator, denominator, positive_denominator: bool = True) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator):
        return np.nan
    if denominator == 0 or (positive_denominator and denominator < 0):
        return np.nan
    return float(numerator / denominator)


def _value(known: pd.DataFrame, metric: str, period: pd.Timestamp, kind: str | None = None) -> float:
    matches = known[(known.metric == metric) & (known.period_end == period)]
    if kind:
        matches = matches[matches.period_type == kind]
    if matches.empty:
        return np.nan
    times = matches["available_at"] if "available_at" in matches else matches.published_at.fillna(matches.get("assumed_published_at", pd.NaT))
    value = matches.assign(_effective_time=times).sort_values("_effective_time").iloc[-1].value
    return float(value) if pd.notna(value) else np.nan


def trailing_value(known: pd.DataFrame, metric: str, period: pd.Timestamp) -> float:
    if metric not in FLOW_METRICS:
        return _value(known, metric, period)
    for kind in ["ttm", "annual"]:
        value = _value(known, metric, period, kind)
        if np.isfinite(value):
            return value
    ends = pd.date_range(end=period, periods=4, freq="QE")
    quarters = [_value(known, metric, end, "quarter") for end in ends]
    if np.isfinite(quarters).all():
        return float(sum(quarters))
    # YTD plus prior annual minus corresponding prior YTD, within a single accounting basis.
    current = _value(known, metric, period, "ytd")
    if period.month == 12:
        return current
    annual = _value(known, metric, pd.Timestamp(period.year-1, 12, 31), "annual")
    prior = _value(known, metric, period - pd.DateOffset(years=1), "ytd")
    return current + annual - prior if np.isfinite([current, annual, prior]).all() else np.nan


def get_fundamental_metrics(records: pd.DataFrame, as_of: str | pd.Timestamp, currency: str = "USD",
                            allow_unverified: bool = False) -> dict:
    day = pd.Timestamp(as_of)
    time_col = "available_at" if "available_at" in records else "published_at"
    times = records[time_col]
    if time_col == "published_at":
        times = times.fillna(records.get("assumed_published_at", pd.NaT))
    known = records[(times <= day) & (records.vintage_verified | allow_unverified) & (records.currency == currency)].copy()
    known["_effective_time"] = times.loc[known.index]
    report_rows = known[known.metric == "revenue"]
    empty = {name: np.nan for name in BASE_METRICS + DERIVED_METRICS}
    if report_rows.empty:
        return {**empty, "financial_status": "missing", "financial_period": pd.NaT,
                "financial_available_at": pd.NaT, "earnings_available_at": pd.NaT,
                "financial_source": "", "financial_currency": currency}
    period = report_rows.period_end.max()
    latest = report_rows[report_rows.period_end == period].sort_values("_effective_time").iloc[-1]
    # Never mix different accounting bases in TTM construction or year-over-year growth.
    known = known[known.accounting_basis == latest.accounting_basis]
    metrics = {metric: trailing_value(known, metric, period) for metric in BASE_METRICS}
    if not np.isfinite(metrics["net_debt"]):
        metrics["net_debt"] = metrics["financial_debt"] - metrics["cash"]
    previous_end = period - pd.DateOffset(years=1)
    for metric in ["revenue", "ebitda", "net_profit"]:
        previous = trailing_value(known, metric, previous_end)
        metrics[metric + "_growth"] = safe_ratio(metrics[metric], previous) - 1
        metrics[metric + "_growth_status"] = "valid" if previous > 0 else "nonpositive_or_missing_comparison"
    old_equity = trailing_value(known, "equity", previous_end)
    old_assets = trailing_value(known, "total_assets", previous_end)
    # Interim statements compare balance sheets with the preceding year end, not the same prior-year quarter.
    # Use that opening balance only when the same-quarter balance is unavailable.
    if period.month != 12 and not np.isfinite(old_equity):
        old_equity = trailing_value(known, "equity", pd.Timestamp(period.year-1, 12, 31))
    if period.month != 12 and not np.isfinite(old_assets):
        old_assets = trailing_value(known, "total_assets", pd.Timestamp(period.year-1, 12, 31))
    metrics.update({
        "roe": safe_ratio(metrics["net_profit"], (metrics["equity"]+old_equity)/2),
        "roa": safe_ratio(metrics["net_profit"], (metrics["total_assets"]+old_assets)/2),
        "ebitda_margin": safe_ratio(metrics["ebitda"], metrics["revenue"]),
        "net_margin": safe_ratio(metrics["net_profit"], metrics["revenue"]),
        "net_debt_ebitda": safe_ratio(metrics["net_debt"], metrics["ebitda"]),
        "debt_equity": safe_ratio(metrics["financial_debt"], metrics["equity"]),
        "current_ratio": safe_ratio(metrics["current_assets"], metrics["current_liabilities"]),
        "quick_ratio": safe_ratio(metrics["current_assets"]-metrics["inventories"], metrics["current_liabilities"]),
    })
    relevant = known[known.period_end <= period]
    # The snapshot only exists once every included observation is already known.
    available = relevant._effective_time.max()
    for metric in DERIVED_METRICS:
        imported = _value(known, metric, period, "ratio")
        metrics["fintables_" + metric] = imported
        # Preserve calculated definitions; do not silently replace a missing denominator with a different convention.
    return {**metrics, "financial_status": "available", "financial_period": period,
            "financial_available_at": available, "earnings_available_at": latest["_effective_time"],
            "financial_currency": currency, "financial_source": latest.source_url,
            "accounting_basis": latest.accounting_basis}


def align_fundamentals(market: pd.DataFrame, records: pd.DataFrame, fx: pd.DataFrame,
                       config: ProjectConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    available = add_availability(records, market.index)
    allow_unverified = config.vintage_policy == "retrospective"
    dates = available.loc[available.vintage_verified | allow_unverified, "available_at"].dropna().drop_duplicates().sort_values()
    snapshots = pd.DataFrame([{**get_fundamental_metrics(available, day, config.fundamental_currency, allow_unverified),
                               "available_at": day} for day in dates])
    if snapshots.empty:
        result = pd.DataFrame(index=market.index)
        for metric in BASE_METRICS + DERIVED_METRICS:
            result[metric] = np.nan
        result["financial_period"] = pd.NaT
        result["earnings_available_at"] = pd.NaT
        result["financial_status"] = "missing"
    else:
        result = pd.merge_asof(pd.DataFrame({"date": market.index}), snapshots.sort_values("available_at"),
                               left_on="date", right_on="available_at", direction="backward").set_index("date")
    # FX uses exact session dates. Missing daily conversion rates stay missing.
    result["usdtry"] = fx.close.reindex(market.index)
    result["market_cap_try"] = market.raw_close * result.shares_outstanding
    result["market_cap_usd"] = result.market_cap_try / result.usdtry
    market_cap = result.market_cap_usd if config.fundamental_currency == "USD" else result.market_cap_try
    for output, denominator in [("pe", "net_profit"), ("pb", "equity")]:
        result[output] = market_cap / result[denominator].where(result[denominator] > 0)
    result["ev_ebitda"] = (market_cap + result.net_debt) / result.ebitda.where(result.ebitda > 0)
    result["financial_age_days"] = (result.index.to_series() - pd.to_datetime(result.earnings_available_at)).dt.days
    result["financial_fresh"] = result.financial_age_days.between(0, config.max_fundamental_age_days)
    result["financial_status"] = result.financial_status.fillna("missing")
    result["vintage_policy"] = config.vintage_policy
    result.loc[(result.financial_status == "available") & ~result.financial_fresh, "financial_status"] = "stale"
    return result, snapshots
