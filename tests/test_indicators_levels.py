import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from bist_analytics.analysis.indicators import calculate_indicators, ema, rsi
from bist_analytics.analysis.levels import cluster_prices, confirmed_pivots, find_support_resistance
from bist_analytics.config import StrategyConfig


def market(n=140):
    close = 100+np.arange(n)*0.02+5*np.sin(np.arange(n)*0.7)
    return pd.DataFrame({"open": close, "high": close+1, "low": close-1, "close": close,
                         "volume": np.full(n, 1000)}, index=pd.bdate_range("2021-01-01", periods=n))


def test_hand_calculated_ema_and_rsi():
    x = pd.Series([1., 2., 3., 4., 8.])
    assert ema(x, 3).iloc[:2].isna().all()
    assert ema(x, 3).iloc[2:].tolist() == [2., 3., 5.5]
    assert rsi(pd.Series([1., 2., 3., 2.]), 3).iloc[-1] == pytest.approx(200/3)
    assert rsi(pd.Series(np.arange(30.))).iloc[-1] == 100
    assert rsi(pd.Series(-np.arange(30.))).iloc[-1] == 0
    assert rsi(pd.Series(np.ones(30))).iloc[-1] == 50


def test_indicators_have_no_future_dependence():
    data = market()
    assert_frame_equal(calculate_indicators(data).iloc[:90], calculate_indicators(data.iloc[:90]))
    assert calculate_indicators(data).macd_signal.iloc[:33].isna().all()


def test_linear_price_sma_macd_and_volume_identities():
    data = market(60)
    data["close"] = np.arange(1.,61.)
    result = calculate_indicators(data)
    assert result.sma_fast.iloc[19] == 10.5
    assert result.macd.iloc[25] == pytest.approx(7)
    assert result.macd_signal.iloc[33] == pytest.approx(7)
    assert result.macd_histogram.iloc[33] == pytest.approx(0,abs=1e-12)
    assert result.relative_volume.iloc[-1] == 1


def test_pivot_requires_right_confirmation_and_zone_prefix_invariance():
    data = market()
    cfg = StrategyConfig(pivot_left=2, pivot_right=3, zone_min_touches=2)
    pivots = confirmed_pivots(data, 2, 3)
    for row in pivots.itertuples():
        assert row.confirmed_at == data.index[row.pivot_position+3]
    full, _, zones = find_support_resistance(data, cfg)
    short, _, _ = find_support_resistance(data.iloc[:90], cfg)
    assert_frame_equal(full.iloc[:90], short)
    assert (zones.last_confirmation <= zones.date).all()


def test_cluster_does_not_chain_beyond_tolerance():
    points = pd.DataFrame({"price": [100, 101, 102], "pivot_date": pd.date_range("2020-01-01", periods=3),
                           "confirmed_at": pd.date_range("2020-01-02", periods=3)})
    groups = cluster_prices(points, .015, 2)
    assert len(groups) == 1 and groups[0]["upper"] == 101
