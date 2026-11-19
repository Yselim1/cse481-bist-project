"""Phase C scenarios: smoke-test each scenario on synthetic universe data."""


import numpy as np
import pandas as pd

from bist_analytics.scenarios import (
    fundamental_reaction,
    reversal_events,
    sector_laggard,
    weekday_patterns,
)


def _synthetic_universe(n: int = 400, seed: int = 0) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-02", periods=n)
    out = {}
    for ticker, drift in [("AAA.IS", 0.001), ("BBB.IS", 0.0007), ("CCC.IS", 0.0005),
                          ("DDD.IS", 0.0002), ("EEE.IS", -0.0003)]:
        close = 100 * np.cumprod(1 + rng.normal(drift, 0.015, n))
        out[ticker] = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                                    "close": close, "adj_close": close,
                                    "volume": rng.integers(1_000_000, 5_000_000, n)}, index=idx)
    return out


def _synthetic_benchmark(n: int = 400) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-02", periods=n)
    rng = np.random.default_rng(1)
    close = 1000 * np.cumprod(1 + rng.normal(0.0004, 0.01, n))
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "adj_close": close,
                         "volume": rng.integers(10_000_000, 30_000_000, n)}, index=idx)


def test_s1_sector_laggard_produces_summary_with_hit_rates(tmp_path):
    universe = _synthetic_universe()
    sector_map = {"AAA.IS": "x", "BBB.IS": "x", "CCC.IS": "y", "DDD.IS": "y", "EEE.IS": "y"}
    result = sector_laggard.run(universe, sector_map, "2024-07-01", "2025-06-01",
                                 output_dir=tmp_path)
    assert result["anchors"] > 0
    summary = result["summary"]
    assert not summary.empty
    assert "hit_rate_5d_vs_peers" in summary.columns
    assert (tmp_path / "s1_sector_laggard.md").exists()


def test_s2_weekday_patterns_covers_each_universe_ticker(tmp_path):
    universe = _synthetic_universe()
    result = weekday_patterns.run(universe, "2024-02-01", "2025-06-01", output_dir=tmp_path)
    panel = result["weekday_panel"]
    assert set(panel.ticker.unique()) == set(universe.keys())
    assert (tmp_path / "s2_weekday.md").exists()


def test_s3_reversal_events_tags_regime(tmp_path):
    universe = _synthetic_universe()
    benchmark = _synthetic_benchmark()
    result = reversal_events.run(universe, benchmark, "2024-04-01", "2025-06-01", output_dir=tmp_path)
    assert not result["events_panel"].empty
    assert "regime" in result["events_panel"].columns
    assert (tmp_path / "s3_reversals.md").exists()


def test_s4_fundamental_reaction_computes_abnormal_returns(tmp_path):
    universe = _synthetic_universe()
    benchmark = _synthetic_benchmark()
    releases = pd.DataFrame({"ticker": ["AAA.IS"] * 3,
                             "published_at": pd.to_datetime(["2024-05-01", "2024-08-01", "2024-11-01"], utc=True)})
    result = fundamental_reaction.run(releases, universe, benchmark,
                                      sector_map={"AAA.IS": "x", "BBB.IS": "x"},
                                      ticker="AAA.IS", output_dir=tmp_path)
    assert not result["panel"].empty
    assert "abnormal_vs_bist_5d" in result["panel"].columns
    assert (tmp_path / "s4_fundamental_reaction.md").exists()


def test_scenarios_do_not_crash_on_empty_universe(tmp_path):
    empty: dict[str, pd.DataFrame] = {}
    benchmark = _synthetic_benchmark()
    r1 = sector_laggard.run(empty, {}, "2024-01-01", "2024-06-01", output_dir=tmp_path)
    assert r1["panel"].empty
    r2 = weekday_patterns.run(empty, "2024-01-01", "2024-06-01", output_dir=tmp_path)
    assert r2["weekday_panel"].empty
    r3 = reversal_events.run(empty, benchmark, "2024-01-01", "2024-06-01", output_dir=tmp_path)
    assert r3["events_panel"].empty
