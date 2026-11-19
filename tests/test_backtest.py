import numpy as np
import pandas as pd
import pytest

from bist_analytics.backtest.engine import replay_order_equity, run_backtest
from bist_analytics.backtest.metrics import calculate_performance, equity_metrics
from bist_analytics.config import ProjectConfig, StrategyConfig
from bist_analytics.strategy.rules import generate_signal


def feature_frame():
    return pd.DataFrame({"open": [100., 110., 80., 90.], "close": [100., 90., 80., 90.],
        "sma_fast": 110., "sma_slow": 100., "rsi": 50., "support_distance": .01,
        "technical_score": 5., "fundamental_score": 5., "combined_score": 1.,
        "financial_fresh": True}, index=pd.bdate_range("2023-01-02", periods=4))


def test_next_open_gap_and_two_sided_costs_by_hand():
    data = feature_frame()
    result = run_backtest(data, ProjectConfig(initial_capital=1000, commission_bps=100, slippage_bps=100))
    assert result.orders.execution_date.iloc[:2].tolist() == list(data.index[1:3])
    assert (result.orders.execution_date > result.orders.decision_date).all()
    units = 1000/(110*1.01*1.01)
    expected_cash = units*(80*.99)*.99
    assert result.daily.equity.iloc[2] == pytest.approx(expected_cash)
    assert result.trades.net_pnl.iloc[0] == pytest.approx(expected_cash-1000)
    assert result.orders.side.tolist() == ["BUY", "SELL"]
    assert result.signals.reason.iloc[1] == "close_stop_loss"
    # Final close BUY signal remains unfilled, never assigned a fabricated next open.
    assert result.signals.action.iloc[-1] == "BUY"
    gross = replay_order_equity(data,result)
    assert gross.iloc[-1] == pytest.approx(1000*80/110)
    assert gross.iloc[-1] > result.daily.equity.iloc[-1]


def test_always_long_gross_matches_price_ratio_and_open_trade_not_win():
    data = feature_frame()
    result = run_backtest(data, ProjectConfig(commission_bps=0, slippage_bps=0), "buy_hold")
    np.testing.assert_allclose(result.daily.equity, 100000*data.close/data.open.iloc[0])
    metrics = calculate_performance(result)
    assert metrics["closed_trades"] == 0 and metrics["win_rate"] is None
    assert metrics["open_trades"] == 1


def test_metrics_include_first_day_loss_and_initial_high_water_mark():
    equity = pd.Series([90., 108., 81.], index=pd.bdate_range("2020-01-01", periods=3))
    result = equity_metrics(equity, 100)
    assert result["cumulative_return"] == pytest.approx(-.19)
    assert result["maximum_drawdown"] == pytest.approx(-.25)
    assert result["sharpe_zero_risk_free"] == pytest.approx(np.mean([-.1,.2,-.25])/np.std([-.1,.2,-.25], ddof=1)*np.sqrt(252))
    flat = equity_metrics(pd.Series([100.,100.], index=equity.index[:2]), 100)
    assert flat["sharpe_zero_risk_free"] is None


def test_stale_fundamentals_force_exit_and_no_entries():
    row = feature_frame().iloc[0].copy()
    row.financial_fresh = False
    assert generate_signal(row, False, 0, 0, StrategyConfig()).action == "HOLD"
    assert generate_signal(row, True, 100, 2, StrategyConfig()).action == "SELL"
    assert generate_signal(row, False, 0, 0, StrategyConfig(), "technical").action == "BUY"


def test_future_price_changes_do_not_rewrite_past_orders():
    data = feature_frame()
    first = run_backtest(data, ProjectConfig())
    data.loc[data.index[-1], ["open", "close"]] = 1000
    second = run_backtest(data, ProjectConfig())
    pd.testing.assert_frame_equal(first.orders.iloc[:2], second.orders.iloc[:2])
