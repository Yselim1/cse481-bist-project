"""Challenge source validation, missing execution, and valuation-history boundaries."""

import numpy as np
import pandas as pd
import pytest

from bist_analytics.analysis.fundamentals import get_fundamental_metrics
from bist_analytics.analysis.scoring import calculate_fundamental_score
from bist_analytics.backtest.engine import run_backtest
from bist_analytics.backtest.metrics import calculate_performance
from bist_analytics.config import ProjectConfig, StrategyConfig
from bist_analytics.data.market import adjusted_view, normalize_download, validate_market


def market():
    return pd.DataFrame({"open":[100.,102.],"high":[105.,105.],"low":[95.,99.],
        "close":[102.,104.],"adj_close":[51.,52.],"volume":[1000.,1200.]},
        index=pd.bdate_range("2023-01-02",periods=2))


def test_yahoo_ticker_selection_and_adjustment_arithmetic():
    raw = market()
    raw.columns = pd.MultiIndex.from_tuples([(c.replace('_',' ').title(),'THYAO.IS') for c in raw])
    result = normalize_download(raw,"THYAO.IS")
    adjusted = adjusted_view(result)
    assert adjusted.open.tolist() == [50.,51.]
    assert adjusted.close.tolist() == [51.,52.]
    assert adjusted.raw_close.tolist() == [102.,104.]
    with pytest.raises(ValueError,match="Requested ticker missing"):
        normalize_download(raw,"XU100.IS")


def test_invalid_market_rows_are_rejected_without_filling():
    base = market()
    cases = [base.iloc[:0],pd.concat([base,base]),base.drop(columns="volume")]
    for bad in cases:
        with pytest.raises(ValueError):
            validate_market(bad)
    for column,value in [("close",np.nan),("open",0),("high",80),("volume",-1)]:
        bad = base.copy()
        bad.loc[bad.index[0],column] = value
        with pytest.raises(ValueError):
            validate_market(bad)


def test_no_trade_and_missing_execution_boundaries():
    base = market()
    # Absent indicators must keep the combined rule flat, not default to a valid score.
    result = run_backtest(base,ProjectConfig())
    metrics = calculate_performance(result)
    assert result.orders.empty and result.trades.empty
    assert metrics["cumulative_return"] == 0
    assert metrics["win_rate"] is None and metrics["sharpe_zero_risk_free"] is None
    base.loc[base.index[-1],"open"] = np.nan
    with pytest.raises(ValueError,match="Invalid execution"):
        run_backtest(base,ProjectConfig(),"buy_hold")


def test_pe_median_excludes_today_and_future_and_requires_complete_components():
    index = pd.bdate_range("2023-01-02",periods=8)
    data = pd.DataFrame({"pe":[10.,20.,30.,40.,50.,1.,np.nan,1000.],"revenue_growth":.2,
        "net_profit_growth":.2,"roe":.3,"net_debt_ebitda":2.,"ebitda":100.},index=index)
    cfg = StrategyConfig(valuation_min_history=5,valuation_lookback=5)
    full = calculate_fundamental_score(data,cfg)
    assert full.pe_history_median.iloc[5] == 30
    assert full.fundamental_score.iloc[5] == 5
    assert np.isnan(full.fundamental_score.iloc[6])
    pd.testing.assert_frame_equal(full.iloc[:6],calculate_fundamental_score(data.iloc[:6],cfg))
    data.loc[index[5],"ebitda"] = -100
    assert np.isnan(calculate_fundamental_score(data,cfg).fundamental_score.iloc[5])


def test_assumed_release_is_explicit_and_partial_inputs_are_not_backfilled():
    records = pd.DataFrame({"metric":["revenue","net_profit"],"value":[100.,20.],
        "period_end":pd.to_datetime(["2022-12-31"]*2),"period_type":"annual","currency":"USD",
        "published_at":pd.NaT,"assumed_published_at":pd.to_datetime(["2023-06-30","2023-07-15"]),
        "accounting_basis":"test","source_url":"https://fintables.com","vintage_verified":False})
    first = get_fundamental_metrics(records,"2023-07-01",allow_unverified=True)
    assert first["revenue"] == 100 and np.isnan(first["net_profit"])
    assert first["earnings_available_at"] == pd.Timestamp("2023-06-30")
    later = get_fundamental_metrics(records,"2023-07-16",allow_unverified=True)
    assert later["net_profit"] == 20
    assert np.isnan(get_fundamental_metrics(records,"2023-07-16")["revenue"])
