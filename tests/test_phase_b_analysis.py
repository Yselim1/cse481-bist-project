"""Phase B: new indicators, reversal events, sector/weekday grouping, and macro release-time safety."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bist_analytics.analysis.grouping import (
    build_sector_peer_groups,
    rank_sector_relative_strength,
    stacked_returns,
    weekday_pattern_test,
)
from bist_analytics.analysis.indicators import (
    atr,
    bollinger_bands,
    kama,
    supertrend,
    true_range,
)
from bist_analytics.analysis.reversals import detect_reversal_events, summarize_events
from bist_analytics.data.macro import macro_context_as_of


def _price_frame(n: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    base = 100 + np.cumsum(rng.normal(0, 1, n))
    high = base + rng.uniform(0.5, 2.5, n)
    low = base - rng.uniform(0.5, 2.5, n)
    close = base + rng.normal(0, 0.5, n)
    open_ = base + rng.normal(0, 0.5, n)
    idx = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "adj_close": close, "volume": rng.integers(1_000_000, 5_000_000, n)}, index=idx)


def test_bollinger_middle_equals_sma_and_bands_contain_middle():
    frame = _price_frame()
    bb = bollinger_bands(frame.close, 20, 2.0)
    pd.testing.assert_series_equal(bb.bb_middle.dropna(), frame.close.rolling(20).mean().dropna(),
                                   check_names=False)
    valid = bb.dropna()
    assert (valid.bb_upper > valid.bb_middle).all()
    assert (valid.bb_lower < valid.bb_middle).all()


def test_true_range_is_max_of_three_distances():
    frame = _price_frame(10)
    tr = true_range(frame.high, frame.low, frame.close)
    manual = pd.concat([frame.high - frame.low,
                        (frame.high - frame.close.shift(1)).abs(),
                        (frame.low - frame.close.shift(1)).abs()], axis=1).max(axis=1)
    pd.testing.assert_series_equal(tr, manual, check_names=False)


def test_atr_is_positive_once_seeded():
    frame = _price_frame()
    result = atr(frame.high, frame.low, frame.close, 14)
    assert result.iloc[:13].isna().all()
    assert (result.iloc[14:] > 0).all()


def test_kama_adapts_faster_on_trending_data():
    trending = pd.Series(np.linspace(100, 200, 60), index=pd.bdate_range("2024-01-02", periods=60))
    choppy = pd.Series(100 + np.sin(np.linspace(0, 20, 60)), index=pd.bdate_range("2024-01-02", periods=60))
    trending_kama = kama(trending, 10)
    choppy_kama = kama(choppy, 10)
    # Trending KAMA should closely follow the underlying series in its later half.
    trend_lag = (trending - trending_kama).dropna().abs().iloc[-20:].mean()
    choppy_lag = (choppy - choppy_kama).dropna().abs().iloc[-20:].mean()
    assert trend_lag < 5
    assert trend_lag < choppy_lag * 5  # trending KAMA is clearly closer than choppy


def test_supertrend_direction_is_plus_or_minus_one_and_flips():
    rising = pd.Series(np.linspace(100, 150, 30), index=pd.bdate_range("2024-01-02", periods=30))
    falling = pd.Series(np.linspace(150, 90, 30), index=pd.bdate_range("2024-02-12", periods=30))
    close = pd.concat([rising, falling])
    high, low = close + 1, close - 1
    st = supertrend(high, low, close, 10, 3.0)
    assert set(st.supertrend_direction.unique()).issubset({-1, 1, 0})
    # at least one flip across the trend reversal
    assert (st.supertrend_direction.diff().abs() == 2).any()


def test_reversal_events_emit_known_event_types_and_forward_returns():
    from bist_analytics.analysis.indicators import calculate_indicators

    frame = _price_frame(120)
    features = calculate_indicators(frame)
    events = detect_reversal_events(features, "TEST.IS")
    # Must cover at least a couple of the event families on 120 sessions of noise.
    assert not events.empty
    assert set(events.event_type.unique()).issubset({
        "bb_lower_touch", "bb_upper_touch", "rsi_oversold_recover",
        "rsi_overbought_fade", "supertrend_flip_up", "supertrend_flip_down",
        "kama_slope_up", "kama_slope_down",
    })
    # forward_Xd must be within [-1, +∞)
    numeric = events[["forward_1d", "forward_3d", "forward_5d", "forward_10d"]].dropna(how="all")
    assert (numeric.fillna(0) >= -1).all().all()
    summary = summarize_events(events)
    assert "count" in summary.columns and (summary["count"] > 0).all()


def test_build_sector_peer_groups_and_relative_strength_flag_laggard():
    universe = {
        "AAA.IS": pd.DataFrame({"adj_close": np.linspace(100, 130, 100)},
                               index=pd.bdate_range("2024-01-02", periods=100)),
        "BBB.IS": pd.DataFrame({"adj_close": np.linspace(100, 125, 100)},
                               index=pd.bdate_range("2024-01-02", periods=100)),
        "CCC.IS": pd.DataFrame({"adj_close": np.linspace(100, 105, 100)},
                               index=pd.bdate_range("2024-01-02", periods=100)),  # the laggard
    }
    sector_map = {"AAA.IS": "x", "BBB.IS": "x", "CCC.IS": "x"}
    groups = build_sector_peer_groups(sector_map)
    assert groups == {"x": ["AAA.IS", "BBB.IS", "CCC.IS"]}
    ranking = rank_sector_relative_strength(universe, sector_map, as_of="2024-05-01", lookback_sessions=63)
    laggard = ranking.set_index("ticker").loc["CCC.IS"]
    assert laggard.relative_vs_sector < 0
    assert laggard.sector_rank == 3


def test_stacked_returns_has_one_column_per_ticker():
    universe = {
        f"X{i}.IS": pd.DataFrame({"adj_close": np.linspace(100, 110 + i, 20)},
                                 index=pd.bdate_range("2024-01-02", periods=20))
        for i in range(3)
    }
    returns = stacked_returns(universe)
    assert list(returns.columns) == ["X0.IS", "X1.IS", "X2.IS"]
    assert returns.iloc[0].isna().all()


def test_weekday_pattern_test_reports_five_weekdays_with_counts():
    idx = pd.bdate_range("2023-01-02", "2024-12-31")
    returns = pd.Series(np.random.default_rng(0).normal(0, 0.01, len(idx)), index=idx)
    stats = weekday_pattern_test(returns, min_count=10)
    assert len(stats) == 5
    assert set(stats.weekday) == {"Mon", "Tue", "Wed", "Thu", "Fri"}
    assert (stats["count"] > 10).all()


def test_macro_context_as_of_returns_none_when_no_cache(tmp_path):
    out = macro_context_as_of(tmp_path, as_of="2026-01-01")
    assert all(v is None for v in out.values())
    assert set(out) == {"usdtry", "eurtry", "policy_rate", "cpi_yoy"}


def test_macro_context_as_of_respects_publication_lag(tmp_path):
    (tmp_path / "data/raw/macro").mkdir(parents=True)
    frame = pd.DataFrame({"date": pd.to_datetime(["2026-01-31", "2026-02-28"]),
                          "value": [55.0, 57.0],
                          "published_at": pd.to_datetime(["2026-02-05", "2026-03-05"]),
                          "source": ["TÜİK via EVDS"] * 2})
    path = tmp_path / "data/raw/macro/cpi_yoy.csv"
    frame.to_csv(path, index=False)
    from bist_analytics.io import sha256, write_json
    write_json(tmp_path / "data/raw/macro/cpi_yoy.metadata.json",
               {"series": "cpi_yoy", "sha256": sha256(path), "rows": 2})
    # as_of before any publication
    out = macro_context_as_of(tmp_path, as_of="2026-01-31", series=["cpi_yoy"])
    assert out["cpi_yoy"] is None
    # as_of after first publication, before second
    out = macro_context_as_of(tmp_path, as_of="2026-02-15", series=["cpi_yoy"])
    assert out["cpi_yoy"]["value"] == 55.0
    assert out["cpi_yoy"]["published_at"] == "2026-02-05"


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parents[1]
