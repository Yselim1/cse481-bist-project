import numpy as np
import pandas as pd

from bist_analytics.backtest.engine import BacktestResult
from bist_analytics.io import clean_json


def equity_metrics(equity: pd.Series, initial_capital: float, annual_sessions: int = 252) -> dict:
    if equity.empty or (equity <= 0).any() or not np.isfinite(equity).all():
        raise ValueError("Equity must be nonempty, positive and finite")
    returns = equity.pct_change(fill_method=None)
    returns.iloc[0] = equity.iloc[0]/initial_capital-1
    peaks = np.maximum.accumulate(np.r_[initial_capital, equity.to_numpy()])[1:]
    drawdown = equity.to_numpy()/peaks-1
    std = returns.std(ddof=1)
    elapsed = max((equity.index[-1]-equity.index[0]).days, 1)/365.25
    return clean_json({"initial_capital": initial_capital, "final_equity": float(equity.iloc[-1]),
        "cumulative_return": float(equity.iloc[-1]/initial_capital-1),
        "cagr": float((equity.iloc[-1]/initial_capital)**(1/elapsed)-1) if elapsed >= 1/12 else None,
        "annualized_volatility": float(std*np.sqrt(annual_sessions)),
        "sharpe_zero_risk_free": float(returns.mean()/std*np.sqrt(annual_sessions)) if std > 1e-15 else None,
        "maximum_drawdown": float(drawdown.min()), "sessions": len(equity),
        "start": str(equity.index[0].date()), "end": str(equity.index[-1].date())})


def calculate_performance(result: BacktestResult, benchmark_return: float | None = None,
                          annual_sessions: int = 252) -> dict:
    metrics = equity_metrics(result.daily.equity, result.initial_capital, annual_sessions)
    closed = result.trades[result.trades.status == "closed"]
    open_trades = result.trades[result.trades.status == "open"]
    metrics.update({"strategy": result.mode, "closed_trades": len(closed), "open_trades": len(open_trades),
        "win_rate": float((closed.net_pnl > 0).mean()) if len(closed) else None,
        "exposure": float(result.daily.position.mean()), "total_commission": float(result.daily.commission.sum()),
        "total_slippage_cost": float(result.daily.slippage_cost.sum()),
        "turnover_initial_capital": float((result.orders.units*result.orders.reference_price).sum()/result.initial_capital),
        "unrealized_pnl": float(open_trades.net_pnl.sum()),
        "benchmark_difference_pp": (metrics["cumulative_return"]-benchmark_return)*100 if benchmark_return is not None else None,
        "diagnostic_flags": [label for test, label in [(len(closed) < 10, "fewer_than_10_closed_trades"),
                                                        (result.daily.position.mean() < 0.05, "exposure_below_5_percent")]
                             if test]})
    return clean_json(metrics)


def index_equity(index: pd.DataFrame, sessions: pd.DatetimeIndex, initial_capital: float) -> pd.Series:
    matched = index.reindex(sessions)
    if matched[["open", "close"]].isna().any().any():
        raise ValueError("BIST 100 has missing matched sessions; benchmark dates must be resolved")
    return (matched.close/matched.open.iloc[0]*initial_capital).rename("bist100_price_index")
